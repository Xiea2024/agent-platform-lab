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


---

## 2026-11-21 · 阶段 03：Argo CD（GitOps）

### D-08 GitOps 部署模式：Argo CD + 本仓库单仓结构

- **选择**：Argo CD v3.6.2（helm chart 10.18.2）；仓库内新增 `gitops/{bootstrap,apps,workloads}` 三层结构
- **理由**：Git 作为唯一事实来源与 AGENTS.md §3.9 声明式配置原则一致；Application CR 注册应用、Helm chart 管理 values，与后续数据组件的发布模式复用
- **安全边界**：Application 无 finalizer、prune=false、selfHeal=false；示例应用独立于现存关键服务；不含 PVC
- **替代方案**：Flux CD（GitOps 另一主流，拉式模型类似）、Argo CD ApplicationSet 多应用管理（后续规模大了再引入）

### D-09 回滚语义：git revert 而非 argocd rollback

- **实测结论**：auto-sync 开启时 Argo CD API 拒绝 CLI rollback（FailedPrecondition），因其会被下次轮询立即覆盖
- **取舍**：回滚 = 在 Git 声明反向 commit（已验证：revert push 后 ~2min 自动收敛）。这强化了"Git 是唯一事实来源"的纪律，代价是回滚必须过 Git 流程（生产应配 PR 保护）

### D-10 chart 获取路径：ghcr OCI 作为本环境首选

- 本机 DNS 拦截 `raw.githubusercontent.com` / `*.github.io`（0.0.0.0 黑洞），ghcr.io / api.github.com / quay.io / docker.io 正常
- 组件选型时把"是否有 ghcr OCI 制品"作为可达性权重项；需要 GitHub 文件时走 blobs API


---

## 2026-11-21 · 阶段 04：Envoy Gateway + Gateway API

### D-11 南北向入口：Envoy Gateway（Gateway API 实现）

- **选择**：Envoy Gateway v1.10.0 作为集群唯一 Gateway 实现；不启用 Ingress Controller（Traefik 阶段 01 已禁用）
- **理由**：AGENTS.md §3.2 优先 Gateway API；Gateway API 是 K8s 南北向流量的标准 API（Ingress 继任者）；一个 GatewayClass 可由实现替换（图纸与施工分离）
- **替代方案**：Traefik/NGINX Ingress（Ingress API，旧标准）、HAProxy Ingress、Kong；Cilium Gateway（若后续 Cilium CNI）
- **CRD channel 决策**：保持 k3s 自带 standard channel（experimental CRD 被 VAP 拒绝是预期保护），URLRewrite/Timeouts 均已在 standard

### D-12 镜像获取：宿主直连与 Docker daemon 分离

- 宿主机（helm/curl）→ docker hub 认证端点被墙；Docker daemon → 配 daocloud 镜像站正常；集群内容器 → 与宿主网络同层，偶发 EOF（重试即可）
- 原则：**宿主机获取制品（chart/tgz）走镜像站 OCI 路径；容器镜像拉取依赖 daemon mirror 不变**


---

## 2026-11-21 · 阶段 05：cert-manager 评估 + CloudNativePG

### D-13 数据库 Operator：CloudNativePG

- **选择**：CloudNativePG v1.30.2，2 实例异步流复制
- **理由**：K8s 原生 PostgreSQL Operator（CNCF Sandbox，贡献者即 PG 核心公司 EDB）；声明式 Cluster CR 管理主备/failover/备份/监控，与 GitOps 模型契合；不重复造数据库（§3.6）
- **替代方案**：Zalando Postgres Operator、CrunchyData PGO、KubeBlocks、Bitnami PostgreSQL Helm（主备靠 InitContainer/Patroni，无 Operator 级 failover）
- **为什么不选 Bitnami Helm**：Helm 主备缺乏 Operator 的故障转移编排能力，实验目标含"多副本切换/RPO-RTO 观测"，需要真正的大脑

### D-14 cert-manager 暂不安装

- CloudNativePG webhook 证书内置自签（chart 0.29.2 无 cert-manager 依赖），当前唯一消费者不需要 → 不安装
- 触发重新评估的条件：需要 Ingress TLS 自动化 / 客户端 mTLS / 多组件共享 CA

### D-15 实验拓扑无对象存储，物理备份路径记录为限制

- 物理备份（barmanObjectStore / VolumeSnapshot）要求实验环境不具备的设施；用 `Backup` CR 实测报错作为证据
- 逻辑备份（pg_dump→PVC→pg_restore）作为实验内闭环路径；生产方案（S3+WAL 归档+PITR）写入文档差异章节


---

## 2026-11-21 · 阶段 06：Valkey + Keycloak + 受保护 API

### D-16 Valkey 用 manifest 直装（放弃官方 chart 探测）

- 单实例缓存场景下，helm chart 的收益（参数化）不值得承担分发渠道不可达风险（D-10）——manifest 16 行即完整可复现
- 缓存平面默认允许丢失：RDB 默认 save 点 + 优雅停机 SAVE 已够实验；AOF/哨兵/集群按需后加

### D-17 Keycloak 选 codecentric keycloakx（ghcr OCI）

- bitnami chart 在 daocloud 镜像站 403；keycloakx 7.4.0 经 ghcr OCI 直达、appVersion 精确、社区成熟
- chart 默认 `command: []` 需显式 `kc.sh start`（troubleshooting 记录）

### D-18 Keycloak hostname 双 Service 模式

- iss（KC_HOSTNAME）必须与集群内 JWKS 访问地址同源，否则验签 issuer 校验失败
- ExternalName 不做端口映射（仅 DNS CNAME）→ 弃用；采用 **ClusterIP 别名 Service 指向同一 Pod**，`keycloak-keycloakx-http:80`（宿主）与 `keycloak:8080`（集群内）并存
- 该模式同样适用于后续其他带 issuer 的内网组件
