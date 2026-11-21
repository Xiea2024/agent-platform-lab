# Progress — Kubernetes Native AI Agent Infrastructure Lab

> 记录各阶段完成情况。每阶段须通过 §10 Definition of Done 验收后才标记完成。

## 阶段总览

| 阶段 | 内容 | 状态 |
|------|------|------|
| 01 | Kubernetes 基础环境（k3d / kubectl / Helm、核心资源与网络验证） | ✅ 已完成，待最终验收 |
| 02 | Metrics + Prometheus + Grafana（kube-prometheus-stack 93.6.1） | ✅ 已完成，待最终验收 |
| 03+ | 待规划 | 未开始 |

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
