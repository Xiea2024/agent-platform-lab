# 实验 06 — Valkey（缓存）+ Keycloak（身份）+ 最小受保护 API

- 日期：2026-11-21
- 组件：Valkey **9.2.0**（manifest 直装）、Keycloak **26.8.1**（codecentric keycloakx chart 7.4.0，ghcr OCI）、lab-api 0.1.1（FastAPI，本地构建 + k3d image import）
- 清单：`components/06-valkey/`、`components/06-keycloak/`
- 状态：6A/6B 两子阶段独立验收全部通过 ✅

## 0. 选型与依赖决策

| 决策 | 结论 |
|---|---|
| Valkey 安装方式 | 官方 helm chart 分发渠道可达性不可靠（D-10 教训）→ 最小 manifest（Deployment+PVC+密码 Secret），镜像 `valkey/valkey:9.2` |
| Keycloak chart | bitnami chart 在 daocloud 镜像站 403 → 改 **codecentric keycloakx 7.4.0**（ghcr OCI，appVersion 26.8.1 精确锁定，含 26.8 CVE 修复） |
| Keycloak 数据库 | 复用 pg-lab（`keycloak` 库，owner=app）——**身份平面依赖数据平面**，连接走 `pg-lab-rw` |
| cert-manager | 仍不需要（Keycloak 自带 TLS 能力，本实验 HTTP 内网） |

依赖链：`lab-api → keycloak.identity:8080（JWKS 验签）→ pg-lab-rw（用户/Realm 存储）`；`API 客户端 → Keycloak（取 token）→ lab-api（Bearer 调用）`

## 1. 子阶段 6A：Valkey 验收

### 1.1 TTL

- `SET session:abc "user-session-data" EX 20` → `TTL` 依次为 20 → 12（8s 后）→ 22s 后 `GET` 返回 nil ✓
- 结论：TTL 语义精确，过期即删（惰性+主动过期）

### 1.2 持久化与重启行为（三种场景对比，教学价值最高）

| 场景 | 操作 | 结果 | 解释 |
|---|---|---|---|
| 优雅删除 Pod | `kubectl delete pod`（SIGTERM） | **数据零丢失** | valkey 停机时自动 SAVE → RDB 落盘（默认 save 点） |
| 手动 SAVE 后重启 | `SAVE` → 删 Pod | SAVE 点数据完整恢复 | RDB 快照在 `/data`（PVC），重启自动加载 |
| 崩溃（DEBUG SEGFAULT） | 写 key 不 SAVE → 段错误 | **未 SAVE 的 key 丢失**，SAVE 过的保留 ✓ | 等价断电/OOMKill：内存脏数据消失，回到最后快照点 |

- save 点配置实测：`3600 1 / 300 100 / 60 10000`
- **结论**：Valkey/Redis 持久化的 RPO = 距上次快照的脏数据窗口；AOF（appendfsync everysec）可将 RPO 降到 ~1s，本实验按最小默认 RDB 运行，AOF 列为生产选项
- 插曲：`--enable-debug-command local` 开启后才允许 DEBUG SEGFAULT（默认禁用）

## 2. 子阶段 6B：Keycloak + 受保护 API 验收

### 2.1 部署排错记录

1. **chart 默认 `command: []`** → 镜像 ENTRYPOINT 只有 `kc.sh` 无 start → 打印帮助崩溃。须显式 `command: ["/opt/keycloak/bin/kc.sh","start"]`（KC_DB* 由 chart 以环境变量注入）
2. **helm upgrade 后 StatefulSet 模板已更新但旧 Pod 不滚动** → 手动删 Pod 强制重建
3. **KC_HOSTNAME=http://keycloak.identity:8080 但无此 Service** → API 验签报 `PyJWKClientConnectionError`；ExternalName Service **不做端口映射**（kube-proxy 只改 DNS），8080 不通；最终用**双 Service 指向同一 Pod**（`keycloak-keycloakx-http:80` 对宿主，`keycloak:8080` 对集群内）使 iss 与集群内访问同源

### 2.2 Realm/Client/角色/用户

- Realm `lab`；Client `lab-api`（confidential、service account、direct grant 开启，实验固定 secret）
- Realm role `api-user`；用户 `tester`（绑 api-user）、`viewer`（不绑，对照组）；service-account-lab-api 绑 api-user
- **KC26 坑**：password grant 报 `Account is not fully set up` 的触发条件——用户缺 **email+emailVerified+firstName+lastName** 任一（逐个补齐后恢复）

### 2.3 JWT 验证（claims 实测）

```json
iss = http://keycloak.identity:8080/realms/lab
azp = lab-api
preferred_username = tester
roles = [offline_access, api-user, default-roles-lab, uma_authorization]
exp = 1795266122
```

- client_credentials（服务身份）与 password grant（用户身份）两种 token 均成功；API 侧 PyJWKClient 从 JWKS 端点拉公钥验 RS256 签名 + issuer/expiry 校验

### 2.4 RBAC 矩阵（受保护 API：FastAPI，`/public` + `/protected`）

| 场景 | 结果 | 含义 |
|---|---|---|
| GET /public 无 token | **200** | 公开端点 |
| GET /protected 无 token | **401** missing bearer token | 未认证 |
| GET /protected viewer token | **403** missing required role | 已认证（签名合法）但**授权**失败 |
| GET /protected tester token | **200** + claims 回显 | 认证+授权通过 |
| GET /protected SA token | **200** | 服务账号同样走角色体系 |

### 2.5 ⚠️ JWT 认证 ≠ 租户隔离（本阶段关键认知）

本实验的 API 只验证了 JWT 签名 + realm 角色，**没有任何租户概念**。两者的区别：

| | JWT 认证 + RBAC | 租户隔离 |
|---|---|---|
| 回答的问题 | 你是谁？你有哪些角色？ | 你只能访问哪些数据？ |
| 层面 | 身份平面（Keycloak） | 数据平面（API 逻辑 + DB） |
| 本实验覆盖 | ✅ 完整 | ❌ 零覆盖 |

实现真正多租户还需要（后续 Agent 平台阶段涉及）：
1. **租户声明**：token 中携带 tenant_id/organization claim（Keycloak Organization/客户端 scope mapper）
2. **强制过滤**：API 中间件从 token 取 tenant 声明，注入所有查询（`WHERE tenant_id = :t`），跨租户访问返回 404 而非 403
3. **数据库兜底**：PostgreSQL RLS（行级安全）以数据库角色隔离，即使应用层漏过滤也被拦截
4. **更强隔离**：schema-per-tenant / database-per-tenant / 独立部署，成本递增

结论：**"通过 JWT 认证"只是多租户的必要条件，离"租户隔离"还差整条数据面授权链**。实验环境切勿把前者当后者。

## 3. 资源实测

| 组件 | 内存 |
|---|---|
| Valkey | **4Mi**（空载极小） |
| Keycloak | **701Mi**（JVM，本阶段最大单体） |
| lab-api | 37Mi |
| WSL VM used | 5795 MiB / 15782 MiB（**36%**） |
| C: 磁盘 | 95.7GB ✓ |

## 4. 生产环境差异

- Valkey 单实例无哨兵/集群：生产按故障转移（哨兵）或分片（Cluster）选型；缓存通常允许丢失，持久化按业务定
- Keycloak 单副本 + HTTP + 固定 secret + 本地构建镜像：生产需 HA（≥2 副本 + 外部 Infinispan）、HTTPS、生产镜像供应链（Harbor 等）
- API 未校验 audience（注释标明）：生产应配 audience mapper 强校验 `aud`
- token 无租户声明/无 revocation 检查：生产按 §2.5 补全

## 5. 访问方式与清理（未执行清理）

```bash
kubectl -n identity port-forward svc/keycloak-keycloakx-http 18082:80  # Keycloak UI/REST
kubectl -n identity port-forward svc/lab-api 18000:8000                # 受保护 API
kubectl -n cache exec deploy/valkey -- valkey-cli -a $PW               # Valkey CLI
# 清理：
helm uninstall keycloak -n identity && kubectl delete ns identity cache database/cnpg 资源另算
```
