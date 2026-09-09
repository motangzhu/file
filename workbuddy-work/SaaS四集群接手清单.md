# SaaS 四集群接手清单（TKE：sit / uat / prod / 中间件）

> 用途：接手一套 SaaS 的 TKE 集群时，按这份清单逐项摸底、逐项提问，把答案填进附录表格，就是你的交接文档和后续 runbook 素材。
> 适用背景：已能通过堡垒机登录节点、能在 TKE 控制台查看，四个集群分别是 sit（集成测试）、uat（验收）、prod（生产）、中间件（共享底座）。
> 铁律：**接手前两周只做只读操作，任何写操作必须有第二人在场或走审批。**

---

## 用法：三阶段推进，别一次全铺开

| 阶段 | 目标 | 交付物 |
|---|---|---|
| **Day 1–3　摸底** | 只读，把四集群的"骨架"画出来 | 填完附录 A 信息回收表 |
| **Week 1　跑通** | 跟着前任完整走一遍 sit → uat → prod 发布流程，只看不动手 | 发布 runbook 一版 |
| **Week 2–4　独立** | 能独立处置告警、能独立发一次 sit、能写清 prod 变更方案 | 补齐监控大盘、故障手册、红线清单 |

**节奏建议**：先搞懂 sit（随便折腾）→ 再搞懂 uat（理解验收标准）→ 最后碰 prod（此时你已经知道该问什么了）。中间件集群穿插在第一周，因为它决定整体可用性。

---

## 第 0 章　先搞清四集群的关系（最重要，先看这个）

### 0.1 心智模型

```
sit / uat / prod  = 三套业务环境（各自独立集群）
中间件集群        = 三套环境共用的底座（DB / Redis / MQ / 注册中心 / ES）
```

由此推出三条**必须刻进脑子**的结论：

1. **中间件集群是风险最高的一个**，不是 prod。它挂了，三套环境一起挂；它慢了，三套环境一起慢。它的变更窗口比 prod 还难排。
2. **prod 的故障不一定在 prod**。线上报障时，一半以上的根因在中间件集群或网络链路上，别闷头只看业务 Pod。
3. **sit/uat 与 prod 的配置差异是事故温床**。同一个镜像在 uat 正常、到 prod 就挂，90% 是配置/密钥/网络策略差异，不是代码问题。

### 0.2 必须先问清的四个问题

- 中间件集群是**三环境共用一套实例**，还是**每环境一套实例（同集群不同命名空间/不同库）**？
- 如果是共用：靠什么隔离？不同 database？不同 Redis db index？不同 MQ topic 前缀？不同 Nacos namespace/group？
- 有没有**跨集群网络打通**？业务集群访问中间件走的是内网 CLB、CEN 云联网、对等连接，还是 Pod 直连？
- prod 的数据链路里，有没有**跨地域**调用（比如 prod 在广州、中间件在上海）？跨地域的延迟与带宽包水位看过吗？

### 0.3 验收标准

能不看文档，在白板上画出：**用户请求 → 入口 → 业务 Pod → 中间件 → 存储** 的完整链路，并说出每一段的"如果这里断了，现象是什么"。

---

## 第 1 章　权限与账号（进不去等于零）

### 要看什么

| 类别 | 具体项 |
|---|---|
| 腾讯云账号 | 主账号归属、子账号、是否有 CAM 权限边界、prod 是否需申请临时权限 |
| 堡垒机 | 可登录哪些节点、是否需要申请、有无操作审计留存 |
| TKE 控制台 | 哪些集群可见、是否有写权限、生产集群是否默认只读 |
| K8s RBAC | 你的账号在四集群分别是 cluster-admin 还是受限 Role；prod 是不是只读 |
| kubectl | kubeconfig 从哪获取、有效期多久、过期怎么续 |
| 镜像仓库 | TCR / CCR / 自建 Harbor 的账号与拉取权限 |
| 代码与流水线 | CNB 或其他 CI 的仓库权限、能否触发构建、能否触发发布 |
| 中间件账号 | 数据库、Redis、MQ、注册中心的账号（尤其**只读账号**，先要只读的） |
| 监控告警 | 云监控、Grafana、CLS 的可见范围；告警通知组里有没有你 |

### 怎么查

```bash
# 我在当前集群能干什么（最重要的一条）
kubectl auth can-i --list

# 具体到某个危险操作（接手第一天就该测）
kubectl auth can-i delete pods -n <ns>
kubectl auth can-i create deployments -n <ns>
```

控制台路径：腾讯云控制台 → 访问管理 CAM → 用户 → 用户列表 → 权限；容器服务 → 集群 → 授权管理。

### 要问什么

- prod 集群的写权限是常开的，还是**每次申请、用完回收**？
- 有没有人能在 prod 上执行 `kubectl delete` 而不留痕？审计日志存多久？
- 前任的账号是否还有效？交接后多久注销？（防止出现"不是我干的"说不清）

### 验收标准

四集群分别跑一遍 `kubectl auth can-i --list`，能说清"我在哪个集群能做什么、不能做什么"。

---

## 第 2 章　集群基础信息

### 摸底清单（四集群各来一遍）

| 项 | 关注点 |
|---|---|
| 集群 ID / 地域 / 可用区 | 跨 AZ 还是单 AZ（单 AZ = 高风险） |
| K8s 版本 | 是否在维护期内；四集群版本是否一致（不一致 → 兼容性坑） |
| 集群类型 | 标准集群 / Serverless 超级节点 / 注册节点（海外节点） |
| 节点池构成 | 数量、机型、CPU/内存、系统盘、是否竞价实例（竞价 = 可能被回收） |
| 网络模式 | **VPC-CNI / Global Router / 混合**（决定 CLB 能否直连 Pod） |
| 容器运行时 | containerd / docker；docker 版本过旧是安全隐患 |
| VPC / 子网 | 网段规划、IP 是否快耗尽（Pod 调度不出来的常见根因） |
| 节点水位 | CPU/内存/磁盘分配率，是否有节点长期 >80% |
| 组件版本 | CoreDNS、CSI、 metrics-server、Ingress Controller 版本 |
| 关键组件 | 有没有装：日志采集、Prometheus、cert-manager、HPA、OPA 等 |

### 怎么查

```bash
kubectl version --short
kubectl cluster-info
kubectl get nodes -o wide
kubectl describe node <node> | head -60      # 看 Allocatable / Allocated / Taints / Conditions
kubectl top node
kubectl get ns
kubectl -n kube-system get pod -o wide       # 看系统组件版本与状态
kubectl api-resources --verbs=list -o name | head -50
```

控制台路径：容器服务 → 集群 → 基本信息 / 节点管理 / 组件管理 / 网络（看网络模式）。

### 要问什么

- 节点是包年包月还是按量/竞价？**竞价节点跑有状态服务吗？**（跑的话是重大隐患）
- 有没有节点打了污点（Taint）专供特定业务？新增业务要怎么选节点？
- Pod IP 网段还剩多少？扩容上限在哪？
- 集群有没有做过升级？上次升级踩了什么坑？

### 验收标准

能报出四集群的：版本、节点数、机型、网络模式、剩余资源水位，并指出"哪个集群最先会资源不够"。

---

## 第 3 章　网络与访问链路

> 按你的排查习惯走：云原生网关 → CLB → CEN 云联网 → NAT → 安全组/CFW → 目标服务。

### 3.1 南北向（外部怎么进来）

| 项 | 要摸清 |
|---|---|
| 接入层类型 | 四集群分别是 CLB Ingress / Nginx Ingress / Kong / TSE 云原生网关？（**可能各不相同，这是常见陷阱**） |
| 域名与证书 | 各环境的域名清单、证书在哪（Secret / 证书管理）、到期时间 |
| CLB 实例 | 数量、类型（公网/内网）、计费方式、监听器与后端健康检查 |
| WAF / CFW | 是否接入、规则谁维护、误拦截怎么处理 |
| DNS | 在哪解析（DNSPod / 云解析）、内网 DNS 是否有自定义域名 |

```bash
kubectl get ingressclass                      # 装了哪些 Ingress 控制器
kubectl get ingress -A -o wide
kubectl get svc -A | grep LoadBalancer        # 找出所有 CLB 型 Service
```

### 3.2 东西向（集群内/跨集群怎么互通）

| 项 | 要摸清 |
|---|---|
| 业务集群 → 中间件集群 | 走内网 CLB？Pod 直连 IP？域名？有没有经过 CEN/对等连接 |
| 跨地域 | 是否跨地域、CEN 带宽包水位、延迟基线 |
| 出公网 | 走 NAT 网关还是节点公网 IP？出网带宽与连接数是否打满过 |
| 服务间调用 | 直连 Service、走注册中心、还是走 Service Mesh（Istio） |
| NetworkPolicy | 有没有启用 Pod 间网络隔离？没启用 = 全通（安全与故障爆炸范围都受影响） |

```bash
kubectl get networkpolicy -A
kubectl get svc -A                            # 看 ClusterIP / ExternalName（ExternalName 常用于指向中间件）
kubectl get endpoints -A | grep -i none       # 空的 Endpoints = 必然 502
```

### 3.3 必做的一项验证

**从业务 Pod 里实测到中间件的连通性**（别只看网络规划图）：

```bash
# 进一个业务 Pod 实测（只读操作）
kubectl -n <ns> exec -it <pod> -- sh
# 在里面分别验：DNS 解析、TCP 连通、HTTP 响应
nslookup <中间件域名>
nc -zv <中间件IP> <端口> -w 3
curl -s -o /dev/null -w "%{http_code} %{time_total}\n" http://<中间件地址>/health
```

### 验收标准

能画出任一外部请求到 Pod 的完整链路，说出每层的排查命令；能说出"中间件集群不可达时，业务会报什么错"。

---

## 第 4 章　工作负载与业务拓扑

### 摸底清单

```bash
kubectl get deploy,sts,ds,job,cronjob -A      # 全部工作负载
kubectl get pod -A -o wide | grep -v Running  # 非 Running 的 Pod（重点看）
kubectl get pod -A --field-selector=status.phase!=Running
```

| 项 | 关注点 |
|---|---|
| 命名空间划分 | 按业务？按团队？按租户？`kube-system` / `kube-public` 里有没有业务东西 |
| 工作负载类型 | Deployment / StatefulSet / DaemonSet / CronJob 各多少，**有没有裸 Pod**（裸 Pod 无自愈能力，是隐患） |
| 副本与 HPA | 关键服务副本数 ≥2？HPA 配了吗？阈值合理吗 |
| 资源配额 | 有没有 ResourceQuota / LimitRange？requests 与 limits 配了吗（没配 → 节点资源抢占） |
| 就绪/存活探针 | 配了吗？探针配置错误是"滚动更新卡住"的第一根因 |
| PDB | 关键服务有没有 PodDisruptionBudget（没有 → 节点驱逐时可能全挂） |
| 有状态服务 | StatefulSet 跑什么？数据在哪？能否重建 |
| CronJob | 有哪些定时任务？失败了会怎样？会不会跟业务高峰撞 |
| 控制器归属 | 哪些是 Helm 管的、哪些是 kubectl apply 的、哪些是**手工创建的**（手工 = 不可复现，最危险） |

```bash
kubectl get hpa -A
kubectl get pdb -A
kubectl get resourcequota,limitrange -A
kubectl get pod -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"\t"}{.metadata.name}{"\t"}{.spec.containers[*].resources}{"\n"}{end}' | head -40
# 找出没有控制器归属的裸 Pod
kubectl get pod -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"/"}{.metadata.name}{"\n"}{end}' | while read p; do
  ns=${p%%/*}; n=${p##*/}
  owner=$(kubectl -n $ns get pod $n -o jsonpath='{.metadata.ownerReferences[0].kind}' 2>/dev/null)
  [ -z "$owner" ] && echo "裸Pod: $p"
done
```

### 要问什么

- 有没有**多租户**？租户之间怎么隔离（命名空间/数据库/独立部署）？
- 哪些 Pod 是**绝对不能重启**的（重启会丢数据或要人工介入）？
- 哪些是**核心链路**（挂了 = S1），哪些是边缘功能？这个分级有没有文档化？

### 验收标准

能说出每个命名空间是干什么的，指出核心链路上的关键服务清单（挂了要立刻响应的那几个）。

---

## 第 5 章　中间件集群专项（这章别人不会给你，但最要命）

### 5.1 先确认隔离模型

这是中间件集群最核心的问题。四种常见模型，风险从高到低：

| 模型 | 说明 | 风险 |
|---|---|---|
| **完全共用** | 三环境连同一个 DB 实例同一个库 | 最高。一次 sit 压测能拖垮生产 |
| 同实例不同库 | 同一个 TDSQL-C 实例，`sit_xxx` / `uat_xxx` / `prod_xxx` 分库 | 高。实例级故障/慢 SQL 仍会互相影响，且权限易串 |
| **同集群不同命名空间** | 每环境一套中间件 Pod | 中。K8s 层面隔离，但节点资源仍共享 |
| 完全独立 | 每环境独立实例 | 低，但成本高 |

**必须问清**：sit 的压测会不会打到生产库？uat 的数据是不是生产脱敏数据？有没有发生过"测试环境操作影响生产数据"的事故？

### 5.2 中间件逐项摸底

| 中间件 | 必问项 |
|---|---|
| **TDSQL-C / MySQL** | 实例规格、连接数上限、慢查询阈值、备份策略与保留期、回档是否演练过、读写分离怎么配、三环境的库如何区分、大表有哪些 |
| **Redis** | 版本、架构（主从/集群）、内存上限与淘汰策略、持久化开关、三环境是否共用（共用则 db index 怎么分）、热 key/大 key 有没有排查过 |
| **消息队列** | 类型（Kafka/RocketMQ/RabbitMQ/CMQ）、topic 清单、消费组、堆积告警阈值、**消息是否会丢**、重复消费怎么处理、死信队列在哪 |
| **注册中心** | Nacos / Consul / 北极星？命名空间与分组划分、服务健康检查机制、有没有出现服务列表脏数据 |
| **ES / 对象存储** | 索引生命周期、磁盘水位、 shard 分配、COS 桶权限与生命周期 |
| **其他** | 有没有定时任务调度中心（XXL-Job）、配置中心（Apollo/Nacos Config）、链路追踪（Jaeger/SkyWalking/APM） |

### 5.3 中间件集群自身的运维边界（很容易扯皮）

- 中间件是**云托管产品**（TDSQL-C、TCR、CMQ）还是**自建在 K8s 里**（自己起 MySQL/Redis Pod）？
- 如果自建：数据存在哪（PVC/CFS/本地盘）？有没有备份？能不能重建？**自建有状态服务 + 无备份 = 定时炸弹**
- 中间件的**升级和扩容谁负责**？有没有 SLA？半夜挂了找谁（云厂商工单 vs 自己人）？

### 5.4 验收标准

能说出中间件集群里每一个组件的：部署形态（托管/自建）、三环境隔离方式、故障影响面、扩容/恢复路径。

---

## 第 6 章　配置、密钥与三环境差异矩阵

### 6.1 配置从哪来（四种常见模式，混用最坑）

1. ConfigMap / Secret（K8s 原生）
2. 配置中心（Nacos Config / Apollo）
3. Helm values（按环境不同的 values 文件）
4. **环境变量写死在 Deployment 里**（最坑，改一个值要改 YAML）

```bash
kubectl get cm -A
kubectl get secret -A
kubectl -n <ns> get deploy <name> -o jsonpath='{.spec.template.spec.containers[*].env}' | head -20
# 找出所有引用了哪些 ConfigMap/Secret
kubectl -n <ns> get deploy -o json | grep -o '"configMapRef":.*' | head
```

### 6.2 必问

- 密钥（数据库密码、API Key、证书）存在哪？有没有进 Git？（**进 Git 是重大安全事故**）
- 改一个配置需要走什么流程？改完是自动生效还是要重启 Pod？
- 有没有配置变更的历史记录？改错了能不能快速回滚？
- **禁止登容器改文件**——这条团队里所有人都遵守吗？有没有人这么干过？

### 6.3 三环境差异矩阵（重点产出，务必填）

> 这张表填完，能避免 80% 的"uat 好好的、prod 就挂了"。

| 配置项 | sit | uat | prod | 差异说明 |
|---|---|---|---|---|
| 镜像 tag 策略 | | | | |
| 数据库地址/库名 | | | | |
| Redis db / 实例 | | | | |
| MQ topic 前缀 | | | | |
| 注册中心 namespace | | | | |
| 域名 | | | | |
| 日志级别 | | | | |
| 资源 requests/limits | | | | |
| 副本数 / HPA | | | | |
| 超时与重试参数 | | | | |
| 限流阈值 | | | | |
| 外部依赖地址 | | | | |
| 特性开关（feature flag） | | | | |

### 验收标准

上表填满，且能解释每一个"不一致"是有意为之还是历史遗留。

---

## 第 7 章　发布与变更流程

> 按你的发版铁律：版本号 → 灰度策略 → 发布步骤 → 观测验证 → 回滚条件，五件缺一不可。

### 7.1 必须问清

| 项 | 问题 |
|---|---|
| 流水线 | 用什么（CNB / Jenkins / GitLab CI / 蓝盾）？配置文件在哪（`.cnb.yml` / `Jenkinsfile`）？ |
| 代码分支 | 分支策略（GitFlow / trunk-based）？sit/uat/prod 分别对应哪个分支？ |
| 版本号 | 有没有语义化版本号？还是用 commit hash / latest？（**用 latest = 无法回滚**） |
| 镜像 | 推到哪个仓库？命名规范？保留策略（旧镜像还留着吗，这是回滚的前提） |
| 部署方式 | Helm / Kustomize / 裸 kubectl apply / ArgoCD 等 GitOps？ |
| 审批 | 谁审批？UAT 验收谁签字？有没有发布窗口？紧急发版走什么流程 |
| 灰度 | prod 怎么灰度（按权重/按 Header/按租户）？有没有金丝雀机制 |
| 数据库变更 | DDL 谁执行？有没有回滚脚本？**加字段和删字段的兼容性怎么保证** |
| 回滚 | 回滚命令是什么？演练过吗？回滚需要多久？数据库变更能不能一起回滚 |
| 发布记录 | 有没有 changelog？最近三次发布分别改了什么、顺不顺利 |

### 7.2 关键风险点

- **数据库变更不可回滚**是最常见的坑：先加可空字段 → 双写 → 切读 → 再删旧字段，这个四步法有没有在用？
- **配置与代码不同步发布**：代码先上、配置后上，中间窗口期会报错。发布顺序约定是什么？
- **prod 有没有"跳过 uat 直接上"的特例**？如果有，是谁批的？

### 7.3 验收标准

能在纸上写出 prod 一次完整发布的每一步命令 + 每一步的回滚命令，并且**真的在 sit 上演练过一遍**。

---

## 第 8 章　数据、存储、备份与灾备

| 项 | 要摸清 |
|---|---|
| 持久化 | 用了哪些 StorageClass、PVC？底层是云硬盘 CBS / CFS / COS / 本地盘？ |
| 有状态数据 | 哪些服务的数据是不能丢的？存哪？ |
| 数据库备份 | 自动备份策略、保留天数、备份在哪、**是否做过恢复演练** |
| 回档能力 | 能回档到任意时间点吗？回档要多久？回档是覆盖还是新建实例？ |
| 跨可用区/地域 | 有没有灾备？RTO/RPO 是多少？有没有人真的测过 |
| 对象存储 | COS 桶清单、权限、生命周期、有没有开启版本控制 |

```bash
kubectl get storageclass
kubectl get pv,pvc -A
kubectl -n <ns> get pvc -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.storageClassName}{"\t"}{.status.capacity.storage}{"\n"}{end}'
```

### 必问（这句一定要问）

> **"我们最近一次真正做过恢复演练是什么时候？恢复成功了吗？"**

没演练过的备份 = 没有备份。这是交接时最该确认、也最常被敷衍的一件事。

### 验收标准

能说清：哪些数据丢了会出大事、它们多久备份一次、恢复需要多久、上一次恢复演练的结果。

---

## 第 9 章　可观测与告警

### 三层监控（按你的方法论）

| 层 | 看什么 | 在哪看 |
|---|---|---|
| 集群/容器层 | 节点 CPU/内存/磁盘、Pod 重启、调度失败、PVC 水位 | 云监控 / Grafana / `kubectl top` |
| 云产品层 | CLB 流量与健康检查、DB 连接数与慢查询、网关 QPS 与错误率、CEN 带宽 | 云监控各产品页 |
| 业务层 | 核心接口成功率、延迟分位、订单/登录等关键业务指标 | Grafana / 自定义埋点 |

### 摸底清单

- 监控大盘在哪？地址多少？有没有**四集群统一视图**？
- 日志在 CLS 吗？日志集/主题怎么划分？索引开了吗？**多久能查到一条线上错误日志**（这是硬指标）
- 有没有链路追踪？能追一个请求跨几个服务吗
- 告警策略：分几档？通知到哪（企微/短信/电话）？有没有恢复通知？有没有收敛（防风暴）？
- 值班：值班表在哪？on-call 要求（多久响应）？升级路径（先找谁、再找谁）？
- 告警有效性：**最近一个月的告警里，有多少是误报？** 误报多 = 真告警会被忽略

```bash
kubectl get pod -A --sort-by=.status.containerStatuses[0].restartCount | tail -20   # 重启最多的 Pod
kubectl get events -A --sort-by=.lastTimestamp | tail -50                           # 最近事件
```

### 验收标准

给你一个告警，能在 5 分钟内判断：影响面多大、是不是误报、去哪查、找谁。

---

## 第 10 章　安全与合规

| 项 | 要摸清 |
|---|---|
| 堡垒机 | 谁有权限、操作是否全程审计、录像保留多久 |
| 安全组/CFW | 南北向/东西向策略谁维护？有没有"0.0.0.0/0 全开"的规则（**重点排查**） |
| WAF | 是否接入？规则模式（观察/拦截）？误拦怎么办 |
| 镜像安全 | 有没有镜像扫描？基础镜像多久没更新？有没有跑 privileged 容器 |
| 密钥管理 | 密钥在哪（Secret/SSM/KMS）？轮换周期？有没有硬编码进镜像 |
| Pod 安全 | 有没有以 root 运行？有没有 hostNetwork/hostPID？ |
| 合规 | 涉及个人信息/等保吗？日志留存要求？审计要求 |

```bash
kubectl get pod -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"/"}{.metadata.name}{"\t"}{.spec.securityContext.privileged}{"\n"}{end}' | grep true
kubectl get psp,psa -A 2>/dev/null
```

### 验收标准

能回答：如果现在发现一个 Pod 被入侵，我能在多久内查到它访问过什么、影响范围多大。

---

## 第 11 章　历史故障、坑与红线

### 必问的历史

- 过去半年出过哪些故障？根因是什么？怎么恢复的？有没有复盘文档？
- 有没有**重复发生过两次以上**的故障？（重复发生 = 根因没解决）
- 最贵的那次故障损失了多少？当时是怎么止损的？
- 有没有"祖传配置"——没人知道为什么这么配、也不敢改的？

### 最容易踩的坑（对照自查）

- [ ] 镜像用 `latest`，导致四环境实际版本不一致
- [ ] 某服务的 ConfigMap 改了但 Pod 没重启，配置没生效
- [ ] 节点资源超卖，高峰期被 OOMKilled
- [ ] 健康检查探针配得太激进，滚动更新时全部被摘除
- [ ] 没配 PDB，节点驱逐时副本全没了
- [ ] 中间件连接数被打满（应用连接池配置不合理）
- [ ] 定时任务在业务高峰跑，抢占资源
- [ ] 日志没开索引，出事了查不到
- [ ] 告警太多，真告警被淹没
- [ ] sit 压测打到生产数据库

### 红线清单（接手后自己立，先问前任有没有）

```
1. 禁止直接 kubectl delete pod -n <prod-ns> 来"重启试试"
2. 禁止登录容器改文件（改了下次发布就没了，且不可追溯）
3. 禁止在业务高峰做变更（除非有灰度）
4. 禁止在没有备份的情况下做数据库 DDL / 删数据
5. 禁止在没有第二人确认的情况下动中间件集群
6. 禁止用生产数据直接灌到 sit/uat（脱敏是底线）
7. 禁止关闭告警（可以临时调整阈值，不能关）
8. 禁止把密钥写进 YAML / Git
```

---

## 附 A：四集群信息回收表（先填这张）

| 项目 | sit | uat | prod | 中间件 |
|---|---|---|---|---|
| 集群 ID | | | | |
| 地域 / 可用区 | | | | |
| K8s 版本 | | | | |
| 集群类型（标准/Serverless） | | | | |
| 网络模式（VPC-CNI/GR） | | | | |
| 节点数 / 机型 | | | | |
| 命名空间清单 | | | | |
| 接入层类型 | | | | |
| 域名 | | | | |
| 工作负载数量 | | | | |
| 部署方式（Helm/kubectl） | | | | |
| 镜像仓库 | | | | |
| 我的权限级别 | | | | |
| 能否独立发版 | | | | |
| 监控大盘地址 | | | | |
| 日志（CLS）主题 | | | | |
| 核心服务清单 | | | | |

## 附 B：Day 1 只读摸底命令集（可放心跑，无写操作）

```bash
# ===== 0. 先确认自己在哪个集群（防误操作第一步）=====
kubectl config current-context
kubectl cluster-info | head -3

# ===== 1. 集群骨架 =====
kubectl version --short
kubectl get nodes -o wide
kubectl top node
kubectl get ns

# ===== 2. 工作负载全景 =====
kubectl get deploy,sts,ds,cronjob -A
kubectl get pod -A -o wide | grep -v Running | grep -v Completed
kubectl get pod -A --sort-by=.status.containerStatuses[0].restartCount | tail -15

# ===== 3. 网络与接入 =====
kubectl get ingressclass
kubectl get ingress -A -o wide
kubectl get svc -A | grep -E 'LoadBalancer|NodePort'
kubectl get endpoints -A -o json | jq -r '.items[] | select(.subsets==null) | "\(.metadata.namespace)/\(.metadata.name) EMPTY"'
kubectl get networkpolicy -A

# ===== 4. 配置与存储 =====
kubectl get cm -A
kubectl get secret -A
kubectl get pv,pvc -A
kubectl get storageclass

# ===== 5. 弹性与约束 =====
kubectl get hpa -A
kubectl get pdb -A
kubectl get resourcequota,limitrange -A

# ===== 6. 健康度 =====
kubectl get events -A --sort-by=.lastTimestamp | tail -50
kubectl get componentstatuses 2>/dev/null

# ===== 7. 权限自查 =====
kubectl auth can-i --list
```

> 建议：把上面整套命令存成 `survey.sh`，四集群各跑一遍，输出存成 `sit.txt` / `uat.txt` / `prod.txt` / `mw.txt`，差异对比用 `diff` 看，能快速发现四环境的不一致。

## 附 C：验收自检（30 题，能答对 25 题算接手完成）

**架构**
1. 用户请求进来的完整链路是什么？每一层断了分别是什么现象？
2. 中间件集群挂了，三个环境分别会怎样？
3. 核心链路上的服务是哪几个？
4. 有没有单点（副本数为 1 的关键服务）？
5. 跨地域调用有哪些？

**操作**
6. 我在四集群分别有什么权限？
7. 怎么发一次 sit？命令是什么？
8. prod 发版谁审批？窗口是什么时候？
9. 回滚命令是什么？演练过吗？
10. 改一个配置项的正确流程是什么？

**故障**
11. 502 怎么排查？第一步看什么？
12. Pod 起不来（ImagePullBackOff/CrashLoopBackOff）怎么排查？
13. 节点 NotReady 怎么办？上面的 Pod 会怎样？
14. 数据库连不上，怎么判断是网络、权限还是连接数？
15. 日志查不到，先查采集还是先查索引？
16. 告警没收到，按什么顺序自查？

**数据与中间件**
17. sit 压测会不会影响 prod？
18. 数据库备份策略是什么？上次恢复演练什么时候？
19. Redis 满了会怎样？淘汰策略是什么？
20. MQ 消息堆积了怎么办？会不会丢消息？
21. 注册中心服务列表脏了怎么清理？

**发布**
22. 版本号规范是什么？能用 latest 吗？
23. 数据库变更怎么保证可回滚？
24. 配置与代码的发布顺序是什么？
25. 灰度怎么做？灰度的观测指标是什么？

**安全与协作**
26. 密钥存在哪？多久轮换？
27. 有没有安全组全开的规则？
28. 值班表在哪？告警发给谁？
29. 出问题先找谁？升级路径是什么？
30. 现有文档在哪？哪些是过期的？

## 附 D：去问前任/组长的问题清单（直接照着念）

**第一轮（30 分钟，建立框架）**
1. 这四个集群大概什么关系？中间件是不是三环境共用？
2. 我目前的权限能做什么？prod 是不是只读？
3. 最核心的几个服务是哪几个？挂了最要命的是哪个？
4. 发一次 prod 要多久、走什么流程、谁审批？
5. 最近一次故障是什么？怎么恢复的？

**第二轮（1 小时，补细节）**
6. 有没有现成的文档/runbook？哪些是可信的、哪些过期了？
7. sit/uat/prod 的配置差异主要在哪几处？
8. 中间件集群是托管还是自建？谁负责扩容和升级？
9. 备份做过恢复演练吗？多久能恢复？
10. 有没有"千万别做"的操作清单？

**第三轮（跟着做）**
11. 带我完整走一次 sit 发布。
12. 带我看一次 prod 的监控大盘和告警。
13. 给我一次真实的故障排查机会，我做你看。

---

> 最后一句：接手期最危险的不是"不懂"，而是"以为自己懂了就去动 prod"。
> 前三周保持只读，把所有疑问记下来，第四周再动手，你会感谢自己。
