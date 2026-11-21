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
