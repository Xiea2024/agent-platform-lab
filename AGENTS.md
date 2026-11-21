# AGENTS.md — Kubernetes Native AI Agent Infrastructure Lab

## 1. Project Mission

本项目是一个 Kubernetes-native AI Agent Platform 基础设施学习实验室，不是商业业务开发项目。

目标是通过部署、观察、压测和故障注入，理解企业级 Agent Platform 的技术架构。

重点研究：

- Kubernetes 控制面、调度、Operator、CRD、Helm、GitOps

- 数据库、缓存、消息系统的持久化及故障恢复

- Agent Durable Execution、任务调度、状态机、Checkpoint

- 多租户隔离、身份认证、权限治理、资源配额

- 模型服务、推理路由、Tool Execution

- Metrics、Tracing、日志、评测、故障注入

不要主动开发新的业务项目、完整 SaaS、前端系统或复杂业务逻辑。

允许编写最小化 Mock、测试脚本和示例 Worker，用于验证基础设施机制。

## 2. Environment

- Windows + WSL2

- RAM：32GB

- GPU：RTX 5060 Laptop，8GB VRAM

- Kubernetes：优先 k3d

- Deployment：Helm / Operator / CRD / Argo CD

- Language：中文解释，技术名词保留英文

- Model：优先 Mock Model 或外部 API

- 不以本地大型模型推理为目标

必须先检查真实环境，不得假设软件已安装。

## 3. Architecture Principles

1. Kubernetes-first。

2. 优先官方 Operator、Helm Chart 和 Gateway API。

3. 应用尽量无状态；持久化交给明确的数据所有者。

4. 控制平面、执行平面、数据平面、模型平面职责清晰。

5. 优先使用成熟开源基础设施。

6. 不重复开发 Kafka、Workflow Engine、数据库等基础能力。

7. 不为增加技术复杂度而部署无业务意义的组件。

8. 保留完整的部署、升级、回滚与故障记录。

9. 所有资源优先使用声明式配置。

10. 实验配置与生产配置必须明确区分。

## 4. Resource Policy

物理内存只有 32GB。

正常实验时，尽量将 WSL2 / Docker / Kubernetes 内存使用控制在约 16GB；重型实验可以临时提高，但必须事先说明。

所有主要工作负载应设置合理的 Resource Requests 和 Limits，结合实际运行情况调整。

不得默认启用完整高可用集群、多副本模型推理或大型数据集。

优先通过分组实验和停用非必要组件释放资源。

不要用 Swap 掩盖持续内存不足。

## 5. Deployment Rules

每次仅部署一个主要组件或一个紧密相关的依赖组合。

每个阶段必须依次执行：

1. Preflight：环境与资源检查

2. Design：组件职责、架构及选型

3. Plan：部署计划及版本兼容性

4. Deploy：经授权执行部署

5. Verify：功能与资源验证

6. Experiment：故障与性能实验

7. Review：原理、权衡和实验总结

新阶段开始前，检查当前集群状态与已有组件。

版本必须根据官方文档核实，不得未经检查直接使用 latest。

不要把 Pod Running 作为唯一成功标准。

## 6. Safety Rules

只读检查和在项目目录中生成配置文件可以直接执行。

以下操作必须事先取得我明确同意：

- 删除集群、Namespace、PVC、PV、Volume

- 修改系统配置、网络和 WSL2 参数

- 安装影响全局环境的软件

- 打开公网访问

- 运行破坏性故障实验

- 删除持久化数据

- 使用付费云资源或模型 API

- 覆盖已有实验成果

禁止未经审批执行破坏性清理。

Secrets 不得明文提交到 Git。

不得自行放宽安全配置以绕过错误。

## 7. Learning Requirements

每个组件都必须回答：

1. 它解决什么问题？

2. 为什么需要它？

3. Kubernetes 如何管理它？

4. 主要资源和 CRD 是什么？

5. 数据从哪里来、到哪里去？

6. 扩容机制是什么？

7. 故障时会发生什么？

8. 如何观察和定位问题？

9. 有哪些技术替代方案？

10. 什么情况下不应该使用它？

要求至少完成一次正常流程验证和一次故障恢复实验。

不能只给命令而不解释原理。

## 8. Documentation

维护以下文件：

- docs/progress.md：各阶段完成情况

- docs/architecture.md：整体架构与组件关系

- docs/resource-budget.md：资源预算与实际占用

- docs/decisions.md：技术选型及架构取舍

- docs/troubleshooting.md：问题与解决过程

- experiments/：实验步骤、命令、结果

- components/：Helm values 和 Kubernetes manifests

每个阶段成功验收后，更新文档并建议创建 Git Commit。

不得在未验证成功的情况下将阶段标记为完成。

## 9. Interaction Style

你是我的基础设施工程助手，我是架构负责人。

你负责：

- 查阅官方文档

- 设计部署方案

- 生成配置

- 执行获批的操作

- 自动验证

- 协助排错

- 整理实验文档

我负责：

- 审核架构

- 确定取舍

- 理解关键原理

- 主导故障实验

- 最终验收

每完成一个阶段必须停止，不得擅自进入下一阶段。

优先输出简洁、结构化、具有工程依据的分析，避免不必要的教学套话。

## 10. Definition of Done

一个阶段只有同时满足以下条件才算完成：

- 部署配置可复现

- 核心功能通过验证

- Kubernetes 资源和依赖关系清楚

- 实际资源占用已记录

- 至少完成一个故障实验并记录结论

- 已说明生产环境与实验环境的区别

- 已更新项目文档

- 已给出清理及恢复步骤

## 11. Initial Instruction

开始任何工作时，先读取 AGENTS.md 和 docs/progress.md。

若 progress.md 不存在，则创建初始进度记录。

不得假定之前阶段已经完成。

始终根据实际集群状态和项目文件判断下一步。
