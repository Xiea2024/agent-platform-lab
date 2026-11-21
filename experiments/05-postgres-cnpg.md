# 实验 05 — cert-manager 评估 + CloudNativePG PostgreSQL

- 日期：2026-11-21
- 组件：CloudNativePG operator **v1.30.2**（chart 0.29.2，ghcr OCI）；PostgreSQL **18.7**（operator 默认镜像）
- 清单：`components/05-postgres/`（Cluster / PodMonitor / 备份 Pod / Backup 检查）
- 状态：部署 + 备份路径检查 + 两次 failover 实验全部完成 ✅

## 0. cert-manager 需求评估（结论：不安装）

- CloudNativePG 自 v1.16 起 webhook 证书**内置自签**，chart 0.29.2 values 中已无任何 cert-manager 依赖键 → **确认不需要 cert-manager**，避免为单一组件引入额外控制面
- 若后续需要签发数据库客户端证书（mTLS）或 Ingress TLS 证书，再评估安装 cert-manager（届时其收益覆盖多个消费者）

## 1. 部署

- operator：`helm install cnpg oci://ghcr.io/cloudnative-pg/charts/cloudnative-pg:0.29.2 -n cnpg-system --set monitoring.podMonitorEnabled=true`
- 集群 `pg-lab`（ns `database`）：2 实例（1 主 1 备，异步流复制）、实例 PVC 1Gi×2（local-path）、requests 200m/256Mi、limits 1/512Mi
- 接入监控：`enablePodMonitor` 已废弃（1.30 起手动管理）→ 手写 PodMonitor（`podmonitor.yaml`），Prometheus `job=podMonitor/database/pg-lab/0`，`cnpg_pg_replication_lag=0` 可查

## 2. 数据面验证

| 项 | 结果 |
|---|---|
| Cluster 状态 | Healthy，PRIMARY 初始 pg-lab-1 |
| 服务 | `pg-lab-rw`（读写）/ `pg-lab-ro`（只读）/ `pg-lab-r`（副本） |
| PVC | pg-lab-1 / pg-lab-2 各 1Gi Bound（local-path 动态供给） |
| 流复制 | `pg_stat_replication`：10.42.0.82 streaming / async；备库可查（hot standby）|
| 测试数据 | `app.lab_data` 100 行（seed），主备一致 |
| 访问模型 | 本地 socket 仅 postgres 超级用户（peer）；网络访问用 `pg-lab-app` secret（无 `-superuser` secret，1.30 按需创建）——测试表属主转给 app |

## 3. 备份与恢复路径检查

### 3.1 物理备份（实验拓扑下不可用，证据）

```bash
kubectl apply -f components/05-postgres/backup-physical-check.yaml   # Backup CR, method=barmanObjectStore
kubectl get backup backup-path-check
# PHASE: failed   ERROR: cannot proceed with the backup as the cluster has no backup section
```

- **结论**：CloudNativePG 物理备份要求集群 spec 配置 `backup.barmanObjectStore`（S3/GCS/Azure）或 CSI VolumeSnapshot；本实验集群两者皆无（不开通云资源、local-path 无 snapshotter）
- 生产建议：MinIO/S3 + WAL 连续归档 → PITR（时间点恢复），RPO 可达分钟级以下

### 3.2 逻辑备份（实验内完整闭环）

```bash
# backup-pod（挂 backup-data PVC，镜像与实例一致）
pg_dump -h pg-lab-rw -U app -d app -Fc -f /backup/app.dump   # 3.2KB
psql -c "CREATE DATABASE app_restore OWNER app"
pg_restore -h pg-lab-rw -U app -d app_restore /backup/app.dump
SELECT count(*) FROM lab_data;   -- 100 ✓（校验后已清理恢复库）
```

- RPO 语义：逻辑备份的 RPO = 两次备份间隔（本实验为手工触发）
- 排错记录：① 裸 Pod apply 改 image 不触发重建（须 delete + apply）；② 镜像 tag `18.7` 不存在，须与实例一致（`18.7-system-trixie`）；③ pg_dump 客户端大版本必须 ≥ 服务端（17.5 客户端对 18.7 服务端直接拒绝）

## 4. 高可用实验（核心）

### 4.1 "非破坏性 Pod 重建" → 实测为自动 Failover（认知修正）

删除主 Pod `pg-lab-1` 后的实际行为**不是原地重启**：

1. 备库 pg-lab-2 提升为新主（failover）
2. 原主 PVC 保留，新 pg-lab-1 Pod 以**备库**角色重建并重新建立流复制
3. 期间写入探测：3 成功 / 1 失败（失败即不可写窗口）

| 指标 | 观测值 |
|---|---|
| RTO（删除→pg-lab-rw 可写） | ≈ 14s |
| RPO | **0**（故障前最后已提交写 19:27:07.222 完好；失败那条为未确认写） |
| 数据 | 103 行无损，拓扑自动收敛 |

### 4.2 受控主故障实验（二次 failover，批准后执行）

删除新主 `pg-lab-2`（pg-lab-1 提升，回到初始拓扑）：

| 指标 | 观测值 |
|---|---|
| RTO | **138s**（19:29:27 → 19:31:45） |
| RPO | **0**（故障前 3 笔已提交写全保留；恢复后第一笔写 19:31:45.554 落库） |
| 客户端表现 | 2 次连接拒绝 → 连接挂起（hang）直到恢复 |

**两次 RTO 差异分析（14s vs 138s）**：
- 第一次：备库长期健康、复制 lag=0，提升快
- 第二次：发生在**集群刚完成一次 failover 的收敛过程中**（pg-lab-1 作为备库仅重建 2 分钟），operator 需完成旧主 fence、一致性检查、备库重建并行流程，服务恢复以"全集群实例就绪"为准 → 窗口长一个数量级
- **教训**：failover 恢复时间不是常数，连续故障/收敛期故障显著变慢；生产应压测统计 P95/P99，并设置客户端重连+超时策略

### 4.3 单副本重启 vs 多副本切换（区分总结）

| 场景 | 机制 | RPO | RTO（观测） |
|---|---|---|---|
| 多副本切换（删主 Pod） | 备库 promote + 原主重建为备 | 0（复制同步时） | 14s~138s（取决于集群收敛状态） |
| 单副本重启（想象 1 实例集群） | 同 PVC 原地重建 | 0 | 分钟级（postgres crash recovery） |
| 备份恢复（无副本可切） | pg_restore / PITR | >0（备份点以来） | 小时级 |

## 5. 资源实测

| 指标 | 实测 |
|---|---|
| pg-lab-1 / pg-lab-2 | 62 / 53 Mi（含 metrics exporter） |
| cnpg operator | 33 Mi |
| backup-pod | ~0（sleeping） |
| PVC | 3 × 1Gi Bound（2 实例 + 1 备份） |
| k3d-lab-server-0 容器 | 5.47 GiB（阶段 04 末 4.54GiB，+0.9GB） |
| WSL VM used | 5082 MiB / 15782 MiB（**31%**） |
| C: 磁盘 | 96.7 GB ✓ |

## 6. 生产环境差异（实验 vs 生产）

- 无对象存储 → 无 PITR；生产必须配 S3/MinIO + WAL 归档 + 定期 Backup 验证恢复
- 异步复制 lag=0 是空载观测；生产高写入下 lag>0 时 RPO>0，关键业务应评估同步复制（`synchronous` 实例组）或至少监控 lag 告警
- 2 实例容忍 1 故障；生产通常 3 实例 + 跨 AZ
- 无连接池（PgBouncer/CloudNativePG Pooler CR）；生产应加 Pooler 减少 failover 连接风暴
- local-path 节点绑定；生产用网络存储（即使延迟更高，换取节点故障转移能力）
- 密码即 secret 随机生成；生产接 External Secrets/Vault 并轮换

## 7. 清理及恢复步骤（未执行）

```bash
kubectl delete namespace database          # 级联删除 cluster/PVC/备份（PVC 删除不可恢复！）
helm uninstall cnpg -n cnpg-system && kubectl delete namespace cnpg-system
# envoyproxy.io 等 CRD 由 operator 管理，随卸载清理
# 恢复：按 §1 顺序重装
```
