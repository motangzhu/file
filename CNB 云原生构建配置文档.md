# CNB 云原生构建配置文档

## 1. 简介

云原生构建（Cloud Native Build，CNB）是腾讯云提供的声明式 CI/CD 平台。其核心配置文件为 `.cnb.yml`，存放于代码仓库根目录，遵循 **「配置即代码」** 原则。

**核心优势**：

- 配置变更可通过 Pull Request 流程管理，适合开源协作
- 构建流程与源代码同步版本控制，确保透明度和变更可追溯
- 采用 YAML 格式，支持嵌套结构和键值对，清晰表达复杂配置

---

## 2. 配置文件说明

| 规范项   | 说明               |
| -------- | ------------------ |
| 文件名   | `.cnb.yml`（必须） |
| 存放位置 | 代码仓库**根目录** |
| 文件格式 | YAML               |
| 管理方式 | 声明式代码管理     |

---

## 3. 基本语法结构

CNB 流水线采用**层级结构**，从外到内依次是：

| 层级                   | 说明                                     | 示例                   |
| ---------------------- | ---------------------------------------- | ---------------------- |
| **触发分支**           | 指定哪些分支的代码会触发流水线           | `main`、`dev`          |
| **触发事件**           | 指定什么操作会触发流水线                 | `push`、`pull_request` |
| **Pipeline（流水线）** | 一次完整的构建流程，包含多个阶段         | 构建流程               |
| **Stage（阶段）**      | 流水线中的一个步骤，可包含一个或多个任务 | 安装依赖               |
| **Job（任务）**        | 最小的执行单元，执行具体的命令或插件     | 执行命令               |

### 执行流程示意图

```
触发分支 (main)
└─ 触发事件 (push)
   ├─ Pipeline (流水线)
   │  └─ Stage（阶段）
   │     └─ Job（任务）
   └─ Pipeline (流水线)
      └─ Stage（阶段）
         └─ Job（任务）
```



### 两种书写方式

**数组形式（推荐）** ：

```yaml
# .cnb.yml
main:                          # 触发分支
  push:                        # 触发事件
    - name: push-pipeline1     # 流水线名称（可选）
      stages:
        - name: job1
          script: echo 1
    - name: push-pipeline2
      stages:
        - name: job2
          script: echo 2
  pull_request:                # main 分支的 PR 事件
    - name: pr-pipeline1
      stages:
        - name: job1
          script: echo 1
```

**对象形式**：

```yaml
# .cnb.yml
main:
  push:
    push-pipeline1:            # 流水线名称（必须唯一）
      stages:
        - name: job1
          script: echo 1
    push-pipeline2:
      stages:
        - name: job2
          script: echo 2
```

> **关键点**：一个事件下可包含多条 Pipeline，这些 Pipeline 会**并发执行**；一条 Pipeline 包含一组**顺序执行**的 Stages。

---

## 4. 触发分支（Trigger Branch）

**作用**：指定哪些分支的代码会触发流水线。

### 支持模式

| 模式类型       | 说明                     | 示例                     |
| -------------- | ------------------------ | ------------------------ |
| **精确匹配**   | 精确匹配分支名           | `main`、`dev`、`release` |
| **通配符匹配** | 使用 glob 语法匹配       | `feature/*`、`hotfix/*`  |
| **兜底匹配**   | 匹配所有未明确指定的分支 | `$`                      |



### 分支匹配示例

```yaml
# .cnb.yml
# 只在 main 分支触发
main:
  push:
    - stages:
        - script: echo "main branch"

# 匹配所有 feature 开头的分支
feature/*:
  push:
    - stages:
        - script: echo "feature branch"

# 兜底：匹配其他所有分支
$:
  push:
    - stages:
        - script: echo "other branches"
```



---

## 5. 触发事件（Trigger Event）

**作用**：指定什么操作会触发流水线执行。

### 常用事件

| 事件名          | 触发时机                         |
| --------------- | -------------------------------- |
| `push`          | 代码推送到分支时触发             |
| `pull_request`  | 创建或更新 Pull Request 时触发   |
| `tag_push`      | 推送标签时触发                   |
| `branch.delete` | 删除分支时触发                   |
| `vscode`        | 点击「启动云原生开发」按钮时触发 |
| `branch.create` | 创建分支时触发                   |
| `api_trigger`   | 自定义 API 事件触发              |
| `web_trigger`   | Web 页面自定义事件触发           |



### 触发事件示例

```yaml
# .cnb.yml
main:
  # 代码推送时执行测试
  push:
    - stages:
        - script: npm test

  # PR 时执行代码检查
  pull_request:
    - stages:
        - script: npm run lint
```



---

## 6. Pipeline（流水线）

**Pipeline** 表示一个流水线，包含一个或多个顺序执行的 `Stage`。

### Pipeline 配置项

| 配置项       | 类型            | 说明                                           |
| ------------ | --------------- | ---------------------------------------------- |
| `name`       | String          | 流水线名称（数组形式可选，对象形式必填且唯一） |
| `runner`     | Object          | 构建节点配置                                   |
| `imports`    | Array\<String\> | 从文件导入环境变量                             |
| `stages`     | Array           | 顺序执行的阶段列表                             |
| `failStages` | Array           | Stages 执行失败时执行的任务                    |
| `endStages`  | Array           | 环境销毁前执行的任务                           |

---

## 7. Stage（阶段）与 Job（任务）

### 基础 Stage 示例

```yaml
stages:
  - name: install dependencies
    script: npm install
  - name: run tests
    script: npm test
```

### 带 Jobs 的 Stage（完整层级）

```yaml
main:
  push:
    - name: pipeline-1
      stages:
        - name: stage-1
          jobs:
            - name: job-1
              script: echo "in pipeline-1"
        - name: stage-2
          jobs:
            - name: job-2
              script: echo "stage-2"
```



> **说明**：如果 Stage 中只有一个 Job，可以直接使用 `script` 简化写法；多个 Job 时使用 `jobs` 数组。

---

## 8. 完整配置示例

### 基础示例：Node.js 项目构建

```yaml
# .cnb.yml
main:                          # 目标分支
  push:                        # 触发事件
    - docker:                  # 执行环境
        image: node:22         # 使用 Node.js 22 镜像
      stages:
        - name: install
          script: npm install
        - name: test
          script: npm test
```



### 带失败处理的示例

```yaml
# .cnb.yml
main:
  pull_request:
    - name: pr-check
      stages:
        - name: lint
          script: npm run lint
        - name: test
          script: npm test
      # stages 失败时执行的任务
      failStages:
        - name: notify
          script: echo "notify to chat group"
```



---

## 9. 高级配置

### 9.1 自定义资源规格（CPU/内存）

通过 `runner.cpus` 声明所需的 CPU 核数，**最大支持 64 核**，内存为 `cpus × 2 GB`。

```yaml
# .cnb.yml
main:
  push:
    - runner:
        cpus: 64                # 最大 64 核
      docker:
        image: node:20
      stages:
        - name: build
          script: npm run build
```



### 9.2 构建缓存（Volumes）

通过 `volumes` 声明缓存目录，加速后续构建。

```yaml
main:
  push:
    - docker:
        image: node:22
      volumes:
        - /root/.npm            # npm 缓存目录
      stages:
        - name: install
          script: npm install
```

### 9.3 环境变量

**声明环境变量**（通过 `env`）：

```yaml
main:
  push:
    - docker:
        image: node:22
      env:
        NODE_ENV: production
        API_URL: https://api.example.com
      stages:
        - script: echo $NODE_ENV
```

**导入环境变量**（通过 `imports`）：

```yaml
main:
  push:
    - imports:
        - config/env-vars.toml   # 从文件导入
      stages:
        - script: echo $DB_HOST
```

> **说明**：在 Pipeline 中声明的环境变量对整个流水线有效；在 Job 中声明的环境变量仅对当前任务有效。

### 9.4 环境销毁前任务（endStages）

```yaml
$:
  vscode:
    - docker:
        image: node:20
      services:
        - vscode
      stages:
        - name: setup
          script: npm install
      endStages:                 # 环境销毁前执行
        - name: cleanup
          script: echo "cleaning up..."
```



---

## 10. 语法检查与自动补全

推荐使用 **云原生开发（WebIDE）** 环境编写配置文件，其原生支持语法检查和自动补全。

---

## 11. 配置最佳实践

| 实践             | 说明                                                  |
| ---------------- | ----------------------------------------------------- |
| **配置即代码**   | 将 `.cnb.yml` 与源代码一同版本管理                    |
| **使用数组形式** | 官方推荐，更清晰易读                                  |
| **复用配置**     | 利用 YAML 锚点 `&`、别名 `*` 和合并语法 `<<` 精简配置 |
| **合理设置缓存** | 使用 `volumes` 缓存依赖，加速构建                     |
| **失败处理**     | 使用 `failStages` 处理构建失败场景                    |
| **资源规格**     | 根据实际需求设置 `runner.cpus`，避免资源浪费          |

---

> **更多参考**：
> - [CNB 语法手册](https://docs.cnb.cool/zh/build/grammar.html)
> - [CNB 触发规则](https://docs.cnb.cool/zh/build/trigger-rule.html)
> - [CNB 官方文档](https://docs.cnb.cool)