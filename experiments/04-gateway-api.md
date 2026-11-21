# 实验 04 — Envoy Gateway + Kubernetes Gateway API

- 日期：2026-11-21
- 组件：Envoy Gateway **v1.10.0**（helm chart `docker.io/envoyproxy/gateway-helm`，经 daocloud 镜像站拉取）
- 清单：`components/04-gateway/`（Namespace `gateway-lab`）
- 状态：六项实验全部完成 ✅

## 0. 部署过程与排错（本阶段踩坑密度最高）

| # | 问题 | 解决 |
|---|---|---|
| 1 | helm 宿主机拉 chart：`registry-1.docker.io` / `auth.docker.io` 被墙（Docker Desktop 配了 daocloud 镜像站，宿主直连不通） | `helm pull oci://docker.m.daocloud.io/envoyproxy/gateway-helm:v1.10.0` |
| 2 | chart 默认装 **experimental channel** Gateway API CRDs，与 k3s 自带 standard channel 冲突，被 ValidatingAdmissionPolicy（safe-upgrades 策略，Gateway API 官方升级保护机制）拒绝 | `--set crds.enabled=false`（复用 k3s 已装的 standard CRD 1.6.301） |
| 3 | `crds.enabled=false` 把 Envoy Gateway **自身** CRD（gateway.envoyproxy.io）也跳过了 | 从 chart tgz 手工 `kubectl apply charts/crds/crds/generated/` 补齐 8 个 |
| 4 | 其中 2 个大 CRD（envoyproxies/securitypolicies）client-side apply 注解超 256KB | `kubectl apply --server-side --force-conflicts` |
| 5 | GatewayClass 未自动出现（chart 不建、controller 只消费） | 手工创建 GatewayClass `eg`（controllerName: `gateway.envoyproxy.io/gatewayclass-controller`）→ Accepted=True |
| 6 | Envoy data plane Pod ImagePullBackOff：`auth.docker.io` 取 token 偶发 EOF（网络抖动，非持续封锁） | 删除 Pod 重试即成功 |

**教学价值**：以上 6 步完整演示了"Gateway API channel 管理（standard vs experimental + VAP 保护）"、"GatewayClass 的控制器广告语义"、"server-side apply 的大对象注解问题"。

## 1. 拓扑与组件关系（Gateway Controller vs Envoy Data Plane）

```
用户 HTTP 请求
   │  :80
   ▼
┌─────────────────────────────────────────────────────┐
│ Gateway lab-gateway (gateway-lab ns)                │  ← Gateway API 资源：声明"我要一个监听 :80 的网关"
│   GatewayClass: eg ←── 指向 controller               │
└─────────────────────────────────────────────────────┘
   │ watch Gateway API CR（Gateway/HTTPRoute/...）
   ▼
┌─────────────────────────────────────────────────────┐
│ envoy-gateway Deployment (control plane, 46Mi)      │  ← Gateway Controller
│  · 翻译 Gateway/HTTPRoute/BackendTrafficPolicy...    │     把集群路由意图翻译成 Envoy 配置(xDS)
│  · 经 xDS(HTTP) 下发配置、管理数据面生命周期          │     自己不碰流量
└─────────────────────────────────────────────────────┘
   │ xDS 配置下发 / 拉起·回收
   ▼
┌─────────────────────────────────────────────────────┐
│ envoy-gateway-lab-lab-gateway Pod (data plane, 43Mi) │  ← Envoy Proxy（真正干活的 L7 代理）
│  Service type=LoadBalancer (80:30994)                │     路由/重写/加权/超时/健康检查都在这
└─────────────────────────────────────────────────────┘
   │ 转发
   ▼
backend-v1(3) / backend-v2(1) / slow-backend(1)
```

**一句话**：Gateway Controller（envoy-gateway）是"看图施工的项目经理"，Envoy Data Plane 是"真正搬流量的工人"；Gateway/HTTPRoute 等 CR 是"图纸"。改图纸（apply CR）→ 经理翻译 → 工人换工具（xDS 热更新，无需重启）。

## 2. 实验记录

访问方式：`kubectl -n envoy-gateway-system port-forward svc/envoy-gateway-lab-lab-gateway-8e66c156 18081:80`

### 实验 1：路径路由 + URLRewrite

- 初版 `/v1` 返回 nginx 404：Gateway API **路径匹配 ≠ 路径重写**，原始 URI 透传，nginx 无 /v1 目录
- 加 `URLRewrite{ReplacePrefixMatch: /}` 后：`/v1` → backend-v1 首页，`/v2` → backend-v2 首页 ✓
- 排错插曲：CRD v1.4+ 中 `replacePrefixMatch` 是字符串字段（旧文档为嵌套对象 `{prefix: /}`），以 `kubectl explain` 为准

### 实验 2：负载均衡

- `/v1` ×9 → 命中 3 个不同 v1 Pod（nqmnw/n8z8s/nv2hz），Envoy 默认加权轮询 ✓
- 小样本分布不均（5/1/3）为统计噪声；实际生产观测应以百分位/大样本为准

### 实验 3：权重切流

| 权重 | 采样 | 实测分布 |
|---|---|---|
| v1:80 / v2:20 | 20 次 | 18:2 |
| 同上 | 50 次 | **41:9 ≈ 82:18** ✓ 符合权重 |
| v1:0 / v2:100 | 6 次 | 6:6 全部 v2（全量切流）✓ |

- 操作：`kubectl patch httproute gateway-lab --type=json -p='[...weight 80→0...]'`（**patch 是实验手段**，生产中应改 Git 声明——本阶段组件未接入 Argo CD，下阶段可评估迁入）

### 实验 4：无健康后端 + 自愈

- `backend-v2` scale 0：
  - `GET /v2`（独占规则指向空池）→ **HTTP 503**（Envoy: no healthy upstream）✓
  - `GET /`（80/20 加权）→ 连续 3 次 **HTTP 200**——Envoy 加权集群会跳过无 healthy host 的份额，流量全部落到健康后端（与独占规则行为不同，记录为实测特性）
- 恢复副本 → `/v2` 重新 200，新 Pod 自动入池 ✓ 零配置自愈

### 实验 5：超时

- slow-backend（nc 接受连接后挂起 30s）+ HTTPRoute `timeouts.backendRequest: 2s`
- `GET /slow` → **HTTP 504，耗时 2.006s**（精确触发 2s 超时）✓
- 对照 `/v1`：200，5ms。Gateway 超时保护使慢后端不会拖垮入口

### 实验 6：回滚

- 切流 v2:100 后重新 `kubectl apply -f components/04-gateway/20-httproute.yaml`（声明文件权重 100/0 即回滚目标）
- HTTPRoute 权重回 100/0 → 6/6 请求全部回 backend-v1 ✓
- 与阶段 03 呼应：这里回滚的是"集群内声明"，接入 GitOps 后应回滚 Git

## 3. 资源实测

| 指标 | 实测 |
|---|---|
| envoy-gateway controller | 46Mi |
| Envoy data plane | 43Mi |
| gateway-lab 后端（5 Pod） | ≈50Mi |
| k3d-lab-server-0 容器 | 4.54 GiB（阶段 03 末 3.91GiB，+0.6GB） |
| WSL VM used | 4567 MiB / 15782 MiB（预算 28%） |
| C: 磁盘 | 19.8GB 剩余（**主要约束**，本阶段 -0.8GB） |

## 4. 生产环境差异（实验 vs 生产）

- 单 Gateway 单 data plane 副本：生产多副本 + HPA + 跨可用区
- LoadBalancer Service 由 k3s ServiceLB 模拟（EXTERNAL-IP=pending 最终给节点 IP）：生产用云 LB / MetalLB
- 无 TLS（HTTP listener）：生产应 HTTPS + cert-manager 自动证书
- 超时仅在路由级 2s 示例：生产按服务分级制定超时/重试/熔断策略（BackendTrafficPolicy/EnvoyExtensionPolicy）
- patch 直接改集群：生产必须走 GitOps

## 5. 清理及恢复步骤（未执行）

```bash
kubectl delete namespace gateway-lab
helm uninstall eg -n envoy-gateway-system && kubectl delete namespace envoy-gateway-system
kubectl delete gatewayclass eg
# envoyproxy.io CRD 如不再使用：
kubectl delete -f /tmp/egchart/gateway-helm/charts/crds/crds/generated/
# 恢复：按 §0 步骤重来（chart pull → crds.enabled=false → 补 CRD → GatewayClass）
```
