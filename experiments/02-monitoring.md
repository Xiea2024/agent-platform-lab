# 实验 02 — Metrics + Prometheus + Grafana

- 日期：2026-11-21
- 组件：kube-prometheus-stack chart **93.6.1**（经 `oci://ghcr.io/prometheus-community/charts` 安装）
- 命名空间：`monitoring`；告警与负载清单在 `components/02-monitoring/`
- 状态：正常流程验证 ✅；CPU 负载告警全生命周期（inactive → firing → inactive）✅

## 1. 部署

```bash
helm install kube-prometheus-stack oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack \
  --version 93.6.1 -n monitoring --create-namespace \
  -f components/02-monitoring/kube-prometheus-stack-values.yaml
```

关键裁剪（values 文件）：禁用 kubeEtcd / kubeScheduler / kubeControllerManager / kubeProxy 抓取（k3s 内嵌无独立 endpoint）及对应默认规则；Prometheus retention 3d + emptyDir + 1Gi limit；全组件 requests/limits。

镜像版本（实测）：prometheus v3.16.0-distroless、grafana 13.3.1-distroless、alertmanager / operator / kube-state-metrics / node-exporter（chart 93.6.1 锁定）。

## 2. 验证

| 验证项 | 命令/方式 | 结果 |
|---|---|---|
| Pod 状态 | `kubectl -n monitoring get pods` | 6 个 Pod 全部 Running（alertmanager 2/2、prometheus 2/2、grafana 3/3） |
| 抓取目标 | `curl :9090/api/v1/targets` | **13/13 up**（无被禁用组件的 down 目标） |
| kubectl top | `kubectl top node / top pods -A` | 正常返回（metrics-server 为 k3s 自带，阶段 01 已部署） |
| 数据源 | Grafana API `/api/datasources` | Prometheus + Alertmanager 已 provision |
| 仪表盘 | Grafana API `/api/search` | **25 个**默认仪表盘（Compute Resources / Pod、Nodes、CoreDNS、Networking 等） |
| 告警规则 | `curl :9090/api/v1/rules` | 自定义规则 LabLoadTestCpuHigh 已加载 |

## 3. 告警实验（CPU 负载全生命周期）

### 3.1 规则（`components/02-monitoring/lab-alert-rules.yaml`）

```yaml
alert: LabLoadTestCpuHigh
expr: sum(rate(container_cpu_usage_seconds_total{namespace="load-test"}[1m])) by (pod) > 0.5
for: 1m
```

### 3.2 加压

```bash
kubectl apply -f components/02-monitoring/load-test-pod.yaml   # busybox yes > /dev/null, limit 1 核
```

观察：

| 时间点 | 指标/状态 | 证据 |
|---|---|---|
| 加压后 | `kubectl top pod -n load-test` | cpu-loader = **1001m**（顶到 limit） |
| 加压后 | 节点 CPU | 1239m → 负载删除后回落 **151m** |
| ~2min | Prometheus 规则状态 | LabLoadTestCpuHigh → **firing** |
| ~2min | Alertmanager `/api/v2/alerts` | LabLoadTestCpuHigh **active**（另含默认 Watchdog 探活告警） |

### 3.3 恢复

```bash
kubectl delete pod cpu-loader -n load-test
```

| 时间点 | 指标/状态 | 证据 |
|---|---|---|
| 删除瞬间 | 查询 `rate(...{namespace="load-test"}[1m])` | 仍为 ~1.43（1 分钟窗口残留旧数据） |
| +2~3min | 同查询 | `[]` 无数据（窗口滑过，序列消失） |
| +2~3min | 规则状态 | → **inactive** |
| +2~3min | Alertmanager | 仅剩 Watchdog |

**结论**：告警链路 `cAdvisor 指标 → Prometheus 规则求值(firing) → Alertmanager 接收` 完整可验证；`for: 1m` + 1m rate 窗口意味着负载停止后告警有 2~3 分钟自然滞后，这是 Prometheus 模型特性而非故障。

## 4. 排错记录（本阶段新增）

1. **GitHub Releases 下载 chart 超时**（2 次）→ 改经 ghcr OCI 安装成功（troubleshooting.md）
2. **Grafana OOMKilled (Exit 137)**：Grafana 13 全量仪表盘 provision 实测需 ~440Mi，初值 limit 256Mi 过小 → 上调 512Mi（troubleshooting.md）

## 5. 资源实测（负载已清理后）

| 指标 | 实测 |
|---|---|
| monitoring 各 Pod 合计 | ≈ **810Mi**（grafana 416 + prometheus 317 + alertmanager 28 + operator 21 + ksm 19 + node-exporter 9） |
| k3d-lab-server-0 容器 | 2.89 GiB（阶段 01 基线 759Mi，增量 ≈ +2.1GB 含采集缓存） |
| WSL VM 整体 used | 3501 MiB / 15782 MiB（阶段 01 基线 1939Mi） |
| C: 磁盘 | 24.7 GB 剩余（本阶段镜像/layer 增量 ≈ 3.2GB） |

## 6. 生产环境差异（实验 vs 生产）

- Prometheus emptyDir + retention 3d：生产应持久卷 + 更长保留 + 对象存储长期归档（Thanos/Cortex）
- Alertmanager 单副本无持久化、仅默认路由：生产需 HA + 通知渠道（钉钉/邮件/PagerDuty）+ 告警分组静默治理
- Grafana 密码为 chart 自动生成：生产应接入 SSO/OAuth， Secrets 走 External Secrets
- node-exporter 在 k3d 容器内采集的是 k3s 容器视角的 /proc：生产应为真实节点级采集 + 独立节点Exporter 拓扑

## 7. 清理及恢复步骤（未执行）

```bash
# 删除本阶段实验负载（保留监控栈）
kubectl delete namespace load-test
kubectl -n monitoring delete prometheusrule lab-load-alert

# 卸载监控栈（删除 CRD 需另行处理，注意会级联删除监控命名空间内 CR 实例）
helm uninstall kube-prometheus-stack -n monitoring

# 恢复
helm install kube-prometheus-stack oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack \
  --version 93.6.1 -n monitoring --create-namespace \
  -f components/02-monitoring/kube-prometheus-stack-values.yaml
kubectl apply -f components/02-monitoring/lab-alert-rules.yaml
```

## 8. 访问方式（port-forward，无需 Ingress）

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090     # Prometheus UI
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80          # Grafana
kubectl -n monitoring port-forward svc/kube-prometheus-stack-alertmanager 9093:9093   # Alertmanager
```

Grafana 登录：用户 `admin`，密码从 secret 读取：

```bash
kubectl get secret --namespace monitoring -l app.kubernetes.io/component=admin-secret \
  -o jsonpath="{.items[0].data.admin-password}" | base64 --decode
```
