# Architecture — 整体架构与组件关系

> 随阶段推进逐步更新。当前包含阶段 01（基础环境）、02（监控）、03（GitOps）。

## 现状（截至阶段 03）

```
Windows 11 (32GB RAM)
└── WSL2  VM（Docker Desktop，内存上限 ≈15.4GiB，符合 16GB 预算）
    └── Docker Engine 29.6.1
        └── k3d 集群 "lab"（容器化 k3s v1.37.2，单 Server 节点，可调度）
            ├── flannel（CNI）/ CoreDNS / ServiceLB / local-path-provisioner / metrics-server
            ├── Namespace demo：nginx + PVC（阶段 01，kubectl 直管）
            ├── Namespace monitoring：kube-prometheus-stack 93.6.1（阶段 02）
            └── Namespace argocd：Argo CD v3.6.2（阶段 03，GitOps 控制面）
                └── Application gitops-demo → 同步 Git 仓库 gitops/workloads/gitops-demo
                    └── Namespace gitops-demo：nginx（2 副本，当前版本 v1.0.0）
```

## GitOps 数据流

```
本仓库 GitHub (唯一事实来源)
  gitops/workloads/<chart>/values.yaml
        │  Argo CD 3min 轮询（argocd-repo-server 拉取）
        ▼
argocd-application-controller ──diff/sync──▶ 集群实际状态
        │ OutOfSync 时只报告（selfHeal=false）
        ▼
kubectl / CLI 手动 sync 收敛；回滚经 git revert 到 Git
```

- 现存 demo / monitoring 等 kubectl 直管资源**不在** Argo CD 管理面内（安全边界）
- 监控栈（阶段 02）仍由 helm 直管；后续阶段可评估迁入 Argo CD

## 平面划分（目标架构演进中）

| 平面 | 当前 | 后续阶段 |
|---|---|---|
| 控制平面 | k3s 单 Server + Argo CD GitOps | 多 Server etcd HA |
| 执行平面 | 同节点 kubelet + 业务 Pod | Agent 节点池、资源配额 |
| 可观测平面 | Prometheus + Grafana + Alertmanager | Loki/Tempo、告警通知渠道 |
| GitOps 平面 | Argo CD 单实例，Application 逐个注册 | ApplicationSet 批量管理、多集群 |
| 数据平面 | — | PostgreSQL / Redis / MQ（各自 Owner，经 Argo CD 发布） |
| 模型平面 | — | 外部 API / Mock Model |

## 端口与访问

- kubectl API：`https://127.0.0.1:5347`（troubleshooting.md）
- Grafana :3000 / Prometheus :9090 / Alertmanager :9093（port-forward，阶段 02）
- Argo CD UI：`kubectl -n argocd port-forward svc/argocd-server 8080:443` → https://localhost:8080
- Service CIDR：10.43.0.0/16
