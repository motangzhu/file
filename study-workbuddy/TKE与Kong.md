# TKE 容器与云原生网关(Kong)

> 面向:刚入职的技术运维工程师,负责腾讯云 TKE 容器服务 + 云原生网关(Kong),后续接管测试集群 SaaS 平台 UAT/SIT 应用服务与 Kong 网关。
> 目标:8 周内从"零基础 + 公司环境陌生"到"独立值班、独立处理常见故障"。
> 使用方式:文档分为【岗位职责】【学习路线】【技术详解】【实战 SOP】【熟悉公司环境】【向组长确认清单】六大块。建议打印"动作清单"和"向组长确认清单"两节随身用。

---

## 一、你的岗位职责与工作范围

### 1.1 角色定位

你是一名**平台/基础设施运维工程师**,不是开发,也不是 SRE(除非公司混岗)。核心职责是:

- 保证**测试集群(UAT/SIT)的应用服务**和**Kong 网关**稳定运行;
- 承接开发团队的发布、扩容、配置变更需求;
- 处理日常告警、故障、工单;
- 维护网关的路由、限流、灰度、鉴权策略。

一句话:开发把应用部署到 TKE,流量从 Kong 网关进来打到应用,你要保证这条链路不出问题、出了问题能快速恢复。

### 1.2 你负责的资源清单(4 个核心对象)

| 编号 | 资源名 | 类型 | 说明 |
|------|--------|------|------|
| 1 | saas平台-应用服务-UAT | TKE 应用 | UAT 环境的 SaaS 应用(用户验收测试) |
| 2 | saas平台-应用服务-SIT | TKE 应用 | SIT 环境的 SaaS 应用(系统集成测试) |
| 3 | SAAS-UAT-Kong 网关 | Kong 网关 | UAT 环境流量入口 |
| 4 | SAAS-SIT-Kong 网关 | Kong 网关 | SIT 环境流量入口 |

**这 4 个对象就是你的"地盘"。** 上岗第一件事:把这 4 个对象在腾讯云控制台里全部找到,记下集群 ID、网关实例 ID、所在地域、命名空间。

### 1.3 你不负责什么(边界,这点很重要)

- ❌ 生产环境(除非组长明确让你参与,否则不碰)
- ❌ 控制面节点(TKE 托管控制面由腾讯云维护,你只读)
- ❌ 开发代码逻辑(应用 bug 找开发,你只负责"跑起来")
- ❌ 后端中间件(MySQL/Redis 一般有 DBA 或独立运维,你只看应用侧连接)
- ❌ 网络底层(VPC/子网/路由表由网络组管,你只看安全组与 Service)

**边界不清的地方,主动问组长,别替别人做了也不讨好,更别把别人的锅扛了。**

### 1.4 上下游协作关系

```
开发团队 ──提发布需求──> 你(运维)
   │                         │
   │ <──告警/故障通知─────────│
   │                         │
   ↓                         ↓
CI/CD流水线 ──> TKE集群 ──> Kong网关 ──> 测试人员/UAT用户
                  │
                  ├──> DBA(数据库)
                  ├──> 网络组(VPC/SLB)
                  └──> 安全组(证书/WAF)
```

你需要经常打交道的人:**开发(发布需求)、测试(验证环境可用)、DBA(数据库连接问题)、网络组(域名/SLB/证书)、组长(变更审批)**。入职第一周把这些角色和对应的 IM 群、邮箱、工单系统全部加好。

### 1.5 第一个月目标

- 第 1 周末:能登录控制台,找到全部 4 个对象,说清各自在哪。
- 第 3 周末:能在 TKE 里独立完成一次 Deployment 的更新、回滚、扩缩容。
- 第 6 周末:能在 Kong 网关里独立配置一条路由、加一个限流插件、做一次灰度。
- 第 8 周末:能独立响应 UAT/SIT 告警,完成一次故障初步定位与恢复。

---

## 二、8 周学习路线总览

### 路线图

参见对话中的"8 周学习路线图"。4 个阶段:

1. **第 1 周 · 基础夯实**:云原生/K8s 概念、腾讯云控制台熟悉、权限与资源盘点、公司文档库熟悉
2. **第 2-3 周 · TKE 深入**:集群与节点池、工作负载 Deployment、Service/Ingress、配置/存储/日志
3. **第 4-6 周 · Kong 网关**:路由/Service、插件机制、限流/鉴权、灰度发布
4. **第 7-8 周 · 实战接管**:UAT/SIT 应用运维、Kong 网关运维、故障 SOP 演练、独立值班

### 阶段验收标准

| 阶段 | 验收标准(能独立完成) |
|------|----------------------|
| 阶段 1 | 说清 Pod/Service/Ingress/Deployment 是什么;在控制台找到 4 个对象 |
| 阶段 2 | 用控制台完成 Deployment 更新、回滚、扩缩容;看懂 Pod 日志和事件 |
| 阶段 3 | 在 Kong 加一条路由通到后端;加 rate-limiting 插件;做按权重灰度 |
| 阶段 4 | 独立响应 1 个 P2 告警并恢复;独立完成 1 次低风险变更 |

---

## 三、阶段 1:基础夯实(第 1 周)

### 3.1 云原生与 K8s 核心概念(必懂,否则后面全听不懂)

| 概念 | 一句话理解 | 为什么重要 |
|------|-----------|-----------|
| Pod | K8s 最小调度单位,里面跑 1 个或多个容器 | 你的应用最终就是一堆 Pod |
| Deployment | 管 Pod 的"控制器",声明要几个副本、用什么镜像 | 你日常更新的就是 Deployment |
| Service | 给一组 Pod 一个稳定访问入口(IP/域名) | Pod 会重建 IP 变,Service 解决"找得到" |
| Ingress | 七层流量入口(域名→Service) | Kong 网关本质上也是干这个,但要更强大 |
| ConfigMap | 配置(明文) | 应用配置走这里,改配置不用重新打镜像 |
| Secret | 配置(密文,如密码/证书) | 数据库密码、TLS 证书走这里 |
| Namespace | 资源隔离的逻辑分区 | UAT/SIT/各业务线通常分 Namespace |
| Node | 工作节点(一台 CVM) | Pod 调度在 Node 上 |
| PV/PVC | 持久化存储 | 有状态服务(如某些缓存)需要 |
| Label/Selector | 标签选择,把对象关联起来 | Service 怎么找到 Pod?靠 selector |

**学习建议**:不要一上来啃《Kubernetes 权威指南》,看腾讯云官方"TKE 产品文档-产品概述"和 K8s 官网互动教程(https://kubernetes.io/zh-cn/docs/tutorials/)的前 3 节就够入门。

### 3.2 腾讯云控制台与权限体系

**控制台入口**:https://console.cloud.tencent.com/tke2(容器服务)/ https://console.cloud.tencent.com/tse(云原生网关,如果 Kong 是 TSE 托管)

**权限模型**(必须搞清,否则你点了半天发现没权限):
- **主账号**:公司老板/管理员,你碰不到
- **子用户/协作者**:你的账号一般是这个,被授予某些策略
- **CAM 策略**:决定你能看/能改哪些资源。**入职第一件事:确认你的 CAM 权限范围**——能看哪些集群?能改 Deployment 吗?能改 Kong 配置吗?

**控制台常用一级菜单(TKE)**:
- 集群 → 集群列表 → 点集群名进详情
- 集群详情里:节点管理、工作负载、服务与路由、配置管理、存储、日志、监控

**控制台常用一级菜单(TSE 云原生网关,如适用)**:
- 网关实例 → 实例列表 → 点实例名
- 实例详情里:路由、服务、消费者、插件、证书

### 3.3 第 1 周动作清单

- [ ] 找组长要:腾讯云子账号、CAM 权限范围说明、4 个对象的集群/实例 ID 和地域
- [ ] 登录 TKE 控制台,把 UAT 和 SIT 两个集群找到,进集群详情看一遍所有菜单
- [ ] 登录 Kong/TSE 网关控制台,把 UAT 和 SIT 两个网关实例找到
- [ ] 找组长要:公司运维知识库地址(Wiki/Confluence/语雀等)
- [ ] 找组长要:告警群、发布群、值班群的 IM 邀请
- [ ] 找组长要:CI/CD 平台地址(Jenkins/GitLab CI/腾讯 CODING 等)和你的账号
- [ ] 通读:公司"发布流程文档""故障应急预案""值班制度"(如果有)
- [ ] 在本机装好 kubectl(即使你偏好控制台,排障时也得用,见 4.10)并配置 kubeconfig(找组长要测试集群的)
- [ ] 把"向组长确认清单"(本文第十二节)填一遍

---

## 四、阶段 2:TKE 容器服务深入(第 2-3 周)

### 4.1 TKE 集群架构

参见对话中的"TKE 集群架构"图。关键认知:

- **控制面(API Server / etcd / Scheduler / Controller-Manager)由 TKE 托管**,你不运维、也登不进去,出问题提工单找腾讯云;
- **工作节点(Worker)是公司自己的 CVM**,你要管:节点是否 Ready、资源是否够、节点上的 Pod 状态;
- 你的"应用服务"=工作负载(Deployment)+ Service + 配置 + 可能的 Ingress。

### 4.2 集群与节点池

控制台路径:`TKE → 集群 → 选集群 → 节点管理`

**你要掌握**:
- 看节点状态(Ready / NotReady / OutOfDisk)
- 看节点资源(CPU/内存 Request 已分配多少、还剩多少)
- 节点池(NodePool)概念:同类节点组成池,支持自动扩缩容(AS)
- 节点故障处理:NotReady 节点上的 Pod 会被驱逐,你要确认业务有没有受影响

**重点提醒**:测试集群资源往往紧张(贵),多副本扩容可能 Pending,这是正常的——你要看懂"为什么 Pending"(资源不够 vs 镜像拉不下来 vs 调度约束)。

### 4.3 命名空间与资源配额

控制台路径:`集群详情 → 命名空间`

- UAT 和 SIT 可能是**不同集群**,也可能是**同集群不同 Namespace**——先搞清你们公司是哪种(向组长确认);
- 命名空间常有 ResourceQuota(CPU/内存上限),防止某个业务吃光资源;
- 你要能看懂哪个应用在哪个 Namespace,变更前确认 Namespace 别搞错。

### 4.4 工作负载(重点中的重点)

控制台路径:`集群详情 → 工作负载 → Deployment`

**4.4.1 五种工作负载类型**

| 类型 | 用途 | 你常碰到 |
|------|------|---------|
| Deployment | 无状态应用(Web/API) | 90% 是这个 |
| StatefulSet | 有状态应用(需稳定网络标识/存储) | 偶尔(如某些中间件) |
| DaemonSet | 每个节点跑一个(日志采集/监控 agent) | 看,一般不自己管 |
| Job | 一次性任务 | 偶尔(数据迁移) |
| CronJob | 定时任务 | 偶尔(定时报表) |

**4.4.2 Deployment 日常操作(控制台)**

| 操作 | 控制台路径 | 说明 |
|------|-----------|------|
| 更新镜像 | 工作负载→Deployment→详情→更新 Pod→修改镜像版本 | 最常见的发布动作 |
| 调整副本数 | 工作负载→Deployment→详情→更新 Pod→副本数 | 扩缩容 |
| 回滚 | 工作负载→Deployment→详情→修订记录→回滚 | 故障恢复神器 |
| 查看 Pod | 工作负载→Deployment→详情→Pod 管理 | 看 Pod 状态/日志 |
| 查看事件 | 工作负载→Deployment→详情→事件 / Pod 详情→事件 | 排障第一站 |

**4.4.3 Pod 状态判读(背下来)**

| 状态 | 含义 | 下一步 |
|------|------|--------|
| Running | 在跑 | 再看 Ready 列是否就绪 |
| Pending | 没调度上 | 看事件:资源不够?调度约束? |
| ContainerCreating | 创建中 | 等几秒,卡住看事件(拉镜像?挂载?) |
| ImagePullBackOff / ErrImagePull | 镜像拉不下来 | 检查镜像名/Tag/仓库凭证 |
| CrashLoopBackOff | 起来就崩 | 看日志,大概率应用 bug 或配置错 |
| Error | 容器退出非 0 | 看日志 |
| Completed | 正常结束(Job) | 一般不用管 |

### 4.5 Service 与 Ingress

控制台路径:`集群详情 → 服务与路由 → Service / Ingress`

- **Service** 给 Pod 一个稳定访问点。类型:
  - ClusterIP:集群内访问(默认,最常见)
  - NodePort:暴露节点端口(较少)
  - LoadBalancer:腾讯云 CLB(对外暴露,Kong 网关后端常是这种或 ClusterIP)
- **Ingress**:七层路由(域名→Service)。但**你们用了 Kong 网关,可能不用 K8s 原生 Ingress,而是 Kong 的 Route**——这点向组长确认。

### 4.6 配置管理(ConfigMap / Secret)

控制台路径:`集群详情 → 配置管理 → ConfigMap / Secret`

- ConfigMap:明文配置(应用配置文件、环境变量)
- Secret:密文(数据库密码、TLS 证书、镜像仓库凭证)
- 改了 ConfigMap 后,**Pod 不会自动重新加载**(除非配了 reload 或滚动更新),常用做法是触发一次滚动更新让其重新挂载。

### 4.7 存储 PV / PVC

控制台路径:`集群详情 → 存储 → StorageClass / PVC`

- 大多数 SaaS Web 应用**无状态,不用 PVC**;
- 但如果应用要存上传文件、日志、缓存,可能用 PVC(挂 CBS 云硬盘或 CFS 文件存储);
- 你要知道:哪个应用用了 PVC?PVC 是不是 Bound 状态?容量够不够?

### 4.8 日志与监控

**日志**:
- 控制台:`Pod 详情 → 日志`(实时 stdout/stderr,够日常用)
- 事件:`Pod 详情 → 事件`(调度/拉镜像/启动失败的原因多在这)
- 集群级日志:若公司接了 CLS(日志服务),去 CLS 控制台查,支持检索

**监控**:
- TKE 自带监控:`集群详情 → 监控`(Pod CPU/内存/网络)
- 告警:`集群详情 → 告警设置` 或腾讯云监控(云监控)
- 你要确认:**UAT/SIT 的告警发到哪个群?** 看不到告警 = 瞎的。

### 4.9 控制台操作路径速查

| 任务 | 路径 |
|------|------|
| 找集群 | TKE → 集群 |
| 看节点 | 集群 → 节点管理 → 节点 |
| 看应用 | 集群 → 工作负载 → Deployment(选 Namespace) |
| 更新镜像 | Deployment 详情 → 更新 Pod |
| 回滚 | Deployment 详情 → 修订记录 → 回滚 |
| 扩缩容 | Deployment 详情 → 更新 Pod → 副本数 |
| 看 Pod 日志 | Deployment 详情 → Pod 管理 → Pod → 日志 |
| 看事件 | Deployment 详情 → 事件 / Pod → 事件 |
| 改配置 | 集群 → 配置管理 → ConfigMap/Secret |
| 看 Service | 集群 → 服务与路由 → Service |
| 看 Ingress | 集群 → 服务与路由 → Ingress |
| 看监控 | 集群 → 监控 |
| 设告警 | 集群 → 告警设置 |

### 4.10 必会 kubectl 命令(即使偏好控制台,这 10 条要会)

> 你之前的偏好是控制台操作,这没问题。但**排障时控制台不够灵活**,这 10 条命令建议背熟,用得到。

```bash
# 1. 看当前上下文(确认你连的是 UAT 还是 SIT,极其重要!别在生产上敲命令)
kubectl config current-context

# 2. 切换命名空间上下文(避免每次加 -n)
kubectl config set-context --current --namespace=<ns>

# 3. 看 Pod(最常用)
kubectl get pods -n <ns> -o wide
kubectl get pods -n <ns> -l app=<deployment名>

# 4. 看 Pod 详情(卡在 ContainerCreating?看这里)
kubectl describe pod <pod名> -n <ns>

# 5. 看日志
kubectl logs <pod名> -n <ns>
kubectl logs -f <pod名> -n <ns>          # 实时跟随
kubectl logs --previous <pod名> -n <ns>  # 看上一次崩溃前的日志(排 CrashLoop)

# 6. 看 Deployment
kubectl get deploy -n <ns>
kubectl describe deploy <名> -n <ns>

# 7. 更新镜像(命令行发布,慎用,一般走 CI/CD)
kubectl set image deploy/<名> <容器名>=<新镜像> -n <ns>

# 8. 扩缩容
kubectl scale deploy/<名> --replicas=3 -n <ns>

# 9. 回滚
kubectl rollout history deploy/<名> -n <ns>      # 看历史版本
kubectl rollout undo deploy/<名> -n <ns>          # 回上一个
kubectl rollout undo deploy/<名> -n <ns> --to-revision=<n>

# 10. 进 Pod 排查(网络/文件/进程)
kubectl exec -it <pod名> -n <ns> -- bash
# 进不去 bash 就用 sh,再不行用 busybox 诊断
```

**安全铁律**:敲任何 `kubectl apply/delete/edit` 之前,先 `kubectl config current-context` 确认上下文。生产集群的 kubeconfig 不要和测试混在一个 kubeconfig 文件里。

### 4.11 第 2-3 周动作清单

- [ ] 在 UAT 集群找到 saas平台-应用服务-UAT 对应的 Deployment,记录:命名空间、副本数、镜像、所用 Service、ConfigMap、Secret
- [ ] 在 SIT 集群做同样的事
- [ ] 用控制台把某个 Deployment 副本数从 N 改到 N+1,观察 Pod 调度,再改回
- [ ] 用控制台做一次镜像更新(找组长要一个测试镜像),观察滚动更新过程
- [ ] 用控制台做一次回滚(修订记录→回滚)
- [ ] 故意把镜像 Tag 写错,观察 ImagePullBackOff,然后改回
- [ ] 用 kubectl 把上面 10 条命令各跑一遍(在 UAT,SIT 也行,**绝不在生产**)
- [ ] 看一次某个 Pod 的实时日志和事件
- [ ] 找到告警群,确认 UAT/SIT 的告警会发到这里

---

## 五、阶段 3:云原生网关 Kong(第 4-6 周)

### 5.1 Kong 是什么 & 在你的架构里的位置

参见对话中的"UAT 与 SIT 环境链路"图。Kong 是一个**高性能 API 网关**,基于 OpenResty(Nginx + Lua)。在你公司架构里:

- 它是**所有外部流量的入口**(uat.company.com / sit.company.com 先到 Kong);
- Kong 根据**路由规则**把流量转发到后端 TKE 里的应用 Service;
- Kong 通过**插件**提供限流、鉴权、灰度、日志、熔断等能力。

**先确认你们用的是哪种 Kong**(向组长确认,影响控制台操作方式):
- **方案 A:自建 Kong**(部署在 TKE 或 CVM 上,用 kong.conf + Admin API 管理)——你要学 kong 命令和 Admin API;
- **方案 B:TSE 云原生网关**(腾讯云托管的 Kong,有控制台)——你主要在控制台操作;
- **方案 C:Kong + Konga/Deck 等管理面板**。

下文以**方案 B(TSE 云原生网关,有控制台)**为主讲,同时给命令行对照。

### 5.2 Kong 核心对象(必须背熟)

| 对象 | 作用 | 类比 |
|------|------|------|
| **Service** | 上游服务抽象(名+协议+host+port) | "后端服务"的定义 |
| **Route** | 路由规则(host/path/method),把请求匹配到 Service | "哪些请求归我管" |
| **Upstream** | 负载均衡目标组(多个 target) | Service 的"后端池" |
| **Target** | Upstream 里的一个具体后端地址(IP:port) | 后端池里的一台 |
| **Consumer** | 消费者(可挂凭证做鉴权) | 谁来调 |
| **Plugin** | 插件,挂在 Service/Route/Consumer/全局 | 限流/鉴权/灰度… |

**流量走向**:`请求 → Route 匹配 → 命中 Service → Upstream 选 Target → 转发到 TKE Pod`

### 5.3 路由与 Service

**控制台(TSE)路径**:`网关实例 → 路由 / 服务`

**配一条新路由的标准动作**:
1. 先建 **Service**:填后端协议(http/https)、host(TKE Service 名或 IP)、port、path;
2. 再建 **Route**:填匹配规则(host=api.uat.company.com、path=/user、methods=GET/POST)、关联上一步的 Service;
3. 保存后用 `curl` 测试:`curl -H "Host: api.uat.company.com" http://<网关IP>/user`

**TKE 后端如何对接 Kong**:
- 如果 Kong 在 TKE 集群内:Service host 用 TKE Service 名(如 `user-svc.default.svc.cluster.local`);
- 如果 Kong 在集群外:Service host 用 TKE LoadBalancer Service 的 CLB VIP 或外部域名;
- 用 Upstream + Target 做动态后端(灰度常用),不要写死 IP。

### 5.4 插件机制(这是 Kong 的灵魂)

**插件作用域优先级**(从大到小):`全局 > Consumer > Route > Service`(具体谁覆盖谁以官方为准,常用最小作用域)。

**你一定会碰到的插件**:

| 插件 | 作用 | 典型场景 |
|------|------|---------|
| **rate-limiting** | 限流(按秒/分/时 QPS) | 保护后端、防止压测打挂 |
| **key-auth / jwt / hmac** | 鉴权 | API 对外开放要 token |
| **acl** | 访问控制(Consumer 组) | 某接口只许 A 系统调 |
| **request-termination** | 直接拒绝(返回固定状态码) | 紧急下线某接口 |
| **request-transformer** | 改请求头/路径 | 兼容老接口 |
| **response-transformer** | 改响应 | 加统一响应头 |
| **correlation-id** | 给请求加唯一 ID | 全链路追踪 |
| **prometheus** | 暴露指标 | 接监控 |
| **file-log / http-log** | 日志 | 访问日志落库 |
| **canary** / 用 Upstream weight | 灰度 | 金丝雀发布 |

### 5.5 常用插件配置详解

**5.5.1 限流(rate-limiting)**

控制台:服务/路由 → 插件 → 新建 → 选 rate-limiting → 填:
- `minute`(每分钟 N 次)或 `second`/`hour`
- `policy`(local/redis/cluster,集群多副本用 redis/cluster)
- `limit_by`(consumer/ip/credential,一般 consumer 或 ip)
- `fault_tolerant`(true:后端挂了不限流,false:严格限流)

效果:超限返回 429。

**5.5.2 鉴权(jwt 示例)**

1. 全局或 Service 上启用 jwt 插件;
2. 建 Consumer,给 Consumer 生成 JWT credential(含 key/secret/algorithm);
3. 客户端请求带 `Authorization: Bearer <jwt>`;
4. Kong 校验通过才转发,否则 401。

**5.5.3 灰度(金丝雀)**

两种方式:
- **Upstream + Target weight**:一个 Upstream 配多个 Target(如 v1 权重 90、v2 权重 10),改权重做灰度;
- **canary 插件**:按比例/按 header 路由到不同 Upstream。

**5.5.4 紧急下线(request-termination)**

某接口出问题要紧急挡掉:加 request-termination,返回 503,几秒钟生效,比改后端代码快得多。**记进应急预案**。

### 5.6 Kong 与 TKE 集成要点

- 后端 Service 用 TKE Service 名(Coredns 解析)或 CLB VIP;
- 健康检查:Upstream 配 `healthchecks.active`,Kong 主动探活,挂了的 Target 自动摘除;
- 长连接:注意 Kong upstream 的 keepalive 配置,高并发场景要调;
- 超时:Route/Service 的 `connect_timeout`/`read_timeout`/`write_timeout`,慢接口要调大但别太大。

### 5.7 控制台操作路径速查(TSE)

| 任务 | 路径 |
|------|------|
| 看网关实例 | TSE → 云原生网关 → 实例 |
| 看路由 | 实例详情 → 路由 |
| 建路由 | 路由 → 新建 |
| 看服务 | 实例详情 → 服务 |
| 建服务/Upstream | 服务 → 新建 |
| 加插件 | 路由/服务 → 插件 → 新建 |
| 看消费者 | 实例详情 → 消费者 |
| 证书 | 实例详情 → 证书 |
| 看监控 | 实例详情 → 监控 |
| 看日志 | 实例详情 → 日志 / CLS |

### 5.8 必会命令(自建 Kong 场景)

```bash
# 1. 列路由
curl -s http://localhost:8001/routes | jq

# 2. 列服务
curl -s http://localhost:8001/services | jq

# 3. 建服务
curl -s -X POST http://localhost:8001/services \
  -d name=user-svc -d url=http://user-svc:8080

# 4. 建路由(关联 service)
curl -s -X POST http://localhost:8001/routes \
  -d "name=user-route" -d "hosts[]=api.uat.company.com" \
  -d "paths[]=/user" -d "service.id=<上面 service 的 id>"

# 5. 加限流插件到路由
curl -s -X POST http://localhost:8001/routes/<route_id>/plugins \
  -d name=rate-limiting -d config.minute=100

# 6. 紧急下线(加 request-termination)
curl -s -X POST http://localhost:8001/routes/<route_id>/plugins \
  -d name=request-termination -d config.status_code=503

# 7. 测试
curl -H "Host: api.uat.company.com" http://<网关IP>/user -i
```

### 5.9 第 4-6 周动作清单

- [ ] 找组长确认:Kong 是自建还是 TSE 托管?控制台地址?管理员账号?
- [ ] 在 UAT Kong 上找到现有的路由列表,记录每条路由 → Service → 后端
- [ ] 在 SIT Kong 做同样的事
- [ ] 在 UAT 上**新建一条测试路由**(找组长要一个测试后端),用 curl 验证通
- [ ] 给这条路由加 rate-limiting(minute=10),用脚本压测验证返回 429
- [ ] 给这条路由加 request-termination,验证返回 503,然后删掉插件
- [ ] 用 Upstream + 两个 Target 做一次 50/50 灰度,观察流量分布
- [ ] 看一次网关监控(QPS、延迟、4xx/5xx),确认告警阈值
- [ ] 在告警群里确认能看到 Kong 的告警

---

## 六、阶段 4:实战接管(第 7-8 周)

### 6.1 UAT 与 SIT 环境职责

- **UAT(用户验收测试)**:测试人员驱动,模拟真实用户场景,稳定性要求较高,**别频繁发版影响测试**;
- **SIT(系统集成测试)**:开发/集成测试驱动,变更频繁,允许短暂不稳定;
- 两者**资源隔离**(不同集群或同集群强隔离),配置变更不要串环境;
- 你要清楚:**当前是 UAT 还是 SIT 在发版?** 看发布日历/群通知。

### 6.2 日常巡检 SOP(每天早晚各一次)

**TKE 侧**:
- [ ] 集群节点是否全部 Ready(`kubectl get nodes` 或控制台节点管理)
- [ ] UAT/SIT 的核心 Deployment 副本数是否符合预期、有无 Pod 异常
- [ ] 是否有 Pod 处于 CrashLoop/Pending 超过 5 分钟
- [ ] 监控大盘有无红色指标(CPU/内存接近上限)
- [ ] 告警群是否有未处理告警

**Kong 侧**:
- [ ] 网关实例状态正常
- [ ] 路由数量是否和预期一致(防误删)
- [ ] 监控:QPS、p99 延迟、5xx 比例是否正常
- [ ] 告警群是否有 Kong 告警

### 6.3 发布与变更(详见第七、八节)

### 6.4 故障处理 SOP

**总原则**:`先恢复,后定位`。能用回滚/限流挡住的,先挡住,再慢慢查根因。

**故障处理 4 步**:
1. **确认影响范围**:哪个环境?哪个应用?影响了谁(测试?用户?)?
2. **快速恢复**:回滚 Deployment / 加 request-termination 挡接口 / 扩容 / 切流量;
3. **通知**:按公司预案通知组长和相关方(影响测试进度就说一声);
4. **定位与复盘**:事后看日志/监控找根因,写复盘文档。

### 6.5 值班与交接

- 接班:看交接文档/群,确认有无遗留变更、未恢复故障、待办;
- 交班:把当前进行中的变更、异常 Pod、未结工单写清楚;
- 值班期间不在岗要找人顶,别让告警没人响应。

---

## 七、UAT/SIT 应用服务运维详解

### 7.1 应用服务部署形态

典型形态:`Deployment(2 副本)+ ClusterIP Service + ConfigMap(配置)+ Secret(密码/凭证)`,可能挂 PVC(有状态部分)。

### 7.2 发布流程(从代码到上线,典型流程)

```
开发提 MR/PR → CI 流水线构建镜像 → 推镜像仓库 → (审批) → 触发 CD →
更新 TKE Deployment 镜像 → 滚动更新 → 健康检查 → 完成
```

**你的角色**:
- 开发找你提"发布申请"(工单/群),你**审批**并**触发或监督**发布;
- 发布前确认:镜像 Tag 对不对?哪个环境?有无数据库变更?是否需要配灰度?是否通知测试暂停用?
- 发布中盯滚动更新,看 Pod 是否 Ready、健康检查是否通过;
- 发布后确认:接口能通、监控正常,通知测试可以用了;
- 出问题:立即回滚。

### 7.3 版本回滚

- **控制台**:Deployment 详情 → 修订记录 → 选版本 → 回滚;
- **命令**:`kubectl rollout undo deploy/<名> -n <ns>`;
- 回滚后确认 Pod 全部 Ready、新版本镜像 Tag 回到上一个;
- 如果回滚也起不来(配置/数据已变更),升级为故障,找开发。

### 7.4 配置变更

- 改 ConfigMap/Secret 后,触发滚动更新让其重新挂载(改 Deployment 加个无害 annotation 即可触发);
- **不要**直接 `kubectl edit` 生产配置,走变更流程留痕;
- 敏感信息(密码)只走 Secret,不在 ConfigMap 或镜像里硬编码。

### 7.5 扩缩容

- 控制台:Deployment 详情 → 更新 Pod → 副本数;
- 命令:`kubectl scale deploy/<名> --replicas=N -n <ns>`;
- 扩容后 Pending?看节点资源、是否触发节点池扩容;
- 缩容注意:有状态服务别乱缩,可能丢会话。

### 7.6 日志查询

- 实时:控制台 Pod 日志 或 `kubectl logs -f`;
- 历史/检索:CLS 日志服务(若接入),按 Pod 名/应用名/级别/时间检索;
- 崩溃前日志:`kubectl logs --previous`(CrashLoop 必杀)。

### 7.7 监控告警响应

- 收到告警:**先判断真假和影响**(误报?影响谁?);
- 进控制台看 Pod 状态、监控曲线、最近变更;
- 常见告警应对:
  - Pod 重启多 → CrashLoop,看日志找应用侧;
  - CPU/内存高 → 扩容或查是不是死循环/内存泄漏;
  - 5xx 多 → 看应用日志 + Kong 日志,定位是网关还是后端;
  - 节点 NotReady → 看 CVM 状态、提工单/找组长。

---

## 八、Kong 网关运维详解

### 8.1 网关日常运维

- 巡检路由数量、插件状态、证书有效期;
- 监控 QPS、延迟、错误率;
- 定期看访问日志,关注异常请求(大量 401/403?被刷了?)。

### 8.2 路由配置 SOP

1. 开发提需求:"新接口 /api/v2/order 上线,后端 order-svc:8080";
2. 你建 Service(order-svc,http,host=order-svc,port=8080);
3. 建 Route(hosts=api.uat.company.com,paths[]=/api/v2/order,关联 service);
4. 加必要插件(鉴权、限流);
5. 测试:curl 验证 200 且打到正确后端;
6. 通知开发/测试可用;
7. 记录变更(变更台账)。

### 8.3 限流策略配置

- 了解后端能扛多少(问开发/压测);
- 配 rate-limiting,留 buffer(后端能扛 1000,网关限 800);
- 按业务维度配(consumer 维度 > ip 维度);
- 配告警:限流触发频繁要告警(可能被刷或后端太慢)。

### 8.4 灰度发布(金丝雀)

- 新版本 v2 镜像上线,先 10% 流量;
- Upstream 配两个 Target:v1 weight=90、v2 weight=10;
- 观察 v2 错误率/延迟,无异常逐步 30→50→100;
- 全量后下掉 v1;
- 出问题:把 v2 weight 调 0,流量全回 v1(秒级恢复)。

### 8.5 鉴权配置

- API 对外开放必加鉴权(jwt/key-auth);
- 对内服务(只给已知系统调)用 acl + key-auth 做白名单;
- **别把无鉴权的接口暴露到公网**。

### 8.6 证书与域名管理

- TLS 证书在 Kong 证书管理里配(关联到 Route 的 host);
- **证书有效期要监控!** 证书过期 = 接口全挂,设告警提前 30 天;
- 域名解析(到网关 CLB)和网络组协调,你一般不直接管 DNS,但要知道链路。

### 8.7 网关故障排查

| 现象 | 可能原因 | 排查 |
|------|---------|------|
| 全部 502 | 后端全挂 / Service 指错 / 网络不通 | 看后端 Pod 状态、Kong upstream target health |
| 偶发 502 | 后端慢/连接超时 | 调 read_timeout,看后端是否 GC/重启 |
| 大量 429 | 限流触发 | 看是否被刷,调阈值 |
| 大量 401/403 | 鉴权问题 | 看 Consumer 凭证是否失效 |
| 404 | 路由没匹配 | 检查 host/path 配置 |
| 延迟突增 | 后端慢或网关压力 | 看监控、扩容、看上游 |
| 网关本身挂 | 实例故障 | TSE 找腾讯云/自建看 Pod |

---

## 九、熟悉公司环境的快速动作

### 9.1 入职第一周必做(按天)

| 天 | 必做 |
|----|------|
| D1 | 领电脑、开账号(腾讯云子用户、IM、邮箱、工单、CI/CD、Wiki) |
| D2 | 找组长要:4 个对象清单、权限范围、告警群、文档库地址 |
| D3 | 在控制台把 4 个对象全找到,记录集群/实例 ID、地域、命名空间 |
| D4 | 通读公司发布流程、故障预案、值班制度文档 |
| D5 | 装 kubectl + 配测试集群 kubeconfig;跑通 `kubectl get pods`;填"向组长确认清单" |

### 9.2 资源盘点清单(向组长索要,填空)

```
UAT 集群:
  集群 ID:__________  地域:__________
  集群类型:托管/独立  网络模式:VPC-CNI/GlobalRouter
  saas平台-应用服务-UAT 所在命名空间:__________
  核心 Deployment 清单:__________
  kubeconfig 来源:__________

SIT 集群:
  集群 ID:__________  地域:__________
  saas平台-应用服务-SIT 所在命名空间:__________
  kubeconfig 来源:__________

SAAS-UAT-Kong 网关:
  类型:TSE托管/自建  实例 ID:__________
  控制台地址:__________  管理账号:__________
  入口域名:__________  CLB VIP:__________
  路由数量:___  关键路由清单:__________

SAAS-SIT-Kong 网关:
  (同上)__________

告警:
  告警群:__________  值班群:__________
  告警接收人是否含我? □

CI/CD:
  平台:__________  账号:__________
  UAT 发布流水线:__________
  SIT 发布流水线:__________

文档:
  运维 Wiki:__________
  发布流程文档:__________
  故障预案:__________
```

### 9.3 关键文档与知识库

向组长要这些文档(有就先读):
- 测试环境架构图
- 发布流程/变更管理流程
- 值班制度与交接模板
- 故障应急预案
- Kong 路由台账(哪些接口对应哪个后端)
- 历史故障复盘记录

### 9.4 工具与权限申请清单

- [ ] 腾讯云子账号 + CAM 权限(TKE 读写、TSE 读写、CLS 只读、CBS 只读)
- [ ] kubectl + kubeconfig(UAT、SIT 各一份)
- [ ] Kong/TSE 控制台账号
- [ ] CI/CD 平台账号(至少能触发发布)
- [ ] CLS 日志服务访问权限
- [ ] 监控大盘访问权限(云监控 / Grafana,若有)
- [ ] IM 群:告警群、发布群、值班群、运维大群
- [ ] 工单系统账号

### 9.5 关键人物与沟通

- **组长**:变更审批、疑难升级、权限申请;
- **开发对接人**:每个核心应用的开发 owner(发版找谁、bug 找谁);
- **测试负责人**:UAT 排期、发布协调;
- **DBA**:数据库变更、连接问题;
- **网络组**:域名、SLB、证书、VPC;
- **腾讯云支持**:控制面故障提工单。

**建议**:入职第二周建一个"运维联系人表"(姓名/角色/IM/电话/职责),随身带。

---

## 十、运维规范与 SOP

### 10.1 变更管理流程

- **任何变更前**:写变更单(变更内容、影响范围、回滚方案、时间窗);
- **审批**:测试环境低风险可组长口头批,中高风险走工单;
- **执行**:双人操作(一人执行一人复核)或留操作日志;
- **验证**:变更后跑一遍核心接口 + 看监控;
- **回滚预案**:变更前就备好回滚步骤,出问题立刻回滚。

**变更红线**:
- 测试环境也别在没人盯的时候大改(周末/深夜除非紧急);
- 同一环境并行变更要协调,别互相踩;
- 改 Kong 全局插件尤其要小心,影响所有路由。

### 10.2 告警响应流程

```
告警进群 →
  看是不是我的(环境/资源对不对) →
    不是 → @ 对应人,转走;
    是 →
      看影响面(谁受影响) →
        通知相关方(测试/开发/组长) →
          快速恢复(回滚/挡流/扩容/重启) →
            验证恢复 →
              留日志和现场信息 →
                事后复盘找根因 →
                  写复盘文档(若达到复盘阈值)
```

**告警响应时效**(参考,按公司规定):
- P1(大面积不可用):5 分钟内响应,立即升级;
- P2(部分功能不可用):15 分钟内响应;
- P3(单点异常):30 分钟内响应。

### 10.3 故障复盘

- 达到复盘阈值(如影响超 30 分钟 / 影响多人 / P1P2)就开复盘;
- 复盘三段:**时间线 / 根因 / 改进项**(谁负责什么时候做完);
- 不追责,追问题,避免下次再犯。

### 10.4 文档编写规范

- 变更留痕:变更单/工单 + 群通知;
- 路由台账:每加/改一条 Kong 路由,更新台账(接口、后端、负责人、插件);
- 故障复盘:模板(时间线/影响/根因/恢复/改进);
- 环境地图:维护一份"UAT/SIT 应用清单 + Kong 路由清单 + 关键依赖",定期更新。

---

## 十一、进阶能力培养(8 周后)

### 11.1 K8s 进阶
- Pod 调度(taint/toleration/affinity)、优先级与抢占;
- HPA/VPA/CronHPA 自动扩缩容;
- NetworkPolicy、PSP/PSS 安全策略;
- Operator / Helm 包管理(公司用 Helm 的话要会)。

### 11.2 Kong 进阶
- 自定义插件(Lua)、Deck 声明式配置;
- Kong 的 Service Mesh(若公司上);
- 高并发调优(worker/连接数/超时)。

### 11.3 可观测性体系
- 指标(Prometheus + Grafana);
- 日志(CLS / Loki);
- 链路追踪(Jaeger / SkyWalking,配合 Kong correlation-id)。

### 11.4 自动化运维
- 用脚本/平台固化发布、巡检、回滚;
- IaC(Terraform 管腾讯云资源,若公司用)。

### 11.5 安全合规
- 镜像扫描、RBAC 最小权限、Secret 轮转、证书自动化、WAF 接入。

---

## 十二、向组长确认的问题清单(入职第一周填完)

> 这是最实用的一节。把这些问题问清楚,能少走 80% 弯路。建议打印出来,带去和组长过一遍。

### 12.1 资源/环境类
1. 我负责的 4 个对象,各自的集群 ID / 实例 ID / 地域 / 命名空间是什么?
2. UAT 和 SIT 是两个集群还是同集群两个 Namespace?
3. Kong 是自建还是 TSE 托管?控制台地址?账号怎么申请?
4. 测试集群的节点规格、数量、是否开了节点池自动扩缩容?
5. CI/CD 用什么(Jenkins/GitLab CI/CODING)?发布流水线在哪?我有什么权限?
6. 镜像仓库地址?拉镜像凭证在哪个 Secret?
7. 日志接了 CLS 吗?日志集/主题名是什么?我有检索权限吗?
8. 监控/告警用什么(云监控/Grafana)?告警发到哪个群?我加了吗?

### 12.2 流程/规范类
9. 发布流程是怎样的?谁审批?谁执行?谁验证?
10. 变更管理流程?哪些变更要工单?哪些口头?
11. 值班制度?我什么时候开始值班?交接模板在哪?
12. 故障应急预案文档在哪?有哪些预案?
13. 测试环境的可用性要求是什么 SLA?允许发版时间窗?

### 12.3 责任边界类
14. 后端 MySQL/Redis 谁管?出了连接问题找谁?
15. 域名/SLB/证书谁管?我要加域名走什么流程?
16. 应用 bug 找开发,开发 owner 清单在哪?
17. 控制面故障提工单流程?有腾讯云 TAM(技术客户经理)吗?
18. 生产环境我能看吗?能改吗?(明确边界)
19. 紧急情况下我能做哪些操作不用请示?(回滚?重启 Pod?挡接口?)

### 12.4 学习/成长类
20. 公司有没有内部 K8s/Kong 培训资料?
21. 前任/同事有没有留下的交接文档?
22. 我的考核指标是什么?第一个月 expected 什么?

---

## 附录 A:常用控制台路径速查表(TKE + TSE)

### TKE
| 操作 | 路径 |
|------|------|
| 集群列表 | 容器服务 → 集群 |
| 节点管理 | 集群详情 → 节点管理 → 节点 |
| 节点池 | 集群详情 → 节点管理 → 节点池 |
| 工作负载 | 集群详情 → 工作负载 → Deployment/StatefulSet/… |
| 更新镜像 | Deployment 详情 → 更新 Pod |
| 回滚 | Deployment 详情 → 修订记录 → 回滚 |
| Pod 日志 | Deployment 详情 → Pod 管理 → Pod → 日志 |
| Pod 事件 | Pod 详情 → 事件 |
| Service | 集群详情 → 服务与路由 → Service |
| Ingress | 集群详情 → 服务与路由 → Ingress |
| ConfigMap | 集群详情 → 配置管理 → ConfigMap |
| Secret | 集群详情 → 配置管理 → Secret |
| PVC | 集群详情 → 存储 → PersistentVolumeClaim |
| 监控 | 集群详情 → 监控 |
| 告警 | 集群详情 → 告警设置 |

### TSE 云原生网关
| 操作 | 路径 |
|------|------|
| 实例列表 | TSE → 云原生网关 → 实例 |
| 路由 | 实例详情 → 路由 |
| 服务/Upstream | 实例详情 → 服务 |
| 消费者 | 实例详情 → 消费者 |
| 插件 | 路由/服务 → 插件 |
| 证书 | 实例详情 → 证书 |
| 监控 | 实例详情 → 监控 |
| 日志 | 实例详情 → 日志 / CLS |

---

## 附录 B:必会命令速查

### kubectl(10 条,见 4.10)
- current-context / set-context
- get pods / describe pod
- logs / logs -f / logs --previous
- get/describe deploy
- set image / scale
- rollout history / undo
- exec -it -- bash

### Kong Admin API(自建场景,见 5.8)
- GET /routes /services
- POST /services /routes /plugins
- curl 测试请求

---

## 附录 C:故障排查决策树(打印贴桌前)

```
告警/报错来了
  │
  ├─ 应用 5xx / 慢
  │    ├─ 是单接口还是全量?
  │    │    ├─ 单接口 → Kong 路由/插件问题?后端某 Pod 问题?
  │    │    └─ 全量 → 后端全挂?网关挂?网络?
  │    ├─ 看 Kong 监控(5xx 来源是网关还是上游)
  │    ├─ 看 TKE Pod 状态(重启?CrashLoop?Pending?)
  │    ├─ 看 Pod 日志
  │    └─ 快速恢复:回滚 / 挡接口 / 扩容 / 重启 Pod
  │
  ├─ Pod CrashLoop
  │    ├─ kubectl logs --previous
  │    ├─ 应用 bug?配置错?依赖连不上?
  │    └─ 找开发,或回滚到上一版
  │
  ├─ Pod Pending
  │    ├─ kubectl describe pod
  │    ├─ 资源不够 → 扩节点 / 减副本 / 清理
  │    ├─ 镜像拉不下 → 检查 Tag / 仓库凭证
  │    └─ 调度约束 → 看 nodeSelector/toleration
  │
  ├─ 节点 NotReady
  │    ├─ 看 CVM 状态(腾讯云控制台)
  │    ├─ SSH 进不去 → 提工单
  │    └─ Pod 会自动驱逐,确认业务影响
  │
  └─ Kong 502 / 全挂
       ├─ 看后端 Pod 是否全挂
       ├─ 看 upstream target health
       ├─ 看 Service host/port 是否对
       └─ 网关实例本身 → TSE 控制台 / 提工单
```

---

## 附录 D:学习资源

### 官方文档(首选,权威)
- TKE 产品文档:https://cloud.tencent.com/document/product/457
- TSE 云原生网关:https://cloud.tencent.com/document/product/1364
- Kubernetes 官方(中文):https://kubernetes.io/zh-cn/docs/
- Kong 官方文档:https://docs.konghq.com/
- Kong Hub(插件库):https://docs.konghq.com/hub/

### 入门教程
- 腾讯云大学 TKE 课程(免费)
- K8s 官网互动教程(前 3 节足够入门)
- 《Kubernetes in Action》(进阶书)

### 实操练习
- 你自己之前的测试环境(单节点 S5)可以拿来跑实验,但**别在上面做生产相关操作**;
- 公司 UAT/SIT 在不影响的时段也可以练手,**练前通知组长**。

---

## 写在最后

这份文档是框架 + 通用知识,**真正的"公司具体情况"要靠你向组长和同事问出来填空**。技术不难,难的是把"公司怎么用这套技术"搞清楚。第一周多问少做,第二周开始动手,第八周你应该能独立值班了。

关键三句话:
1. **先恢复,后定位** —— 故障来了别钻研根因,先让业务能用。
2. **变更必有回滚预案** —— 没想好怎么回滚,就别动。
3. **边界不清就问** —— 别替别人做,也别扛别人的锅。

祝顺利上手。
