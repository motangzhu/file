# CNB 三个仓库的构建配置与部署流程讲解

> 本文档用于熟悉 `d:/jinbiCNB` 下三个交付仓库的代码结构、构建配置与部署流程。
> 这三个仓库属于同一套「金智 SAAS 平台」的 CI/CD 体系，按发布域拆分为：后端/大数据、AI 组件、前端 Web 应用。

- 仓库根目录：`d:/jinbiCNB`
- 三个仓库：`cnb-file`、`saas-k8s-config`、`saas-k8s-frontend-config`

---

## 一、总览：三个仓库的分工

| 仓库 | 定位 | 服务对象 | 关键产出 |
|------|------|----------|----------|
| `cnb-file` | 大数据/SAAS 后端的**镜像构建 + K8s 部署** | 后端微服务、大数据组件、xxl-job、seata | 带 commit 号的 Docker 镜像 + K8s 资源 |
| `saas-k8s-config` | **AI 组件（网关/向量库/工作流）部署 + 网关源码构建** | Higress AI 网关、Qdrant、deer-flow、Argilla 等 | 渲染后的 K8s 资源 + 跳板机编译的网关镜像 |
| `saas-k8s-frontend-config` | **前端 Web 应用部署** | `saas-frontend-*` 各类前端站点 | 渲染后的 K8s Service + Deployment |

三者共用同一套设计哲学：**`deploy.sh` + `configs/*.properties` + `templates/*.yaml` 配置驱动部署**，通过 `envsubst` 渲染模板、`kubectl apply` 部署、再 `rollout status` 等待滚动更新完成并验证。

---

## 二、仓库一：`cnb-file`（后端/大数据构建部署）

目录结构：

```
cnb-file/
├── project_bigdata/            # 大数据服务镜像构建
│   └── ycdata-cnb-build.sh     # 大数据镜像打包器（核心构建脚本）
├── k8s_build_template/         # 通用 K8s 部署模板
│   ├── saas-deploy/            # 最完整、最典型的通用部署器
│   │   ├── deploy.sh           # 主部署脚本（22KB）
│   │   ├── services/           # 41 个后端服务，每个一个目录 + service-config.properties
│   │   ├── configs/            # 通用 ConfigMap 模板、环境配置 envs/
│   │   └── k8s/                # service/deployment/pvc 模板
│   ├── saas-deploy-prod/       # prod 环境的同版副本（deploy.sh 内容一致）
│   ├── seata-deploy/           # Seata 分布式事务部署
│   ├── xxl-job-admin/          # 单服务轻量部署
│   └── ...（多个 *.sh、*.yaml、*.properties）
└── project_djpt/ project_saas/ project_xuanlan/ ...   # 各业务线的 K8s yaml 清单
```

### 2.1 构建脚本：`project_bigdata/ycdata-cnb-build.sh`

作用：把大数据各组件**从源码构建成带 commit 版本号的 Docker 镜像并推送到腾讯云镜像仓库 TCR**，做完镜像校验。

用法：

```bash
bash ycdata-cnb-build.sh <服务名> <commit> <短commit>
# 例: bash ycdata-cnb-build.sh datasource abc123...def 1a2b3c4
```

支持的服务（case 分支）：`datasource`、`scheduler`、`dts-backend`、`dts-engine`、`frontend`、`datatransfer`、`platform`。

关键能力：

- **文件锁**（`flock` + `exec 9>/var/lock/...`）：保证同机同时只有一个构建在跑。
- **源码克隆** `clone_source`：克隆指定仓库并切到指定 commit。
- **依赖注入** `clone_dependency`：拉取公共依赖仓库（如 `ycdata-common-backend`），用 Docker `--build-context` 注入构建。
- **前端特殊处理**：`frontend` 在 `node:22-alpine` + pnpm 容器内 install 依赖、类型检查、再 `build:prod`。
- **推送校验** `push_and_verify`：push 后重新 pull 校验 digest 与 revision 标签，确保推上去的镜像可追溯、可用。
- `platform` 服务一次构建网关（scg）、devcenter 后端，并把官方 Prometheus 镜像转存到私有仓库。

本质：这是给 CNB（cnb.jinbizhihui.com）流水线用的**镜像打包器**，产出带 commit 号的镜像。

### 2.2 通用部署脚本：`k8s_build_template/saas-deploy/deploy.sh`

作用：根据配置和模板，**动态生成 K8s 资源（ConfigMap / Service / PVC / Deployment）并部署，等待滚动更新完成并验证**。

用法：

```bash
bash deploy.sh <服务名:版本> [环境] [部署模式]
# 例: bash deploy.sh saas-iam:1.0.0 uat stable
```

- 环境（`ENVIRONMENT`）：`sit` / `uat` / `prod`（默认 `sit`），同时决定命名空间 `saas-${ENVIRONMENT}`。
- 模式（`DEPLOY_MODE`）：`stable` / `canary`（影响副本数）。

`deploy.sh` 主流程（`main` 函数）：

1. `validate_input`：校验服务名格式、服务目录 `services/<服务名>` 与 `service-config.properties` 存在，模式合法。
2. `load_configurations`：读取 `services/<服务>/service-config.properties` + `configs/envs/<环境>-config.properties`，拼出完整镜像地址（默认 `saas-service-tcr.kehuan.cloud/saas/<镜像名>:<tag>`），导出副本数、资源限制、PVC 容量（默认 10Gi）、Spring profile、Service 类型（默认 ClusterIP）等。
3. `generate_k8s_resources`：`envsubst` 渲染 `bootstrap-configmap.yaml`、`service-service.yaml`、`service-pvc.yaml`、`service-deployment.yaml` 到 `k8s/generated/`；Service/Deployment 做 `kubectl --dry-run` 语法校验。
4. `deploy_resources`：命名空间不存在才建；apply ConfigMap（始终更新）；Service 不存在才建；PVC apply（支持扩容，首次创建等 Bound）；Deployment 始终更新。
5. `wait_for_deployment`：三阶段等待——① Deployment 资源创建 → ② `kubectl rollout status`（最多 5 次轮询、每次 30s）→ ③ Pod 全部 Running 验证。
6. `verify_deployment`：打印 Deployment / Service / Pod / 镜像 / ReplicaSet 状态做最终核对。

配置加载 `safe_load_config`：自动转换 CRLF（Windows 换行符）、过滤注释与空行、只认合法的 `key=value`，并做必要变量校验。

### 2.3 其他部署脚本

- `xxl-job-admin/deploy.sh`：轻量单服务部署，`kubectl apply` + `set image` 更新，适用 xxl-job-admin 调度控制台。
- `seata-deploy/seata-deploy.sh`：部署 Seata 分布式事务的同类脚本。
- `saas-deploy-prod/deploy.sh`：与 `saas-deploy/deploy.sh` 内容一致，是 prod 环境独立副本。
- `project_*/`：各业务线的 K8s yaml 清单（djpt/saas/xuanlan/kehai/investment/works/middleware 等），多为直接 `kubectl apply` 用的静态清单。

### 2.4 cnb-file 构建/部署流程

```
源码(git commit)
   │  ycdata-cnb-build.sh（仅大数据）
   ▼
Docker 镜像 + TCR 推送 + digest 校验
   │
服务配置 services/<svc>/service-config.properties + 环境 envs/<env>.properties
   │  deploy.sh
   ▼
envsubst 渲染模板 → k8s/generated/*.yaml
   │
kubectl apply（ns/ConfigMap/Service/PVC/Deployment）
   │
rollout status 等待 + 验证
```

---

## 三、仓库二：`saas-k8s-config`（AI 组件部署 + 网关源码构建）

目录结构：

```
saas-k8s-config/
├── docs/                       # 文档
└── opa/                        # AI 平台（OPA）部署配置
    ├── deploy.sh               # 核心通用部署器（改进版，含 namespace 校验）
    ├── deploy-person-distillation.sh   # 双端（backend/frontend）部署包装器
    ├── deploy-qdrant.sh        # Qdrant 向量库部署
    ├── deploy-go.sh            # 轻量 Go 服务部署（stable/canary）
    ├── deploy-argilla.sh / deploy-deer-flow.sh / deploy-workbuddy.sh / deploy-workspace-service.sh
    ├── deploy-wasm-plugin.sh / deploy-ai-gateway.sh  # AI 网关相关
    ├── setup-ai-gateway-build-env.sh   # 跳板机构建依赖安装（Go≥1.24 等）
    ├── build-ai-gateway.sh [git-ref]   # 跳板机源码编译网关镜像
    ├── run-ai-gateway-cnb-deploy.sh    # CNB 流水线入口（选 source/official 模式）
    ├── setup-ai-jump-disk.sh           # 跳板机数据盘挂载到 200G（防写满系统盘）
    ├── patches/console-svcfix/build-console-image.sh  # 控制台镜像补丁
    ├── configs/<镜像名>/<env>.properties   # 每服务每环境的配置（108 个）
    └── templates/              # K8s yaml 模板
```

### 3.1 通用部署器 `opa/deploy.sh`（相对 cnb-file 的改进）

与 `cnb-file/saas-deploy/deploy.sh` 同宗但做了增强（注释中记录了踩坑修复）：

- 生成的文件名带 `ENVIRONMENT`（`*-<env>-stable-*.yaml`），避免 test/prod 共用文件名互相覆盖导致 namespace 冲突。
- 新增 `assert_yaml_namespace` 校验：渲染出的 YAML 中 `metadata.namespace` 必须与目标 `NAMESPACE` 一致，否则直接报错退出。
- Deployment 模板可被 properties 里的 `DEPLOYMENT_TEMPLATE` 覆盖（AI 集群 Go 服务用带 imagePullSecrets 的模板）。
- 默认环境 `uat`，Service 默认 `NodePort`。
- 服务的是 OPA Policy Handler 类后端服务。

### 3.2 各 AI 组件专用部署脚本

套路一致（读 `configs/<服务>/<env>.properties` → `envsubst` 渲染 → `kubectl apply` → 等 rollout）：

- `deploy-qdrant.sh`：部署 Qdrant 向量库（官方镜像转推 TCR），渲染 StatefulSet + PVC + NodePort Service，等 `statefulset/qdrant` ready。
- `deploy-go.sh`：Go 服务（如 `version-notify`），支持 stable/canary 两套副本，canary 验证通过后需再用 stable 发布。
- `deploy-person-distillation.sh`：`both/backend/frontend` 三种 target，分别滚 backend / frontend，按 ENV 切 `ai-app-*` kubectl context。
- `deploy-argilla.sh` / `deploy-deer-flow.sh` / `deploy-workbuddy.sh` / `deploy-workspace-service.sh`：各类 AI 应用同构部署。
- `deploy-wasm-plugin.sh` / `deploy-ai-gateway.sh`：AI 网关 WASM 插件与 Higress 网关部署。

### 3.3 AI 网关「跳板机源码构建」链路（与 cnb-file 最大区别）

这些脚本在**跳板机**上把 AI 网关（Higress）从源码完整编译成镜像再入 Kind 集群：

- `setup-ai-gateway-build-env.sh`：幂等安装构建依赖（Go≥1.24、make 等）。
- `build-ai-gateway.sh [git-ref]`：从 CNB rsync 的源码做 submodule → prebuild → `make docker-build` → `kind load`（或 ctr import）进本地 Kind 集群，stdout 仅输出镜像 tag。
- `run-ai-gateway-cnb-deploy.sh <BUILD_SOURCE> <TAG> <REF> <CNB_COMMIT> <ENV> <MODE>`：CNB 流水线入口，选 `source`（源码构建）或 `official`（官方镜像 tag）模式拿到镜像 tag，再调 `deploy-ai-gateway.sh` 部署。
- `setup-ai-jump-disk.sh`：跳板机运维，把 Docker/containerd 数据目录 bind 到 200G 数据盘 `/data`，带 fstab 持久化、幂等、先停服 rsync 再挂载，防系统盘写满。

### 3.4 saas-k8s-config 构建/部署流程

```
AI 服务镜像
   ├─ 官方镜像: run-ai-gateway-cnb-deploy.sh → official 模式取 tag → deploy-ai-gateway.sh
   └─ 源码构建: setup-ai-gateway-build-env → build-ai-gateway（rsync 源码→make→kind load）→ deploy-ai-gateway
其他 AI 组件: configs/<svc>/<env>.properties + templates → deploy-*.sh → kubectl apply → rollout status
```

---

## 四、仓库三：`saas-k8s-frontend-config`（前端 Web 应用部署）

目录结构：

```
saas-k8s-frontend-config/
└── saas-frontend-deploy/
    ├── deploy.sh               # 唯一部署脚本（19.9KB）
    ├── templates/
    │   ├── deployment-template.yaml
    │   └── service-template.yaml
    └── configs/                # 75 个 .properties（21 个前端服务 × 多环境）
        ├── saas-frontend-saas-basic-platform/
        ├── saas-frontend-address-manage-h5/
        ├── saas-frontend-billing-system/
        ├── saas-frontend-work-order/
        └── ...（共 21 个前端服务目录，每目录含 saas-prod/saas-uat/... 等 env 文件）
```

### 4.1 部署脚本 `saas-frontend-deploy/deploy.sh`

作用：把 **SAAS 前端 Web 应用** 部署到 K8s（Service + Deployment），是配置驱动的通用部署器。

用法：

```bash
./deploy.sh <镜像名:版本> <环境> [部署模式]
# 例:
./deploy.sh saas-frontend-saas-basic-platform:v1.0.0-prd saas-prod stable
```

参数：

- 镜像名（如 `saas-frontend-saas-basic-platform`）→ 决定去 `configs/<镜像名>/` 读配置。
- 环境（必填，同时作为命名空间）：`saas-prod` / `saas-tenant-prod` / `saas-dev` / `saas-sit` / `saas-uat`。
- 模式：`stable` / `canary`（canary 取 `REPLICAS_CANARY`、stable 取 `REPLICAS_STABLE`）。

主流程（`main`）：与 cnb-file 的 `saas-deploy/deploy.sh` 一致——`validate_input` → `load_configurations` → `generate_k8s_resources` → `deploy_resources` → `wait_for_deployment` → `verify_deployment`。

特点 / 注意事项：

- **配置粒度极细**：75 个 `.properties` = 多个前端服务 × 5 个环境，每服务每环境一套配置。
- **安全配置加载**：自动转 CRLF、只认合法 `key=value`、端口类变量不包引号（当整数处理）。
- **Ingress 不在脚本里管**：`usage()` 注释明确「Ingress 配置已改为在腾讯云控制台手动创建」——脚本只管 Service + Deployment，域名/路由在云控制台配。
- **Service 默认 `LoadBalancer`**：前端需对外暴露，用腾讯云 CLB（不同于 AI 集群的 NodePort）。
- **命名空间即环境**：`saas-prod` 既是环境又是 K8s namespace，靠此约定隔离多套环境。

模板片段（`templates/deployment-template.yaml`）：

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${SERVICE_NAME}-${VERSION}
  namespace: ${NAMESPACE}
spec:
  replicas: ${REPLICAS}
  template:
    spec:
      containers:
      - name: ${SERVICE_NAME}
        image: ${FULL_IMAGE_NAME}
        imagePullPolicy: Always
        ports:
        - containerPort: ${SERVICE_PORT}
        resources:
          requests: { cpu: ${CPU_REQUEST}, memory: ${MEMORY_REQUEST} }
          limits:   { cpu: ${CPU_LIMIT},   memory: ${MEMORY_LIMIT} }
```

### 4.2 saas-k8s-frontend-config 部署流程

```
前端镜像（已在别处构建）
   │  deploy.sh <镜像名:版本> <环境> <模式>
   ▼
configs/<镜像名>/<环境>.properties + templates/*.yaml
   │  envsubst 渲染 → generated/
   ▼
kubectl apply（ns/Service/Deployment）→ rollout status → 验证
   │  （Ingress 由腾讯云控制台手动维护）
```

---

## 五、三个仓库的结构共同点（快速记忆）

1. **配置驱动**：`<服务>/<环境>.properties` 决定镜像、副本、资源、端口、Service 类型。
2. **模板渲染**：`envsubst` 填充 `templates/*.yaml` 生成 `generated/` 下真实 YAML。
3. **安全部署**：命名空间不存在才建、Service 不存在才建、Deployment 始终 apply 更新、PVC 支持扩容、rollout 等待 + 最终验证。
4. **灰度支持**：`stable` / `canary` 两套副本与资源名。

差异点：

| 维度 | cnb-file | saas-k8s-config | saas-k8s-frontend-config |
|------|----------|-----------------|--------------------------|
| 是否有镜像构建 | 有（大数据 ycdata） | 有（AI 网关跳板机源码构建） | 无（镜像在别处） |
| Service 默认类型 | ClusterIP | NodePort | LoadBalancer |
| 默认环境 | sit | uat | 必填（无默认） |
| 额外能力 | CFS PVC、ConfigMap | 网关源码编译、数据盘运维 | Ingress 走云控制台 |

---

## 六、常见操作速查

```bash
# 后端服务部署
cd d:/jinbiCNB/cnb-file/k8s_build_template/saas-deploy
bash deploy.sh saas-iam:1.0.0 uat stable

# 大数据镜像构建
cd d:/jinbiCNB/cnb-file/project_bigdata
bash ycdata-cnb-build.sh datasource <commit> <短commit>

# AI 网关（源码模式）部署
cd d:/jinbiCNB/saas-k8s-config/opa
bash run-ai-gateway-cnb-deploy.sh source <TAG> <REF> <CNB_COMMIT> <ENV> <MODE>

# 前端部署
cd d:/jinbiCNB/saas-k8s-frontend-config/saas-frontend-deploy
./deploy.sh saas-frontend-saas-basic-platform:v1.0.0-prd saas-prod stable
```