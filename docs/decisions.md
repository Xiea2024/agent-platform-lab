# Decisions — 技术选型与架构取舍

## 2026-11-21 · 阶段 01：Kubernetes 基础环境

### D-01 本地 Kubernetes 发行版：k3s（经 k3d 运行）

- **选择**：k3d v5.9.0 + k3s v1.37.2-k3s1，单 Server 节点
- **理由**：AGENTS.md 明确优先 k3d；单节点满足实验需求且内存占用最小；k3d 在 Docker Desktop（WSL2 后端）内运行，复用现有 16GB VM 预算，无需额外虚拟机
- **替代方案**：kind（同为容器内 K8s，但缺少内置 local-path Provisioner 与 ServiceLB 的完整体验）、minikube、Kubeadm + VM（资源开销大）
- **生产差异**：生产应为多 Server（嵌入式 etcd 高可用）、专用 CNI/CSI、禁用默认组件并由平台团队统一管理

### D-02 本阶段禁用 Traefik

- **理由**：阶段 01 仅需验证 Pod/Deployment/Service/Namespace/PVC/集群网络，无 Ingress 需求；禁用可减少约 100MB 占用
- **后续**：Ingress/Gateway 阶段再启用（或改用 Gateway API，见 k3s 已内置 gateway-api CRD）

### D-03 版本固定（不使用 latest）

| 组件 | 版本 | 核实来源 |
|---|---|---|
| k3d | v5.9.0 | GitHub Releases（2026-06-02） |
| k3s | v1.37.2+k3s1 | GitHub Releases（2026-11-03） |
| Helm | v4.3.2 | GitHub Releases（2026-11-13） |
| kubectl | v1.36.1（Docker Desktop 自带） | 与 server v1.37 差 1 个 minor，符合兼容性策略 |

- **注意**：Helm 主版本已升至 v4（本实验安装 v4.3.2），与 v3 的命令语法基本兼容；后续 Chart 安装时留意 v4 行为差异

### D-04 安装方式：winget（Windows 用户级）

- k3d.k3d 与 Helm.Helm 均有官方 winget 包且版本与 pinned 一致；安装于用户目录，不污染系统目录


---

## 2026-11-21 · 阶段 02：Metrics + Prometheus + Grafana

### D-05 监控栈选型：kube-prometheus-stack（Prometheus Operator 路线）

- **选择**：chart 93.6.1，保留 Prometheus / Grafana / Alertmanager / kube-state-metrics / node-exporter；禁用 kubeEtcd / kubeScheduler / kubeControllerManager / kubeProxy 抓取（k3s 内嵌，无独立 endpoint）
- **理由**：AGENTS.md §3.5 优先成熟开源基础设施；Operator + ServiceMonitor 的声明式采集模型与后续 GitOps 阶段契合；单 chart 统一版本管理
- **替代方案**：纯手工 Prometheus 部署（可控但重复维护）、VictoriaMetrics（更省资源，生态兼容 Prometheus）、Grafana Alloy/Agent 采集链路
- **为什么不选 VictoriaMetrics**：实验目标之一是理解 Prometheus 原生模型（PromQL/规则/告警生命周期），VM 可作后续对比实验

### D-06 chart 获取路径：ghcr OCI 优先于 GitHub Releases

- 本机 github.com release asset 下载超时但 ghcr.io 通畅；prometheus-community chart 两种形态同步发布，固定 `--version 93.6.1` 语义等价

### D-07 数据保留与存储策略

- Prometheus `retention 3d` + emptyDir；Grafana / Alertmanager 无持久化
- **理由**：实验环境数据可弃，emptyDir 免除 local-path 的容量管理；retention 限制磁盘上限（预计 <1GB）
- **生产差异**：PVC + 更长保留 + 对象存储归档，已记录于实验文档 §6
