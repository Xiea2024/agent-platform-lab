# Progress — Kubernetes Native AI Agent Infrastructure Lab

> 记录各阶段完成情况。每阶段须通过 §10 Definition of Done 验收后才标记完成。

## 阶段总览

| 阶段 | 内容 | 状态 |
|------|------|------|
| 01 | Kubernetes 基础环境（k3d / k3s） | ✅ 已完成，待最终验收 |
| 02 | Metrics + Prometheus + Grafana | ✅ 已完成，待最终验收 |
| 03 | Argo CD GitOps | ✅ 已完成，待最终验收 |
| 04 | Envoy Gateway + Gateway API | ✅ 已完成，待最终验收 |
| 05 | cert-manager 评估 + CloudNativePG（HA/备份/RPO-RTO） | ✅ 已完成，待最终验收 |
| 06+ | 待规划（建议：Redis 或 MQ；磁盘已解除预警） | 未开始 |

## 阶段 05 — cert-manager 评估 + CloudNativePG

### Preflight / Plan（2026-11-21，分两批获批）

- cert-manager 不存在且 CloudNativePG 无依赖 → **不安装**（避免重复组件）✓
- CloudNativePG v1.30.2（chart 0.29.2，ghcr OCI）；磁盘 95.2GB ✓

### Deploy / Verify

- operator + pg-lab（2 实例，PG 18.7，PVC 1Gi×2，异步流复制，PodMonitor 接入 Prometheus）
- 服务 -rw/-ro/-r；数据 100 行主备一致；`cnpg_pg_replication_lag=0`
- 排错：镜像 tag 需与实例一致（18.7-system-trixie）、裸 Pod 改 image 须重建、pg_dump 版本匹配、1.30 无 superuser secret（用 app 用户 + 属主转让）

### Experiment

| 实验 | 结果 |
|---|---|
| 物理备份路径 | `Backup` CR failed（no backup section）→ 需对象存储，证据记录 |
| 逻辑备份闭环 | pg_dump → PVC → pg_restore → 校验 100 行 ✓ |
| Pod 重建（非破坏性） | **实测为自动 failover**：备升主、原主重建为备；RTO≈14s，**RPO=0** |
| 受控主故障（二次 failover，单独获批） | RTO=**138s**（收敛期故障显著变慢），**RPO=0**（时间线铁证）；拓扑恢复初始 |

### Review（资源实测）

- pg 115Mi + operator 33Mi；VM used 5082MiB（31%）；C: 96.7GB

### Definition of Done 核对

- [x] 部署可复现；PVC/主备角色/备份路径全检查；两次故障实验 + RPO/RTO 观测表
- [x] 单副本重启 vs 多副本切换区分（experiments/05 §4.3）
- [x] 资源占用；异常记录；生产差异（§6）；清理步骤（§7）

## 阶段 01–04 归档

- 01 `experiments/01-kubernetes-baseline.md` / 02 `experiments/02-monitoring.md` / 03 `experiments/03-gitops-argocd.md` / 04 `experiments/04-gateway-api.md`
