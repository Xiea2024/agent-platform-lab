# Progress — Kubernetes Native AI Agent Infrastructure Lab

> 记录各阶段完成情况。每阶段须通过 §10 Definition of Done 验收后才标记完成。

## 阶段总览

| 阶段 | 内容 | 状态 |
|------|------|------|
| 01 | Kubernetes 基础环境（k3d / k3s） | ✅ 已完成，待最终验收 |
| 02 | Metrics + Prometheus + Grafana | ✅ 已完成，待最终验收 |
| 03 | Argo CD GitOps | ✅ 已完成，待最终验收 |
| 04 | Envoy Gateway + Gateway API | ✅ 已完成，待最终验收 |
| 05+ | 待规划（建议：数据平面 PostgreSQL，先做磁盘清理评估） | 未开始 |

## 阶段 04 — Envoy Gateway + Gateway API

### Preflight / Plan（2026-11-21，获批）

- GatewayClass 无（干净起点）；Gateway API standard CRD 已由 k3s 自带（1.6.301）；Envoy Gateway v1.10.0 核实

### Deploy（排错密集，全部解决）

- chart 经 daocloud 镜像站 OCI 拉取；`crds.enabled=false` 避开 experimental/standard channel 冲突（VAP 保护机制）
- 手工补齐 8 个 gateway.envoyproxy.io CRD（2 个大 CRD 用 server-side apply 绕开 256KB 注解限制）
- 手工创建 GatewayClass eg → controller 拉起 Envoy data plane（镜像拉取 EOF 为网络抖动，重试成功）

### Experiment（六项全部通过）

| 实验 | 结果 |
|---|---|
| 路由 | /v1、/v2 经 URLRewrite 正确分发（排错：v1.4+ replacePrefixMatch 为字符串字段） |
| 负载均衡 | 9 次请求分布 3 个 Pod（Envoy 加权轮询） |
| 权重切流 | 80/20 → 50 次实测 41:9≈82:18；0/100 全量切 v2 ✓ |
| 无健康后端 | 独占规则 503；加权规则自动跳过空池（均 200）；恢复副本自愈 ✓ |
| 超时 | /slow 2.006s 精确返回 504（backendRequest: 2s）✓ |
| 回滚 | 重应用声明文件，权重回 100/0，流量全回 v1 ✓ |

### Review（资源实测）

- envoy controller 46Mi + data plane 43Mi + 后端 50Mi；VM used 4567MiB（28% 预算）
- **C: 剩 19.8GB，标记为后续阶段首要约束**

### Definition of Done 核对

- [x] 部署可复现（含 6 步排错记录）；核心功能六项验证
- [x] Controller/Data Plane 关系图解（experiments/04 §1）
- [x] 资源占用记录；异常记录（channel 冲突、注解超限、镜像 EOF）
- [x] 生产差异（§4）；清理步骤（§5）

## 阶段 01–03 归档

- 01：`experiments/01-kubernetes-baseline.md`；02：`experiments/02-monitoring.md`；03：`experiments/03-gitops-argocd.md`
