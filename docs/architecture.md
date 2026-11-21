# Architecture — 整体架构与组件关系

> 随阶段推进逐步更新。当前包含阶段 01–04。

## 现状（截至阶段 04）

```
Windows 11 (32GB RAM)
└── WSL2 VM（Docker Desktop，≈15.4GiB 上限）
    └── Docker Engine 29.6.1（registry mirror: docker.m.daocloud.io）
        └── k3d 集群 "lab"（k3s v1.37.2，单 Server）
            ├── 集群基础：flannel / CoreDNS / ServiceLB / local-path / metrics-server
            │            + Gateway API CRD（standard channel 1.6.301，k3s 自带）
            ├── ns demo：nginx + PVC（kubectl 直管）
            ├── ns monitoring：kube-prometheus-stack（helm 直管）
            ├── ns argocd：Argo CD（GitOps 控制面）
            │   └── Application gitops-demo → ns gitops-demo（nginx v1.0.0）
            ├── ns envoy-gateway-system：Envoy Gateway v1.10.0
            │   ├── envoy-gateway（Gateway Controller：CR→xDS 翻译）
            │   └── envoy-gateway-lab-lab-gateway（Envoy Data Plane：L7 代理）
            │       └── LoadBalancer Service :80
            ├── ns gateway-lab：Gateway lab-gateway + HTTPRoute
            │   └── backend-v1×3 / backend-v2 / slow-backend
            ├── ns cnpg-system：CloudNativePG operator v1.30.2（数据平面 Owner）
            ├── ns database：Cluster pg-lab（PG 18.7，主备异步流复制，PVC 1Gi×2）
            │   ├── 服务 pg-lab-rw / -ro / -r；PodMonitor 接入 Prometheus
            │   ├── keycloak 库（身份平面的数据库依赖）
            │   └── backup-pod（pg_dump 逻辑备份 → backup-data PVC）
            ├── ns cache：Valkey 9.2（Deployment+RDB PVC+密码 Secret）
            └── ns identity：Keycloak 26.8.1（StatefulSet，pg-lab 后端）
                ├── svc keycloak-keycloakx-http:80（宿主 port-forward）
                ├── svc keycloak:8080（集群内别名，与 iss 同源，D-18）
                └── lab-api（FastAPI 受保护 API，本地构建镜像）
```

## 依赖关系（数据流）

```
API 客户端 ──token──▶ Keycloak(身份平面) ──JDBC──▶ pg-lab-rw(数据平面)
    │                                                ▲
    └──Bearer JWT──▶ lab-api ──JWKS 验签──▶ Keycloak ┘
lab-api 缓存场景（后续 Worker 用）：──▶ Valkey:6379（cache 平面，可选加速）
```

## 数据平面现状（各组件自带 Owner）

| 组件 | Owner | 高可用 | 备份路径 | 状态 |
|---|---|---|---|---|
| PostgreSQL 18.7 | CloudNativePG Operator | 2 实例异步流复制（实测 failover RTO 14~138s，RPO=0） | 逻辑 pg_dump→PVC（物理备份需对象存储，未配置） | Healthy |

## 流量路径（南北向）

```
外部 HTTP ──port-forward──▶ Envoy Data Plane(:80)
                              │ HTTPRoute 规则：路径匹配/重写/加权/超时
                              ▼
                          backend-v1/v2（ClusterIP）
```

- 入口能力均由 Gateway API CR 声明（图纸），Envoy Gateway Controller 翻译为 Envoy 配置（xDS 热更新）
- 尚无 TLS、无生产 LB（k3s ServiceLB 模拟）、无限流/鉴权策略（后续阶段可加 BackendTrafficPolicy/SecurityPolicy）

## 平面划分

| 平面 | 当前 | 后续 |
|---|---|---|
| 控制平面 | k3s 单 Server | 多 Server HA |
| 执行平面 | 单节点 kubelet + 业务 Pod | 节点池、配额 |
| 流量入口 | Envoy Gateway + Gateway API | TLS、多网关、策略（限流/鉴权） |
| 可观测 | Prometheus + Grafana + Alertmanager | Loki/Tempo、通知渠道 |
| GitOps | Argo CD（应用逐个注册） | ApplicationSet、组件迁入 GitOps |
| 数据平面 | — | PostgreSQL / Redis / MQ（各自 Owner） |
| 模型平面 | — | 外部 API / Mock Model |

## 端口与访问

- kubectl API：https://127.0.0.1:5347
- Grafana :3000 / Prometheus :9090 / Alertmanager :9093 / Argo CD :8080（https）
- Envoy Gateway：`kubectl -n envoy-gateway-system port-forward svc/envoy-gateway-lab-lab-gateway-8e66c156 18081:80`
- 宿主机 80/443 仍空闲；C: 剩 19.8GB（关注）
