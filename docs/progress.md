# Progress — Kubernetes Native AI Agent Infrastructure Lab

> 记录各阶段完成情况。每阶段须通过 §10 Definition of Done 验收后才标记完成。

## 阶段总览

| 阶段 | 内容 | 状态 |
|------|------|------|
| 01 | Kubernetes 基础环境（k3d / kubectl / Helm、核心资源与网络验证） | ✅ 已完成，待最终验收 |
| 02 | Metrics + Prometheus + Grafana（kube-prometheus-stack 93.6.1） | ✅ 已完成，待最终验收 |
| 03 | Argo CD GitOps（v3.6.2，同步/Drift/回滚实验） | ✅ 已完成，待最终验收 |
| 04+ | 待规划 | 未开始 |

## 阶段 03 — Argo CD（GitOps）

### Preflight / Plan（2026-11-21，获批）

- 集群与余量验证 OK；Argo CD v3.6.2（2026-11-18 发布）核实

### Deploy

- **计划偏差**：argo-helm chart 仓库（argoproj.github.io）被本机 DNS 拦截 → 改经 `oci://ghcr.io/argoproj/argo-helm/argo-cd:10.18.2`（appVersion 精确对应 v3.6.2）；network 细节见 troubleshooting.md
- argocd CLI（winget argoproj.argocd 3.6.2）；values 最小化（禁 dex/notifications）
- `applicationSet.enabled=false` 未生效（chart 10.x key 变化），接受现状并记录
- gitops/ 目录结构：bootstrap / apps / workloads

### Verify / Experiment（全部通过）

- 首次 Sync ~20s → Synced/Healthy；2 副本 + v1.0.0 ✓
- Git 变更自动同步：push 后 ~2min 收敛为 3 副本 + v1.1.0，零 kubectl 操作 ✓
- Drift：scale 到 5 → 40s 内 OutOfSync（selfHeal 关闭不纠正）→ 手动 sync 收敛回 3 ✓
- 回滚：`argocd app rollback` 被 auto-sync 拒绝（FailedPrecondition，设计如此）→ 改 git revert → ~2min 自动收敛回 2 副本 + v1.0.0 ✓

### Review（资源实测）

- argocd ≈184Mi；VM used 4160MiB/15782MiB（三阶段合计 ~26% 预算）；C: 剩 22.6GB

### Definition of Done 核对

- [x] 部署配置可复现（values + OCI 命令）
- [x] 核心功能验证（Sync/Drift/回滚/values 管理）
- [x] 安全边界（无 finalizer、prune=false、不接管现存服务、无 PVC）
- [x] 资源占用记录；异常记录（DNS 拦截、applicationSet 偏差）
- [x] 生产差异说明（experiments/03 §7）；清理步骤（§8）

### 待办

- [ ] 架构负责人最终验收（阶段 01–03）
- [ ] 建议 Git Commit：experiments/03、docs 更新

## 阶段 02 — Metrics + Prometheus + Grafana

### Preflight（2026-11-21）

- 阶段 01 验证：Node Ready、demo 负载正常、`kubectl top` 可用（metrics-server 为 k3s 自带）
- 余量：VM used 1939MiB/15782MiB，C: 剩 27.9GB → 充足
- 版本核实：kube-prometheus-stack **93.6.1**（GitHub Releases 页面确认）

### Deploy（经批准）

- helm repo add + install；GitHub Releases tgz 下载两次超时 → 改经 **ghcr OCI** 成功
- values 最小化：禁用 4 个 k3s 无独立 endpoint 的控制面抓取 + 对应默认规则；retention 3d；emptyDir；全组件 requests/limits
- 自定义告警规则 `LabLoadTestCpuHigh`（CPU>0.5 核持续 1m）+ 负载 Pod `cpu-loader`（busybox yes>/dev/null，限 1 核）
- 排错：Grafana 13 OOMKilled(137) → limits 256Mi→512Mi 后 3/3 Running（troubleshooting.md）

### Verify（全部通过）

- 6 Pod 全部 Running；Prometheus targets **13/13 up**；`kubectl top` 正常
- Grafana：Prometheus/Alertmanager 数据源 provision 完成，**25 个默认仪表盘**
- 告警链路：规则加载 ✓

### Experiment（CPU 负载全生命周期）

| 阶段 | 证据 |
|---|---|
| 加压 | cpu-loader 顶满 limit（top 实测 1001m），节点 CPU 1239m |
| firing | Prometheus 规则状态 firing；Alertmanager 收到 active 告警 |
| 恢复 | 删 Pod 后 2~3min：序列消失 → 规则 inactive → Alertmanager 仅剩 Watchdog；节点 CPU 回落 151m |
| 结论 | `for:1m`+rate 窗口带来 2~3min 滞后属 Prometheus 模型特性 |

### Review（资源实测）

- monitoring ≈810Mi；k3d-server 容器 2.89GiB；VM used 3501MiB/15782MiB；C: 剩 24.7GB
- 详见 `experiments/02-monitoring.md`、`docs/resource-budget.md`

### Definition of Done 核对

- [x] 部署配置可复现（values 文件 + 安装命令已记录）
- [x] 核心功能验证（targets/仪表盘/数据源/top）
- [x] K8s 资源与依赖关系清楚（architecture.md 已更新监控平面）
- [x] 实际资源占用已记录
- [x] 异常场景记录（GitHub 下载超时、Grafana OOM）
- [x] 生产与实验区别已说明（实验文档 §6）
- [x] 项目文档已更新
- [x] 清理及恢复步骤已给出

### 待办

- [ ] 架构负责人最终验收（阶段 01 + 02）
- [ ] 建议 Git Commit：docs/、components/（01、02）、experiments/

## 阶段 01 — Kubernetes 基础环境

（保持上版记录，见 git 历史或上文归档）

- 状态：✅ 已完成，待最终验收；详见 `experiments/01-kubernetes-baseline.md`
