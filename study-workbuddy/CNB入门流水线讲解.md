# CNB 云原生构建入门流水线 —— 逐行讲解

> 配套文件：`.cnb.yml`（已生成在仓库根目录）
> 官方文档：https://docs.cnb.cool/zh/configuration.html

---

## 一、CNB 是什么

- **CNB = Cloud Native Build**，腾讯的云原生 CI/CD 平台（cnb.cool）。
- 你只需要在代码仓库根目录放一个 `.cnb.yml` 文件，写清楚**“什么事件触发、在什么环境跑、跑什么命令”**，剩下的构建、测试、打包、推送镜像都交给平台自动完成。
- 核心理念：**配置即代码（Config as Code）**。流水线配置和源码一起进版本管理，谁改了流水线、为什么改，都有 git 记录可追溯。

---

## 二、.cnb.yml 的四层结构（一句话记）

```
分支(branch)  →  事件(event)  →  流水线(pipeline)  →  阶段(stage)  →  命令(script)
```

| 层级 | 关键字 | 作用 | 执行方式 |
|------|--------|------|----------|
| 分支 | `main:` / `master:` | 监听哪个分支 | — |
| 事件 | `push:` / `pull_request:` / `tag_push:` / `cron:` | 什么动作触发 | — |
| 流水线 | `- name: xxx` | 一条完整任务流，事件下可有多条 | **并发** |
| 阶段 | `stages:` 下的项 | 一个步骤 | **串行** |
| 命令 | `script:` | 真正执行的 shell 命令 | 顺序执行 |

> 关键点：**同一条流水线里的所有阶段共享同一个运行环境（同一个容器）**；但**同事件下的多条流水线是并发跑的**。

---

## 三、逐段讲解生成的流水线

### 第 1 部分：main 分支的 push / pull_request

```yaml
main:                      # ① 分支名：监听 main 分支
  push:                   # ② 触发事件一：git push 到 main 时触发
    - name: build-and-test        # ③ 流水线名称
      docker:                     # ④ 运行环境
        image: node:22            #    用 Node.js 22 官方镜像当“执行机器”
      stages:                     # ⑤ 阶段列表（串行）
        - name: 安装依赖
          script: npm install     # ⑥ 装依赖
        - name: 代码检查
          script: npm run lint    # 跑 ESLint 等静态检查
        - name: 运行测试
          script: npm test        # 跑单元测试
        - name: 打包构建
          script: npm run build   # 产出 dist/ 等构建物
```

- **`docker: image: node:22`**：注意这里**不是构建 Docker 镜像**，而是“用哪个镜像当作执行机器”。换成 `python:3.11`、`golang:1.24` 就能跑别的语言。
- **`script` 的两种写法**：
  - 单行：`script: npm install`
  - 多行块：`script: |`（用 `|` 保留换行，可写多行 shell）

```yaml
  pull_request:            # ② 触发事件二：向 main 提/更新 PR 时触发
    - name: pr-check
      docker:
        image: node:22
      stages:
        - name: 安装依赖
          script: npm install
        - name: 代码检查
          script: npm run lint
        - name: 运行测试
          script: npm test
```

- 这一段和 push 几乎一样，区别在**触发时机**：PR 阶段一般只做“检查 + 测试”，不发布，避免在合并前就动生产资源。

### 第 2 部分：打 tag 时的 Docker 镜像构建与推送

```yaml
tag_push:                 # ① 触发事件：推送 Git tag 时触发
  - name: docker-build-push
    services:
      - docker            # 开启 Docker-in-Docker
    docker:
      image: node:22
    stages:
      - name: 构建并推送镜像
        script: |
          IMAGE="${CNB_DOCKER_REGISTRY}/${CNB_REPO_SLUG_LOWERCASE}:${CNB_COMMIT_SHORT}"
          docker build -t "$IMAGE" .
          docker push "$IMAGE"
```

- **`services: [docker]`**：开启 **Docker-in-Docker**，让流水线内部能执行 `docker build` / `docker push`。**不加这行，流水线里用不了 docker 命令。**
- 开启 `services:[docker]` 后，CNB 会**自动帮你 `docker login` 到它的制品库**，所以后面的 `docker push` 能直接推，不用自己写登录命令。

---

## 四、关键概念速查

| 概念 | 说明 |
|------|------|
| `docker: image:` | 运行环境镜像，不是产出物，是“执行机器” |
| `services: [docker]` | 开启 Docker-in-Docker，用于构建/推送镜像 |
| `script` | 阶段里真正执行的命令，支持单行或 `\|` 多行 |
| `stages` | 顺序执行的步骤列表 |
| 多条 pipeline | 同事件下写多条 `- name:`，会**并发**执行 |

**CNB 内置环境变量（无需自己定义，直接 `${变量名}` 用）：**

| 变量 | 含义 |
|------|------|
| `CNB_DOCKER_REGISTRY` | CNB 制品库地址（如 `docker.cnb.cool`） |
| `CNB_REPO_SLUG_LOWERCASE` | 当前仓库路径（小写） |
| `CNB_COMMIT_SHORT` | 当前提交的短哈希 |
| `CNB_BRANCH` | 当前分支名 |

---

## 五、怎么跑起来

1. 把 `.cnb.yml` 放到你仓库的**根目录**。
2. 按你的项目改 `script`（见下一节“换语言”）。
3. 提交并推送：
   - `git push origin main` → 触发第 1 部分（构建 + 测试）。
   - `git tag v1.0 && git push origin v1.0` → 触发第 2 部分（构建并推送镜像）。
4. 到 cnb.cool 对应仓库的 **“构建”** 页面，能看到实时日志和每一步的成败。

> **和你的 TKE 联动**：第 2 部分把镜像推到 CNB 制品库后，你在 TKE 里部署工作负载时，直接填这个镜像地址（`${CNB_DOCKER_REGISTRY}/${CNB_REPO_SLUG_LOWERCASE}:<tag>`）即可，形成“提交代码 → 自动出镜像 → 部署到 TKE”的闭环。

---

## 六、换成其他语言（示例片段）

**Python：**
```yaml
main:
  push:
    - name: py-build-test
      docker:
        image: python:3.11
      stages:
        - name: 安装依赖
          script: pip install -r requirements.txt
        - name: 运行测试
          script: pytest
```

**Go：**
```yaml
main:
  push:
    - name: go-build
      docker:
        image: golang:1.24
      stages:
        - name: 下载依赖
          script: go mod download
        - name: 编译
          script: go build -o app .
```

---

## 七、进阶方向（学完入门再碰）

- `pull_request` 加 `lock: { key: pr, cancel-in-progress: true }`：新提交自动取消旧构建，省资源。
- `exports`：把上一步的 shell 输出导出为变量，供后续阶段使用。
- `cron:`：定时构建（如每天凌晨跑一次全量测试）。
- 多架构镜像：`docker buildx` + `rootlessBuildkitd` 构建 amd64/arm64 双架构。
- `if` / `ifModify`：按条件或按改动文件决定是否执行某阶段。

---

_提示：本文件与 `.cnb.yml` 配套使用。先把 `.cnb.yml` 放到你的仓库根目录即可开始体验。_
