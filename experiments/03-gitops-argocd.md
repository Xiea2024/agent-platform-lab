# 实验 03 — Argo CD（GitOps）

- 日期：2026-11-21
- 组件：Argo CD **v3.6.2**（helm chart `argo-cd` 10.18.2，经 ghcr OCI 安装）
- 状态：Application / Sync / Drift / Rollback / Helm values 管理全部完成 ✅

## 1. 部署

- chart：`oci://ghcr.io/argoproj/argo-helm/argo-cd:10.18.2`（appVersion v3.6.2 精确对应）
- values：`gitops/bootstrap/argocd-values.yaml`（单副本、禁 dex/notifications、全组件 requests/limits）
- CLI：winget `argoproj.argocd` v3.6.2
- **计划偏差记录**：
  1. 原计划 helm repo `argoproj.github.io` 被本机 DNS 解析为 0.0.0.0（拦截），改经 ghcr OCI（troubleshooting.md）
  2. values 中 `applicationSet.enabled: false` 未生效（chart 10.x key 结构变化），applicationset-controller 仍在运行（23Mi，接受现状，后续如需精确控制查 chart values 文档）

## 2. GitOps 目录结构

```
gitops/
├── bootstrap/argocd-values.yaml   # Argo CD 自身 helm values
├── apps/gitops-demo.yaml          # Application CR
└── workloads/gitops-demo/         # 被管理的 Helm chart（nginx + 版本 ConfigMap）
```

## 3. 安全边界（按阶段要求）

- Application 无 `resources-finalizer` → 删除 Application 不级联删除集群资源
- syncPolicy：`automated` 但 **prune: false**（Git 删文件不自动删集群资源）、**selfHeal: false**（便于 Drift 实验）
- 示例应用不含 PVC；现存 `demo` / `monitoring` 等命名空间未注册进 Argo CD，完全不受管

## 4. 实验记录

### 4.1 首次 Sync

- `kubectl apply -f gitops/apps/gitops-demo.yaml` 后 ~20s：Synced/Healthy
- `gitops-demo` 命名空间自动创建（CreateNamespace=true）；Deployment 2/2、ClusterIP Service、ConfigMap `APP_VERSION=1.0.0` ✓

### 4.2 Git 变更自动同步

- 变更：`values.yaml` 副本 2→3、`appVersion 1.0.0→1.1.0` → commit `8b7209a` → push
- **未执行任何 kubectl 操作**，~2min 后（默认 3min 轮询周期内）自动收敛：
  - Deployment 3/3，ConfigMap `APP_VERSION=1.1.0` ✓

### 4.3 Drift 实验

- 人为漂移：`kubectl -n gitops-demo scale deploy/gitops-demo --replicas=5`
- 40s 内 Application 状态：**OutOfSync / Healthy**（selfHeal 关闭，Argo CD 只报告、不纠正）
- 手动收敛：`argocd app sync gitops-demo` → `successfully synced` → 副本回 3/3，状态回 Synced/Healthy ✓

### 4.4 回滚实验

**关键发现**：`argocd app rollback` 在 auto-sync 开启时被 API 拒绝：

```
FailedPrecondition: rollback cannot be initiated when auto-sync is enabled
```

**原因**：rollback 本质是带 revision 覆盖的 sync；auto-sync 下次轮询会把集群拉回 main HEAD，回滚立即被"修复"，产生无意义震荡。这是 Argo CD 的刻意设计。

**GitOps 正确姿势——Git 层回滚**：

```bash
git revert 8b7209a --no-edit && git push   # 生成反向 commit 5c34efb
```

- ~2min 后自动同步：Deployment 回 2/2、ConfigMap 回 `1.0.0` ✓
- **结论**：GitOps 中回滚不是"把集群退回旧状态"，而是"在 Git 中声明一个新状态"；Git 是唯一事实来源，集群永远向 Git 收敛

## 5. 访问方式

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
# UI: https://localhost:8080 （注意是 https，--insecure 访问）
# CLI: argocd login localhost:8080 --insecure --grpc-web
```

- 初始 admin 密码：`kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d`

## 6. 资源实测

| 指标 | 实测 |
|---|---|
| argocd 各 Pod 合计 | ≈ **184Mi**（controller 99 / server 29 / repo-server 28 / applicationset 23 / redis 5） |
| k3d-lab-server-0 容器 | 3.91 GiB（阶段 02 末 2.92GiB，增量 ≈ +1GB） |
| WSL VM 整体 used | 4160 MiB / 15782 MiB |
| C: 磁盘 | 22.6 GB 剩余（本阶段增量 ≈ 2.1GB） |

## 7. 生产环境差异（实验 vs 生产）

- 单副本非 HA、无 Ingress/TLS 终端、admin 初始密码未轮换：生产需 HA、SSO（dex 此时启用）、证书管理
- 无 project 隔离（用 default project + 无 source 限制）：生产应 AppProject + RBAC 细分团队权限
- 3 分钟轮询：生产应配 Webhook / ApplicationSet 批量管理 / 多集群
- 回滚依赖 git revert（已验证）：生产应保护 main 分支（PR review、CI、CODEOWNERS）

## 8. 清理及恢复步骤（未执行）

```bash
# 注销应用（集群资源保留：无 finalizer、prune=false）
kubectl -n argocd delete application gitops-demo
kubectl delete namespace gitops-demo        # 单独手动清理工作负载

# 卸载 Argo CD
helm uninstall argocd -n argocd && kubectl delete namespace argocd

# 恢复
helm install argocd oci://ghcr.io/argoproj/argo-helm/argo-cd:10.18.2 \
  -n argocd --create-namespace -f gitops/bootstrap/argocd-values.yaml
kubectl apply -f gitops/apps/gitops-demo.yaml
```
