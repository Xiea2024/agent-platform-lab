# Troubleshooting — 问题与解决过程

## 2026-11-21 · k3d 集群创建后 kubectl 无法连接 API Server

**现象**

```
kubectl get nodes
E1121 ... dial tcp 192.168.5.32:5347: connectex: A connection attempt failed ...
```

**排查**

1. `k3d cluster list` 显示集群正常，容器全部 Up。
2. `docker ps`：`k3d-lab-serverlb  0.0.0.0:5347->6443/tcp` —— 端口确实发布。
3. `ping host.docker.internal` → 解析为 `192.168.5.32`（WSL vEthernet 地址），`netstat` 显示到该地址:5347 的连接一直 SYN_SENT。
4. `curl -k https://127.0.0.1:5347/version` 返回 401 Unauthorized（API Server 正常）。
5. 检查证书 SAN：包含 `IP Address:127.0.0.1` 与 `DNS:localhost`。

**根因**

本机 WSL2 使用 `networkingMode=mirrored`。k3d 写入 kubeconfig 的 API Server 地址是 `https://host.docker.internal:<port>`，该名字在 Windows 侧被解析到 WSL 虚拟网卡地址，而 Docker Desktop 发布的端口实际监听在宿主机回环（127.0.0.1），导致连接超时。这是 mirrored 网络模式 + Docker Desktop 的已知组合怪癖。

**解决**

```bash
kubectl config set-cluster k3d-lab --server=https://127.0.0.1:5347
```

（证书 SAN 已含 127.0.0.1，TLS 校验通过，无需 --insecure-skip-tls-verify）

**预防**：后续新建 k3d 集群时，检查 kubeconfig 中 server 地址；若再次写入 host.docker.internal，重复上述修正。

---

## 2026-11-21 · helm 安装 chart 时 GitHub Releases 下载超时

**现象**

```
helm install ... prometheus-community/kube-prometheus-stack --version 93.6.1
Error: INSTALLATION FAILED: Get "https://github.com/prometheus-community/helm-charts/releases/download/..." wsarecv: 连接超时
```

连续两次失败（本机访问 github.com release asset 不通，但 api.github.com / ghcr.io / docker.io 均正常）。

**解决**

改用该 chart 同步发布的 OCI 制品（ghcr.io 连通良好）：

```bash
helm install kube-prometheus-stack oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack \
  --version 93.6.1 -n monitoring --create-namespace -f <values>
```

**经验**：prometheus-community 的 chart 同时发布 GitHub Releases(tgz) 与 ghcr OCI 两种形态；前者不可达时优先尝试 OCI。

---

## 2026-11-21 · 本机 DNS 拦截部分 GitHub 域名（getaddrinfow: no data / 0.0.0.0）

**现象**

阶段 03 安装 Argo CD 时：

```
helm repo add argo https://argoproj.github.io/argo-helm
Error: ... lookup argoproj.github.io: getaddrinfow: The requested name is valid, but no data of the requested type is found
```

**排查**

`nslookup` 结果对比：

| 域名 | 解析结果 | 结论 |
|---|---|---|
| raw.githubusercontent.com | **0.0.0.0** | 被拦截（黑洞） |
| argoproj.github.io | **0.0.0.0** | 被拦截（黑洞） |
| api.github.com | 正常 | 可用 |
| github.com | 正常（git push 成功） | 可用 |
| quay.io / ghcr.io / docker.io | 正常 | 可用 |

**根因**：本地 DNS 对 raw.githubusercontent.com、*.github.io 等域名返回 0.0.0.0（典型网络环境拦截）。

**解决（按优先级）**

1. 目标组件若发布 ghcr OCI 制品，优先用 OCI（Argo CD chart：`oci://ghcr.io/argoproj/argo-helm/argo-cd:10.18.2`）
2. 单文件可用 GitHub Contents/Blobs API（api.github.com 可达）经 `Accept: application/vnd.github.raw` 直接取 raw 内容
3. 大文件（>1MB）用 git blobs API 的 sha 直接拉取，绕开 contents API 的 1MB 限制

**注意**：未修改 hosts / DNS（属系统配置变更，需架构负责人批准）；若长期实验建议专项申请。

---

## 2026-11-21 · Grafana CrashLoopBackOff（OOMKilled 137）

**现象**

kube-prometheus-stack 安装后 Grafana Pod 反复重启，`READY 2/3`，readiness 探针 connection refused。

**排查**

- `kubectl describe pod`：`Last State: Terminated, Reason: OOMKilled, Exit Code 137`，limits memory 256Mi。
- 日志本身无报错，Grafana 启动到 provision dashboards 阶段即被内核杀。

**根因**

Grafana 13（13.3.1-distroless）加载 25 个 provision 仪表盘 + 内置插件初始化，实测稳定占用 ~440Mi，初版 values 给的 256Mi limit 过小。

**解决**

`components/02-monitoring/kube-prometheus-stack-values.yaml` 中 grafana limits.memory 256Mi → **512Mi**（requests 128Mi → 256Mi），`helm upgrade` 后 3/3 Running。

**经验**：开源组件的"官方默认 resources"不可直接照抄到实验环境；应小步给值、以 OOMKilled/Throttle 实测为准回调——也印证了 AGENTS.md §4"结合实际运行情况调整"。


---

## 2026-11-21 · pg_dump 版本不匹配（server 18.7 vs client 17.5）

**现象**：`pg_dump: aborting because of server version mismatch`

**根因**：CloudNativePG 1.30 默认镜像已是 PostgreSQL 18.7，备份 Pod 用 17.5 镜像；pg_dump 客户端大版本必须 ≥ 服务端。

**解决**：备份/工具容器镜像与实例镜像**逐字一致**（`ghcr.io/cloudnative-pg/postgresql:18.7-system-trixie`，从运行中实例 `spec.containers[*].image` 取），不要猜 tag（`18.7` 这种短 tag 不存在）。

---

## 2026-11-21 · 裸 Pod kubectl apply 改 image 不生效

**现象**：apply 修改了 Pod 的 image 字段，容器仍在跑旧镜像。

**根因**：裸 Pod 没有控制器，kubelet 对 Pod spec 的镜像变更不做滚动重建（与 Deployment 不同）。

**解决**：`kubectl delete pod` 后重新 apply（有 PVC 挂载的场景数据不丢）。

---

## 2026-11-21 · CloudNativePG 1.30 无 `-superuser` secret / peer 认证

**现象**：`kubectl get secret pg-lab-superuser` NotFound；`psql -U app` 本地 socket 报 `Peer authentication failed`。

**根因**：CNPG 实例内本地访问只放行 postgres 操作系统用户经 peer 映射到 postgres 角色；`-superuser` secret 按需创建，未配置外部访问时不生成。

**解决（实验访问模型）**：实例内运维操作一律 `psql -U postgres`（peer 免密）；应用访问走网络 + `<cluster>-app` secret（密码认证）；需要应用用户拥有测试表时，用 postgres 建表后 `ALTER TABLE ... OWNER TO app`。


---

## 2026-11-21 · keycloakx chart 启动崩溃：`kc.sh` 打印帮助即退出

**现象**：Keycloak Pod CrashLoopBackOff，日志是 kc.sh 的 usage 帮助。

**根因**：chart 默认 `command: []`（values 注释 "Overrides the default entrypoint"），镜像 ENTRYPOINT 为 `/opt/keycloak/bin/kc.sh` 且无参数 → 打印帮助退出。chart 不会自动生成 `start` 命令。

**解决**：values 显式给出：
```yaml
command: ["/opt/keycloak/bin/kc.sh", "start"]
```
KC_DB* 等由 chart 以环境变量注入，start 模式自动读取。

**附带发现**：helm upgrade 更新 StatefulSet 模板后旧 Pod 可能不滚动（本次需手动 `kubectl delete pod` 强制重建）。

---

## 2026-11-21 · KC_HOSTNAME 与 JWKS 访问地址不同源导致验签失败

**现象**：API 验证 token 报 `invalid token: PyJWKClientConnectionError`。

**根因**：KC_HOSTNAME 设为 `http://keycloak.identity:8080`，但集群内不存在该 Service（真实服务名 `keycloak-keycloakx-http`，端口 80）。

**弯路**：ExternalName Service 别名——**kube-proxy 对 ExternalName 只做 DNS CNAME，不做端口映射**，client 连 `别名:8080` 实际打到目标 Service 的 8080（未监听）→ 仍不通。

**解决（D-18 双 Service 模式）**：再建一个 ClusterIP Service（selector 指向同一 Pod，`8080→8080`），集群内统一用 `keycloak.identity:8080`，与 KC_HOSTNAME/iss 同源。

---

## 2026-11-21 · Keycloak 26 password grant：`Account is not fully set up`

**现象**：`grant_type=password` 返回 `invalid_grant / Account is not fully set up`。

**根因**：KC26 对密码流校验用户 profile 完整性，**email + emailVerified + firstName + lastName 缺一即拒绝**。client_credentials（服务账号）不受影响——这解释了为何 SA token 一开始就能拿。

**解决**：kcadm 补齐用户属性：
```bash
kcadm update users/<id> -r lab -s email=viewer@lab.local -s emailVerified=true -s firstName=View -s lastName=Er
```

---

## 2026-11-21 · FastAPI 依赖注入 422：`HTTPAuthorizationCredentials | None` 被当作 body

**现象**：带正确 Bearer token 请求返回 422 `{"loc":["body"],"msg":"Field required"}`。

**根因**：依赖函数签名 `def verify_token(creds: HTTPAuthorizationCredentials | None = None)`——FastAPI 不会把裸类型注解识别为 security scheme，union + 默认 None 使它被当作普通请求体字段。

**解决**：显式挂 `Depends(bearer)`：
```python
def verify_token(creds: HTTPAuthorizationCredentials = Depends(bearer)):
```
**教训**：自建镜像先本地 `docker run -p 8000:8000` 冒烟再导入集群，能省一轮镜像重建。
