# 实验 01 — Kubernetes 基础环境基线

- 日期：2026-11-21
- 集群：k3d `lab`（k3s v1.37.2+k3s1，单 Server 节点，禁用 Traefik）
- 状态：正常流程验证 ✅ 全部通过（故障恢复实验属阶段后续内容，本阶段做 Pod 级自愈验证）

## 1. 集群创建

```bash
k3d cluster create lab --servers 1 --agents 0 \
  --image rancher/k3s:v1.37.2-k3s1 \
  --k3s-arg "--disable=traefik@server:*" --wait
```

- 成功，kubeconfig context 自动切换为 `k3d-lab`
- API Server 经 LoadBalancer 容器发布：`0.0.0.0:5347 -> 6443`（见 troubleshooting.md，需手动改回 127.0.0.1）

## 2. 核心组件验证

| 验证项 | 命令 | 结果 |
|---|---|---|
| 节点 | `kubectl get nodes -o wide` | k3d-lab-server-0 Ready，v1.37.2+k3s1 |
| Namespace | `kubectl get ns` | default / kube-system / kube-public / kube-node-lease |
| 系统 Pod | `kubectl get pods -A` | coredns、local-path-provisioner、metrics-server Running；gateway-api-crd 安装器 Completed；无 traefik（已禁用）✓ |
| 默认存储类 | `kubectl get sc` | local-path（default，WaitForFirstConsumer，Delete） |

## 3. 工作负载验证（Namespace demo）

Manifest 位于 `components/01-kubernetes-baseline/`。

### 3.1 Deployment + Service

```bash
kubectl apply -f components/01-kubernetes-baseline/
kubectl -n demo rollout status deployment/nginx   # successfully rolled out, 2/2
kubectl -n demo get svc                           # nginx ClusterIP 10.43.155.10:80
```

### 3.2 PVC 动态供给

```bash
kubectl -n demo get pvc     # 初始 Pending（WaitForFirstConsumer）
```

- Pod `pv-test` 调度后，provisioner 自动创建 PV：`/var/lib/rancher/k3s/storage/pvc-bc002730-..._demo_data`
- PVC `data` Bound（100Mi，RWO）
- 数据验证：`kubectl -n demo exec pv-test -- cat /data/written-by-pv-test.txt` → 时间戳文件存在 ✓

### 3.3 Service 发现（DNS）

```bash
kubectl -n demo run net-test --image=busybox:1.36 --restart=Never --rm -i -- nslookup nginx.demo.svc.cluster.local
```

- 解析结果：`10.43.155.10`（ClusterIP），CoreDNS 正常 ✓
- HTTP 访问（curl Pod 经 Service DNS 发 3 次请求）：3/3 HTTP 200 ✓

### 3.4 Pod 自愈

```bash
kubectl -n demo delete pod nginx-b4564c78b-ks7q6 --wait=false
```

| 观察项 | 结果 |
|---|---|
| 副本数 | Deployment 全程保持 2/2 AVAILABLE |
| 新 Pod | 12s 内新建 `nginx-b4564c78b-6lnm8`（新 UID、新 IP 10.42.0.13） |
| 业务连续性 | 删除后立即 curl 5 次：5/5 HTTP 200（Service 将流量切到存活 Pod） |
| EndpointSlice | `nginx-5tcst` 更新为 10.42.0.6,10.42.0.13 ✓ |

**结论**：ReplicaSet 控制器保证期望副本数；Service/EndpointSlice 提供稳定虚拟 IP 与后端发现，单 Pod 故障对客户端透明。

## 4. 资源占用实测

| 指标 | 实测 |
|---|---|
| k3d-lab-server-0 容器 | 720.8 MiB（4.57% of VM），CPU 基线 ~9.5%（含拉起抖动，平时 <5%） |
| k3d-lab-serverlb / tools | 22.05 MiB / 2.77 MiB |
| WSL2 VM（Docker Desktop 整体） | used 2167 MiB / 15782 MiB，available 13331 MiB |
| K8s 视角 Node | 714Mi，CPU 166m |
| demo 业务 Pod | nginx 12Mi×2，pv-test ~0 |
| kube-system | coredns 15Mi + local-path 9Mi + metrics-server 23Mi |
| 磁盘增量 | C: 29.6→27.9GB（约 1.7GB：k3s 镜像 379MB + 应用镜像 + 容器层/PV） |

## 5. 生产环境差异（实验 vs 生产）

- 单 Server + SQLite 存储：生产应为 ≥3 Server 嵌入式 etcd 高可用
- 节点本地目录存储（local-path）：生产应使用网络存储（CSI）保障跨节点持久化与故障转移
- 无 Ingress / 无 RBAC 细分 / 无 NetworkPolicy：生产需统一入口、最小权限、网络隔离
- 资源无 LimitRange / ResourceQuota：生产需配额治理

## 6. 清理及恢复步骤（未执行）

```bash
# 仅删除本阶段工作负载（保留集群）
kubectl delete namespace demo

# 删除整个集群（破坏性，需事先批准）
k3d cluster delete lab

# 重新创建
k3d cluster create lab --servers 1 --agents 0 --image rancher/k3s:v1.37.2-k3s1 --k3s-arg "--disable=traefik@server:*" --wait
kubectl apply -f components/01-kubernetes-baseline/
```
