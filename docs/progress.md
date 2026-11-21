# Progress — Kubernetes Native AI Agent Infrastructure Lab

> 记录各阶段完成情况。每阶段须通过 §10 Definition of Done 验收后才标记完成。

## 阶段总览

| 阶段 | 内容 | 状态 |
|------|------|------|
| 01 | Kubernetes 基础环境（k3d / k3s） | ✅ 已完成，待最终验收 |
| 02 | Metrics + Prometheus + Grafana | ✅ 已完成，待最终验收 |
| 03 | Argo CD GitOps | ✅ 已完成，待最终验收 |
| 04 | Envoy Gateway + Gateway API | ✅ 已完成，待最终验收 |
| 05 | cert-manager 评估 + CloudNativePG | ✅ 已完成，待最终验收 |
| 06 | Valkey + Keycloak + 受保护 API | ✅ 已完成，待最终验收 |
| 07+ | 待规划（建议：MQ 或 Agent 执行平面首个 Worker） | 未开始 |

## 阶段 06 — Valkey + Keycloak

### Preflight / Plan（2026-11-21，获批 6A+6B）

- 版本：Valkey 9.2.0 / Keycloak 26.8.1（keycloakx chart 7.4.0）
- cert-manager 仍不需要（两组件均内置证书能力）

### 6A Valkey（验收通过）

- TTL：20s 递减精确、过期即删 ✓
- 持久化三场景：优雅删 Pod 零丢失（停机自动 SAVE）/ SAVE 快照恢复 / **DEBUG SEGFAULT 崩溃丢失脏数据**（等价断电，RPO=快照窗口）✓

### 6B Keycloak + 受保护 API（验收通过）

- Realm lab / client lab-api / role api-user / tester(viewer 对照组) / SA 绑定 ✓
- JWT claims 验证（iss/azp/roles/exp）；password grant 排错（KC26 profile 完整性要求）✓
- **RBAC 矩阵：public 200 / 无 token 401 / 无角色 403 / 有角色 200×2** ✓
- 关键认知成文：**JWT 认证 ≠ 租户隔离**（experiments/06 §2.5，含 RLS 等四层隔离路径）

### Review（资源实测）

- Valkey 4Mi / Keycloak 701Mi / API 37Mi；VM used 5795MiB（36%）；C: 95.7GB
- 依赖链：lab-api → keycloak.identity(JWKS) → pg-lab-rw(PG)

## 阶段 01–05 归档

- 01 `experiments/01-kubernetes-baseline.md` / 02 `02-monitoring.md` / 03 `03-gitops-argocd.md` / 04 `04-gateway-api.md` / 05 `05-postgres-cnpg.md`
