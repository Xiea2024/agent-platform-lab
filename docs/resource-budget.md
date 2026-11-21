# Resource Budget — 资源预算与实际占用

> 预算依据 AGENTS.md §4：正常实验 WSL2/Docker/K8s 内存 ≤ 16GB；不默认启用 HA。

## 预算分配（实验运行期）

| 项目 | 预算 |
|---|---|
| Docker Desktop VM（WSL2）总上限 | ≈15.4 GiB（现状默认值，已符合 16GB 要求） |
| 阶段 01 k3d 集群 | ≤ 3 GB |
| 预留（后续数据库/缓存/消息组件） | ≈ 8 GB |
| 宿主 Windows + 日常应用 | ≈ 14 GB |

## 阶段 01 实测（2026-11-21）

| 指标 | 实测 | 占预算 |
|---|---|---|
| k3d-lab-server-0 | 720.8 MiB | k3d 预算的 24% |
| k3d-lab-serverlb + tools | 24.8 MiB | — |
| WSL VM 整体 used | 2167 MiB / 15782 MiB | 13.7% |
| C: 磁盘 | 本次增量 ≈1.7 GB（剩余 27.9 GB） | — |

**结论**：阶段 01 占用远低于预算，后续阶段无需调整 .wslconfig / Docker Desktop 内存配置。

## 历史记录

- 2026-11-21：阶段 01 基线测量（上表）。原始记录见 `experiments/01-kubernetes-baseline.md` §4。


## 阶段 02 实测（2026-11-21，负载清理后）

| 指标 | 实测 | 对比阶段 01 基线 |
|---|---|---|
| monitoring Pod 合计 | ≈810Mi（grafana 416 / prometheus 317 / 其余 <30） | — |
| k3d-lab-server-0 容器 | 2.89 GiB | 759Mi → +2.1GB |
| WSL VM 整体 used | 3501 MiB / 15782 MiB | 1939Mi → +1.5GB |
| C: 磁盘 | 24.7 GB 剩余（本阶段增量 ≈3.2GB） | 27.9GB |

**结论**：两阶段合计占用 VM 内存 ~3.5GB / 16GB 预算，后续数据类组件（PostgreSQL/Redis/MQ）仍有充足余量；C: 磁盘需留意（剩 24.7GB，单个大镜像即可达 1GB+）。


## 阶段 03 实测（2026-11-21）

| 指标 | 实测 | 对比阶段 02 末 |
|---|---|---|
| argocd Pod 合计 | ≈184Mi（controller 99 / server 29 / repo-server 28 / applicationset 23 / redis 5） | — |
| k3d-lab-server-0 容器 | 3.91 GiB | 2.92GiB → +1GB |
| WSL VM 整体 used | 4160 MiB / 15782 MiB | 3503Mi → +657Mi |
| C: 磁盘 | 22.6 GB 剩余（本阶段增量 ≈2.1GB） | 24.3GB |

**结论**：三阶段合计占用 VM 内存 ~4.2GB / 16GB 预算（26%）；C: 磁盘剩余 22.6GB 仍是主要约束。


## 阶段 04 实测（2026-11-21）

| 指标 | 实测 | 对比阶段 03 末 |
|---|---|---|
| envoy-gateway controller + data plane | 46 + 43 Mi | — |
| gateway-lab 后端（5 Pod） | ≈50Mi | — |
| k3d-lab-server-0 容器 | 4.54 GiB | 3.91GiB → +0.6GB |
| WSL VM 整体 used | 4567 MiB / 15782 MiB（预算 28%） | 4160Mi → +0.4GB |
| C: 磁盘 | **19.8 GB 剩余**（本阶段 -0.8GB） | 22.6GB |

**结论**：内存余量充足（71%），但 **C: 磁盘跌破 20GB** 成为首要约束——后续大镜像组件（数据库/MQ）每阶段预计 1-3GB，需在阶段 05 前确认磁盘清理方案（docker system prune 候选，需批准）。


## 阶段 05 实测（2026-11-21）

| 指标 | 实测 | 对比阶段 04 末 |
|---|---|---|
| pg 实例 ×2 + operator | 62 + 53 + 33 Mi | — |
| k3d-lab-server-0 容器 | 5.47 GiB | 4.54GiB → +0.9GB |
| WSL VM 整体 used | 5082 MiB / 15782 MiB（**31%**） | 4567Mi → +0.5GB |
| PVC | 3 × 1Gi（2 实例 + 1 备份） | — |
| C: 磁盘 | 96.7 GB ✓ | 19.8GB → 已解除 |

**结论**：五阶段合计 VM 内存 31%（余量 ~10.7GB），数据平面再添 Redis/MQ 无压力；C: 磁盘充裕。


## 阶段 06 实测（2026-11-21）

| 指标 | 实测 |
|---|---|
| Valkey | 4Mi |
| Keycloak | 701Mi（JVM，本阶段最大单体） |
| lab-api | 37Mi |
| WSL VM used | 5795 MiB / 15782 MiB（**36%**，余量 ~9.6GB） |
| C: 磁盘 | 95.7GB ✓ |

**结论**：六阶段合计 VM 36%。Keycloak 是内存消耗第一名（比 Prometheus+Grafana 合计还高），若后续资源紧张，优先评估 Keycloak 单副本裁剪（KC_HEAP）而非动数据面。
