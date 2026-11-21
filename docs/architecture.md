# Architecture — 整体架构与组件关系

> 随阶段推进逐步更新。当前包含阶段 01（基础环境）与阶段 02（监控）。

## 现状（截至阶段 02）

```
Windows 11 (32GB RAM)
└── WSL2  VM（Docker Desktop，内存上限 ≈15.4GiB，符合 16GB 预算）
    └── Docker Engine 29.6.1
        └── k3d 集群 "lab"（容器化 k3s v1.37.2，单 Server 节点，可调度）
            ├── flannel（CNI，VXLAN：Pod CIDR 10.42.0.0/16）
            ├── CoreDNS（集群内 DNS 发现）
            ├── ServiceLB / klipper-lb（LoadBalancer 模拟）
            ├── local-path-provisioner（默认 SC：local-path，WaitForFirstConsumer）
            ├── metrics-server（HPA/Top 指标来源，k3s 自带）
            ├── Namespace demo：Deployment/nginx（2 副本）+ ClusterIP Service + PVC
            └── Namespace monitoring（kube-prometheus-stack 93.6.1）
                ├── prometheus-operator（CRD：Prometheus/Alertmanager/ServiceMonitor/PrometheusRule）
                ├── prometheus（retention 3d，emptyDir，13 个抓取目标）
                ├── alertmanager（单副本，默认路由）
                ├── grafana（25 个 provision 仪表盘，数据源=Prometheus/Alertmanager）
                ├── kube-state-metrics（K8s 对象状态指标）
                └── node-exporter（节点指标，k3d 容器视角 /proc）
```

## 数据流（监控链路）

```
cAdvisor/kubelet ──scrape──▶ Prometheus ──规则求值──▶ firing ──推送──▶ Alertmanager
                                   │
                                   └──query──▶ Grafana（仪表盘） / kubectl top（metrics-server 链路独立）
```

- 采集：Operator 按 ServiceMonitor/PodMonitor 生成抓取配置，30s 间隔
- 告警：PrometheusRule（如 LabLoadTestCpuHigh）→ Prometheus 求值 → Alertmanager 路由
- 展示：Grafana 经内置 datasource 查询 Prometheus；`kubectl top` 走 metrics-server 聚合链路与 Prometheus 无关

## 平面划分（目标架构演进中）

| 平面 | 当前 | 后续阶段 |
|---|---|---|
| 控制平面 | k3s 单 Server（API Server / Scheduler / Controller Manager，SQLite 存储） | 多 Server etcd HA |
| 执行平面 | 同节点 kubelet + 业务 Pod | Agent 节点池、资源配额 |
| 可观测平面 | Prometheus + Grafana + Alertmanager + metrics-server（本阶段） | Loki/Tempo 日志与链路、告警通知渠道 |
| 数据平面 | — | PostgreSQL / Redis / MQ（各自 Owner） |
| 模型平面 | — | 外部 API / Mock Model |

## 端口与访问

- kubectl 经 kubeconfig 访问 API Server：`https://127.0.0.1:5347`（k3d 经 serverlb 发布 `0.0.0.0:5347->6443`；因 WSL mirrored 网络修正，见 troubleshooting.md）
- Web UI 均经 `kubectl port-forward` 访问（不映射宿主机端口）：Grafana :3000、Prometheus :9090、Alertmanager :9093（命令见 experiments/02-monitoring.md §8）
- 宿主机 80/443/8080/9090 仍空闲，留待 Ingress / 后续阶段
- Service CIDR：10.43.0.0/16（demo/nginx = 10.43.155.10）
