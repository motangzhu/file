# 服务路由与 Ingress：两世界概念速查

- 版本：2026-09-04
- 适用：正在熟悉 TKE 集群与 Kong 网关（TSE 托管版或自建）的对象模型，搞不清 Service / Ingress / 路由 / 服务 / 服务来源各自作用的人
- 配套：同名 HTML 文件内含两张链路图（K8s 世界转发链、Kong 命中链），本文用文字链表达

---

## 0. 核心认知：你在两个世界的界面里看东西

| 界面 | 属于哪个世界 | 对象 |
|---|---|---|
| TKE 集群「服务与路由」 | **K8s 世界**（集群内部） | Service、Ingress 是 Kubernetes 原生对象，描述**集群内流量怎么转发** |
| Kong 网关「服务路由」 | **网关世界**（集群外部） | 路由、服务、服务来源是 Kong 自己的配置对象，描述**网关收到请求后转给哪个后端** |

两边都叫"服务 / 路由"，**但不是同一个东西**——同名不同物，这是所有混乱的根源。

---

## 1. K8s 世界：TKE「服务与路由」里谁在干活

```
Ingress 资源(规则声明)  →  Ingress Controller(执行进程)  →  Service(稳定入口)  →  Pod(真正干活)
```

| 站点 | 是什么 | 类型 | 一句话作用 |
|---|---|---|---|
| **Ingress 资源** | 你写的一条规则：域名/路径 → 指向哪个 Service | 配置文件 | 只是一张"规则纸"，**自己不转发** |
| **Ingress Controller** | 集群内真正接收流量、按 Ingress 规则转发的进程 | 运行进程 | 规则的实际执行者（TKE 里 = CLB 型控制器 / Nginx Ingress / 其他） |
| **Service** | 一组 Pod 的稳定入口 | 配置文件 | 名字 + 虚拟 IP 恒定，Pod 死了换 IP 也不影响访问；按 SELECTOR 标签认 Pod，均衡分发到各副本 |
| **Pod** | 跑业务容器的副本 | 运行进程 | 真正干活的，可以被随时杀死重建 |

记忆点：
- **Ingress 是声明，Controller 才是执行者**——Ingress 资源没有 Controller 读它，就是一张废纸。
- **Service 的作用是抗 Pod 死亡**——谁要访问这组 Pod，只认 Service 这个名字。
- 判断"集群用了哪种 Ingress"：看集群里跑的是哪个 Ingress Controller（`kubectl get ingressclass` / `kubectl get deploy -A | grep -i ingress`）。

---

## 2. 网关世界：Kong「服务路由」三件套

```
请求 → 路由(入口匹配) → 服务(后端抽象) → 服务来源(发现后端) → 后端实例(真正干活)
```

| 菜单 | 对应 Kong 对象 | 一句话作用 | 看什么 |
|---|---|---|---|
| **路由** | Route | **入口匹配规则**：host / path / header 满足才放行，不匹配直接 404 | 协议、host、路径、是否 HTTPS、指向哪个服务 |
| **服务** | Service | **后端抽象**：这个逻辑后端连谁、用什么协议、超时多久、重试几次 | 绑定的服务来源、后端地址/名称、端口 |
| **服务来源** | Upstream / 来源插件 | **后端从哪发现**：K8s 集群（按命名空间 + Service 名发现）、Nacos、静态 IP | 关联的集群、命名空间、健康检查 |

⚠️ 注意：菜单从上到下是「路由 / 服务 / 服务来源」，**不等于请求命中顺序**。请求实际是**从路由进、经服务、落到服务来源发现的后端**——别被菜单顺序误导。

实际作用一句话：`服务来源`告诉网关"后端机器在哪找"，`服务`把一组后端包成逻辑后端，`路由`决定"什么请求转给这个逻辑后端"。三层合起来才构成一个完整转发入口。

---

## 3. 同名不同物：对照表

| 概念 | K8s 世界 | Kong 网关世界 |
|---|---|---|
| 入口规则 | Ingress 资源（由 Ingress Controller 执行） | 路由 Route |
| 后端抽象 / 稳定入口 | Service（按标签认 Pod） | 服务 Service（绑服务来源） |
| 后端发现 | 集群内天然按 SELECTOR 发现 | 服务来源（K8s / Nacos / 静态） |

---

## 4. 为什么「Kong 里的 Ingress 没用到」——完全正常

Kong 对接 Kubernetes 有**两条路，二选一**：

**路线 A：服务来源模式（多数场景在用）**
控制台「服务来源」关联 TKE 集群 → 建「服务」时选集群里的 Service → 建「路由」配域名路径。
→ 配置全部在 Kong 控制台完成，**K8s 集群里的 Ingress 资源 Kong 根本不看**。所以"Kong 的 Ingress 功能空置"不是漏配，是这条路不需要它。

**路线 B：KIC 模式（Kong Ingress Controller）**
把 Kong 关联为集群的 Ingress Controller → 在 K8s 里写 Ingress 资源（`ingressClassName: kong`）→ Kong watch 并自动生成路由/服务。
→ 此时才用到 Kong 的 Ingress 功能，配置源头在 K8s 侧。

### 现象对照（典型场景）

| 观察 | 含义 |
|---|---|
| Kong「服务路由」三个菜单都有东西 | 走了**路线 A**，Kong 是独立网关，自带配置在管理流量 |
| Kong 的 Ingress 没用到 | 没启用 KIC（路线 B）——**正常，两条路线二选一** |
| TKE 集群的 Service / Ingress 都有用到 | 集群**自己的**入口链路（CLB 型或 Nginx Ingress → Service → Pod）在工作，**和 Kong 是两套并行的体系** |

⚠️ 推论（重要）：路线 A 下 **Kong 不 watch 业务集群的 Ingress**。所以"业务集群的 Ingress 由谁执行"，要看业务集群里跑的是哪个 Ingress Controller，而不是 Kong。这两件事别混成一个。

---

## 5. 怎么看才能记住：三问框架

看任何对象（无论 K8s 还是 Kong），只问三件事：

1. **它在请求链路哪一段？** 入口规则？后端抽象？稳定地址？——对号入座到第 1、2 节的站点。
2. **谁创建它？** K8s YAML / 控制台手点 / 别的控制器自动生成——来源决定你该去哪改。
3. **流量穿过它之后去了哪？** 看它的"指向字段"，顺着指向继续追。

控制台里每条记录都有指向字段（Ingress 的 BACKEND、Kong 路由的"指向服务"）。**顺着指向一路点下去，就是在重放请求旅程**——看"进去了"的标志，是看到一条记录就下意识想追它的下一跳。

---

## 6. 动手追链（最快固化，逐条手敲）

选一条真实链路，三步走完（假设已切到目标集群与命名空间）：

```bash
kubectl get ingress -A -o wide
```

看 `HOSTS` / `PATH` / `BACKEND` 三列 = 第 1 站。挑一条认识的，记下 BACKEND 是哪个 Service。

```bash
kubectl -n <命名空间> get svc <上一步的backend名> -o wide
```

看 `SELECTOR` 和 `CLUSTER-IP` = 第 2 站。Service 靠 SELECTOR 认 Pod——这就是"名字稳定、按标签分发"的实锤。

```bash
kubectl -n <命名空间> get pods -l <上一步的SELECTOR内容> -o wide
```

第 3 站：看到真正跑业务的几个 Pod 副本。

三步 = 一次完整旅程重放：**Ingress(规则) → Controller(隐含执行者) → Service(稳定入口) → Pod(干活)**。Kong 侧同理：挑一条路由 → 看指向的服务 → 点进服务看绑定的服务来源与后端。

---

## 7. 一句话总记

- **Ingress 是规则纸，Controller 是执行者，Service 是稳定入口，Pod 是干活的。**
- **Kong 服务路由：路由是门禁，服务是路线图，服务来源是通讯录。**
- **两套体系并行，别用"Kong 的 Ingress 空置"判断"集群 Ingress 失效"。**
