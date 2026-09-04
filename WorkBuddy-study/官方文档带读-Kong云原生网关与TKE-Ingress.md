# 云原生网关 Kong × TKE Ingress 官方文档带读

- 抓取日期：2026-09-04
- 覆盖文档两篇（腾讯云官方原文）：
  1. 《使用 Kong Ingress Controller》—— 最近更新 2026-07-23（product/1826）
  2. 《Ingress Controllers 说明》—— 最近更新 2026-01-23（product/457）
- 阅读目的：搞清「托管 Kong 怎么接入 TKE」与「TKE 侧 Ingress 有哪几条路、怎么选」之间的关系

---

## 0. 读前一句话定位

- 腾讯云托管网关（内核就是 Kong）本身是**集群外部的网关**，要管理集群内流量，得把 TKE 集群"关联"给它、以 Kong Ingress Controller（KIC）模式工作 → **文档一**讲的就是这个关联操作。
- TKE 集群自己有 Ingress 体系，共三条路：**CLB 型**（默认、最简）、**Nginx**（自建或应用市场）、**Others**（自装任意 Controller）→ **文档二**讲的就是这三条路的定位。
- 托管 Kong 的 KIC 模式，本质上是 Others 路线里的"**托管实现**"——关联动作在控制台点，不用自己在集群里装 Controller。

注意：这篇文档当前挂载的产品页标题为「**云原生智能网关**」，控制台导航仍是 TSF → 云原生网关，产品命名近期有变动迹象，以控制台实际为准。

---

## 1. 文档一：使用 Kong Ingress Controller

### 1.1 解决什么问题

KIC 让 Kong 监听容器集群的资源变化（Service、Ingress、插件），自动把流量配置同步到网关，免去人工管理。Kong 的插件、健康检查、负载均衡能力通过它作用于 Kubernetes Service。

### 1.2 前提条件（两步）

1. 已创建云原生网关实例（文档 1826/134765）
2. 已购买 TKE 标准集群 或 TKE Serverless 集群

### 1.3 启用：控制台路径

TSF 控制台 → 云原生网关 → 云原生网关 → 目标实例详情 → 左侧 **Ingress** → 立即关联容器集群 → 选择集群 → 确定

关键参数：

| 参数 | 官方说明 |
|---|---|
| 网络前提 | 与网关实例网络连通：同 VPC，或用云联网 CCN / 对等连接打通 |
| Ingress 版本 | 支持 **2.7.0 / 2.12.0 / 2.5.0 / 1.3.4** |
| 多集群 | **仅 Ingress 2.7.0 支持关联多容器集群**（2.12.0 虽在支持列表，但官方原文未给它多集群能力） |
| IngressClass | 默认 `kong`，支持自定义，用来标识网关实例 |

启用后验证：服务路由 → 服务 → 看是否自动生成对应 Service；进服务详情 → 服务信息页签，看是否有节点信息。

### 1.4 Ingress 资源两种写法

| 维度 | v1beta1 写法 | v1 写法 |
|---|---|---|
| apiVersion | `extensions/v1beta1` | `networking.k8s.io/v1` |
| 指定 class | annotation：`kubernetes.io/ingress.class: kong` | spec 字段：`ingressClassName: kong` |
| 插件注解 | —（示例未涉及） | `konghq.com/plugins` |
| backend | `serviceName` / `servicePort` | `service.name` / `service.port.number` |
| pathType | 无 | `Prefix` |

v1 写法示例（新集群一律用这个）：

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: demo-v1
  annotations:
    konghq.com/plugins: "httpbin-auth"
spec:
  ingressClassName: kong
  rules:
  - http:
      paths:
      - path: /demo-v1
        pathType: Prefix
        backend:
          service:
            name: nginx
            port:
              number: 80
```

官方提示：两种 apiVersion 的详细区别见 Kong 官方文档（ingress-versions 对比）。`extensions/v1beta1` 的 Ingress 在 K8s 1.22+ 已被移除，存量资源需迁移。

### 1.5 停止与影响

实例详情 → 基本信息 → Kong Ingress Controller 卡片 → **解除关联**。

影响（官方原文）：停止后 Kong 不再监听容器集群变化，资源变更无法同步到网关实例，**通过网关访问容器服务可能出现异常**。属变更影响面较大的操作，慎做。

### 1.6 带读点评

这篇是托管 Kong 对接集群的"上岗手册"，能回答你两个实际判断：

- "一套托管网关能不能管我的多个 TKE 集群？" → 能，但**只有选 Ingress 2.7.0 时支持多集群**。
- 注意别把两层版本混了：这里说的 2.7.0/2.12.0 是 **Ingress（KIC）版本**；创建网关实例时选的 2.4.1/2.5.1 是 **Kong 引擎版本**，是两回事。

---

## 2. 文档二：Ingress Controllers 说明

### 2.1 三条路线

**应用型 CLB（TKE 自带）**
基于腾讯云 CLB 实现的 TKE Ingress Controller。CLB 将流量经 NodePort 转发至 Pod（CLB 直连 Pod 时直接转发）。一条 Ingress 配置绑定一个 CLB 实例（IP）。适合仅需简单路由管理、对 IP 收敛不敏感的场景。

**Nginx Ingress Controller**
基于开源 ingress-nginx 的容器化部署（集群内跑 Nginx 反代），CLB 后面加一层代理。通过 Annotations 扩展原生 Ingress 能力。适合对接入层路由有更多诉求、有 IP 地址收敛诉求的场景。

**Others 类型**
一句话带过：需指定 IngressClass，自行安装对应的 Ingress Controller。—— 自建 KIC、以及托管 KIC 都属于这一类。

### 2.2 NginxIngress 组件已停更（时效信息）

官方原文：容器服务扩展组件 NginxIngress 基于开源 ingress-nginx 提供安装服务，核心代码完全遵循开源版本；**近期已停止对扩展组件 NginxIngress 的版本更新和维护**。兼容性不受影响，仍可通过**自建方式或 TKE 应用市场**继续使用 Nginx Ingress。
公告链接：cloud.tencent.com/document/product/457/108517

含义：别再按旧教程在 TKE 里"安装 NginxIngress 扩展组件"——那条路官方不维护了。

### 2.3 官方功能对比表（转述原文）

| 模块 | 功能 | 应用型 CLB | Nginx Ingress Controller |
|---|---|---|---|
| 流量管理 | 支持协议 | http, https | http, https, http2, grpc, tcp, udp |
| | IP 管理 | 一条 Ingress 一个 IP（CLB） | 多条 Ingress 一个 IP，地址收敛 |
| | 特征路由 | host、URL | 更多：header、cookie 等 |
| | 流量行为 | 不支持 | 支持重定向、重写等 |
| | 地域感知负载均衡 | 不支持 | 不支持 |
| 应用访问寻址 | 服务发现 | 单 Kubernetes 集群 | 单 Kubernetes 集群 |
| 安全 | SSL 配置 | 支持 | 支持 |
| | 认证授权 | 不支持 | 支持 |
| 可观测性 | 监控指标 | 支持（需在 CLB 中查看） | 支持（云原生监控） |
| | 调用追踪 | 不支持 | 不支持 |
| 组件运维 | — | 关联 CLB 已托管，集群内仅需运行 TKE Ingress Controller | 需集群内运行 Nginx Ingress Controller（控制面 + 数据面） |

### 2.4 带读点评

这张表就是"集群内选型"的核心决策表：

- 只做简单 host/path 路由转发 → **CLB 型**够用且最省事（默认）。
- 需要 http2/grpc/tcp/udp 协议、header/cookie 路由、重定向重写、认证授权 → CLB 型给不了，上 **Nginx** 或 **Kong**。
- 两条路都只做**单集群**服务发现——要跨集群统一入口，TKE 这套原生体系本身不提供，这正是托管 Kong（2.7.0）这类外部网关的增量价值。

---

## 3. 两篇合起来的判断框架

| 问题 | 答案 |
|---|---|
| 托管 Kong 在 TKE Ingress 体系里算什么 | Others 路线的托管实现（控制台关联 KIC），能力上限远高于 CLB / Nginx（完整插件生态：认证、限流、灰度、镜像等） |
| 什么信号选托管 Kong | 已有 / 计划建 TSE 网关实例；要多集群统一入口（仅 2.7.0）；要网关级插件治理且不想自己运维 |
| 什么信号留在集群内方案 | 无托管实例；单集群；追求完全 GitOps、版本自控；只做纯路由转发（CLB / Nginx 已够） |
| 自建 KIC vs 托管 KIC | 版本自主（开源已 3.x）vs 版本受限（官方只给 2.x 列表）；自担运维 vs 付实例费 |
| Kong 引擎版本 vs Ingress 版本 | 引擎版本在创建实例时定（官方参考 2.4.1 / 2.5.1）；Ingress(KIC) 版本在关联集群时体现（2.7.0 / 2.12.0 / 2.5.0 / 1.3.4），两者是两套版本体系 |

---

## 4. 与工作区《Kong 与 TKE Ingress 选型手册》第 9 章的核对结论

手册第 9 章原有"三个必须向腾讯云确认的点"，本次抓原文核实：

| 待确认点 | 今日核实结果 | 状态 |
|---|---|---|
| KIC 版本落后 | 官方支持列表现为 2.7.0 / 2.12.0 / 2.5.0 / 1.3.4（较手册多了 2.12.0），仍是 2.x 主线，落后开源 3.x 判断维持 | 结论确认，版本列表需补 |
| 多集群限制 | 官方原文（2026-07-23 更新）仍写「仅 Ingress 2.7.0 支持关联多容器集群」；新增的 2.12.0 未获多集群能力 | 结论确认成立 |
| 新购白名单限制 | 本文档未涉及，需另找实例创建 / 购买指南确认 | 维持待确认 |

新增时效（手册第 3 章相关）：TKE 扩展组件 NginxIngress 已停止官方维护，详见公告 457/108517。

---

## 5. 延伸阅读（均为本次核实的真实链接）

| 主题 | 链接 |
|---|---|
| 创建云原生网关实例（前提条件） | cloud.tencent.com/document/product/1826/134765 |
| 创建云原生 API 网关实例（API 层：引擎版本 2.4.1/2.5.1、产品版 TRIAL/STANDARD/PROFESSIONAL、规格、VPC） | cloud.tencent.com/document/api/1364/96757 |
| CLB 类型 Ingress 详情 | cloud.tencent.com/document/product/457/45685 |
| Nginx 类型 Ingress 详情 | cloud.tencent.com/document/product/457/50502 |
| NginxIngress 扩展组件停更公告 | cloud.tencent.com/document/product/457/108517 |
| Kong 官方：Ingress 版本（v1beta1 vs v1）区别 | docs.konghq.com/kubernetes-ingress-controller/latest/concepts/ingress-versions/ |

---

## 6. 读后三句话

1. 托管 Kong 进 TKE 只有一个核心动作：控制台关联集群，Ingress 资源写 `ingressClassName: kong`。
2. 多集群是硬门槛：官方支持列表里**只有 KIC 2.7.0 能关联多集群**，其余版本（含 2.12.0）只能单集群。
3. TKE 默认 CLB 型最省事、Nginx 组件已停更但可自装，要网关级能力（认证/限流/灰度/多集群入口）才轮到 Kong。
