# KubeSphere 集群搭建 — 完整操作流程（CentOS Stream 9 + VMware，最新版）

> 适用环境：VMware 虚拟机 ×4，CentOS Stream 9，内网网段 192.168.85.0/24
> 目标：用官方推荐工具 **KubeKey** 一体化安装 Kubernetes + KubeSphere，挂载 NFS（.104）作为存储
> **版本选型（最新版）**：KubeSphere **v4.2.1**（LuBan 可插拔架构）+ Kubernetes **v1.34.3** + containerd + Calico + NFS
> 说明：经二次核实，KubeSphere v4.2.1 可搭配 K8s 最高 **1.34.x**（社区已验证 `kubekey v4.0.5 + k8s v1.34.3 + ks v4.2.1` 跑通，且 KubeKey v4.0.5 脚本验证支持 K8s 1.23–1.36）。⚠️ K8s 版本号**必须写完整**（如 `v1.34.3`），只写 `v1.34` 会被 KubeKey 当默认处理甚至报错。
> 说明：你给的 4 个节点里，.104 仅作 NFS 存储服务器，**不加入 K8s 集群**。

---

## 0. 环境拓扑

| IP | 主机名 | 角色 | 说明 |
|----|--------|------|------|
| 192.168.85.101 | master01.itcast.cn / master01 | Master（控制平面 + etcd） | 单控制节点 |
| 192.168.85.102 | worker01.itcast.cn / worker01 | Worker | 工作节点 |
| 192.168.85.103 | worker02.itcast.cn / worker02 | Worker | 工作节点 |
| 192.168.85.104 | nfs01.itcast.cn / nfs01 | NFS 服务器 | 仅提供存储，不进集群 |

网络规划（KubeKey 默认 CNI 为 Calico）：
- Pod 网段：`192.168.0.0/16`
- Service 网段：`10.96.0.0/12`

> 镜像加速（国内必看）：下面所有 KubeKey 下载都用 `KKZONE=cn` 走国内源；KubeSphere 组件镜像走官方国内镜像 `hub.kubesphere.com.cn`（第 5/8 步 helm 安装 ks-core 时通过 `global.imageRegistry`/`extension.imageRegistry` 指定）。

---

## 1. 所有节点基础准备（4 台都要做）

KubeKey 会自动装依赖，但 CentOS Stream 9 这些前置最好先手动确认，避免踩坑。

### 1.1 设置主机名
```bash
hostnamectl set-hostname master01.itcast.cn   # 101
hostnamectl set-hostname worker01.itcast.cn   # 102
hostnamectl set-hostname worker02.itcast.cn   # 103
hostnamectl set-hostname nfs01.itcast.cn      # 104
```

### 1.2 配置 /etc/hosts（4 台都写）
```bash
cat >> /etc/hosts <<'EOF'
192.168.85.101 master01.itcast.cn master01
192.168.85.102 worker01.itcast.cn worker01
192.168.85.103 worker02.itcast.cn worker02
192.168.85.104 nfs01.itcast.cn nfs01
EOF
```

### 1.3 关闭防火墙（实验室环境；生产请改为放通端口）
```bash
systemctl disable --now firewalld
```

### 1.4 关闭 SELinux（CentOS Stream 9 默认 enforcing，会与容器/Calico 冲突）
```bash
setenforce 0
sed -i 's/^SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config
```

### 1.5 关闭 swap（kubelet 要求）
```bash
swapoff -a
sed -i '/\sswap\s/s/^/#/' /etc/fstab
```

### 1.6 加载内核模块与 sysctl
```bash
cat > /etc/modules-load.d/k8s.conf <<'EOF'
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter

cat > /etc/sysctl.d/k8s.conf <<'EOF'
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sysctl --system
```

### 1.7 时间同步 + 必要依赖包
```bash
systemctl enable --now chronyd
dnf install -y socat conntrack ebtables ipset chrony nfs-utils tar curl wget
```

> SSH 准备：KubeKey 通过 SSH 操作各节点。建议用 **root** 账号，提前打通免密（`ssh-keygen` + `ssh-copy-id root@各IP`）；若用密码，配置里填 `password` 即可（下面第 4 步）。

---

## 2. 配置 NFS 服务器（仅 192.168.85.104）

```bash
dnf install -y nfs-utils
mkdir -p /data/nfs
chmod 777 /data/nfs

echo "/data/nfs 192.168.85.0/24(rw,sync,no_root_squash,no_all_squash)" >> /etc/exports

systemctl enable --now rpcbind nfs-server
exportfs -r
showmount -e localhost        # 验证能看到 /data/nfs
```

> 101/102/103 三台集群节点上第 1.7 步已装 `nfs-utils`（作 NFS 客户端，provisioner Pod 才能挂载）。

---

## 3. 准备 KubeKey（在 master01 上执行，或任意能 SSH 到所有节点的机器）

> ⚠️ 若 `curl ... | sh -` 后没有 `kk` 文件，是**下载静默失败**（国内访问 GitHub Releases 常被墙，
> `curl -sf` 失败时无报错、管道喂给 sh 的是空内容）。直接用下面**手动下载**最稳。
> 当前最新稳定版：**KubeKey v4.0.5**（2026-06-05 发布，支持 K8s 1.23–1.36，兼容 KubeSphere v4.2.1）。

```bash
# 方式一（推荐）：手动下载稳定版 v4.0.5，解压即得 kk
export KKZONE=cn
wget https://github.com/kubesphere/kubekey/releases/download/v4.0.5/kubekey-v4.0.5-linux-amd64.tar.gz
tar -zxvf kubekey-v4.0.5-linux-amd64.tar.gz
chmod +x kk
mv kk /usr/local/bin/        # 放进 PATH，后续任意目录可直接敲 kk
kk version                   # 确认可用，v4.0.5 支持 K8s 最高 v1.36
```

```bash
# 方式二（GitHub 不通时的国内镜像）
wget https://mirror.ghproxy.com/https://github.com/kubesphere/kubekey/releases/download/v4.0.5/kubekey-v4.0.5-linux-amd64.tar.gz
tar -zxvf kubekey-v4.0.5-linux-amd64.tar.gz && chmod +x kk && mv kk /usr/local/bin/
```

```bash
# 方式三：仍想用官方一键脚本（务必带 VERSION，且多试几次）
export KKZONE=cn
curl -sfL https://get-kk.kubesphere.io | VERSION=v4.0.5 sh -
chmod +x kk
```

---

## 4. 生成并编辑两份配置（v4.0.5 双文件模型：config.yaml 组件 + inventory.yaml 节点）

> **【关键】KubeKey v4.0.5 是「双文件」模型，和旧的 `kind: Cluster` 单文件写法完全不同：**
> - `config.yaml`（`apiVersion: kubekey.kubesphere.io/v1`, `kind: Config`）= **组件配置**，只描述 K8s/CNI/CRI/存储等软件，**不含节点**。就是上一步 `kk create config` 打印出来的内容。
> - `inventory.yaml`（`kind: Inventory`）= **节点清单**，描述每台机器的 IP、SSH 连接方式、角色（master/worker/etcd）。需另外 `kk create inventory` 生成。
> 两者都**没有**旧版的 `hosts / roleGroups / addons` 写法了。

> **【重要】`--with-kubesphere` 已从 KubeKey v4.0.5 完全移除**（实测在 `kk create config` 和 `kk create cluster` 上都报 `unknown flag: --with-kubesphere`）。即 **v4.0.5 的 kk 不再负责装 KubeSphere**——K8s 用 kk 建，KubeSphere v4（ks-core，LuBan 可插拔架构）用官方 Helm chart 装到已存在的集群。本步两步生成都不带该 flag，KubeSphere 安装见第 5 步阶段二。

### 4.1 生成两份文件
```bash
kk create config --with-kubernetes v1.34.3 -o config.yaml      # 组件配置（保存为文件）
kk create inventory -o inventory.yaml                          # 节点清单（默认 localhost 占位，下面改）
```

### 4.2 编辑 config.yaml（组件配置）
只改两处：把 `zone` 设为 `cn`（国内镜像加速），并把 NFS 启用为存储类。用 `vi config.yaml`：

```yaml
spec:
  zone: "cn"          # 原是 zone: ""，改 cn 走国内源
  ...
  storage_class:
    # 保留 OpenEBS 本地卷为默认 StorageClass（实际 SC 名 openebs-hostpath），满足 KubeSphere 安装前置（零依赖，KK 自带 OpenEBS localpv）
    local:
      enabled: true
      default: true
    # ↓ 启用 NFS 存储类（指向 .104），作为额外 StorageClass 供有状态应用使用
    nfs:
      enabled: true
      nfs_provisioner_version: "4.0.18"
      server: 192.168.85.104
      path: /data/nfs
```
> 说明：KubeSphere 安装硬性要求是「集群里存在一个默认 StorageClass」，KK 自带的 OpenEBS 本地卷会生成 `openebs-hostpath`(default) 已满足；NFS 作为额外 SC（名称通常为 `nfs-client`），你的 PVC 写 `storageClassName: nfs-client` 即用 .104 的存储。
> 若你坚持要 NFS 作为默认：把上面 `local.default` 改为 `false`，并在 `nfs:` 下加 `default: true`（v4.0.5 支持该字段；若 kk 报错不认，回退上面的写法即可）。
> 其余（kube_version、calico、containerd 等）保持 `kk create config` 生成的默认值。

### 4.3 编辑 inventory.yaml（节点清单）
用 `vi inventory.yaml`，把默认 `localhost` 占位替换成你的 3 台节点。

**方式 A：密码登录（最简单）** — 需目标机 sshd 允许密码认证（CentOS Stream 9 默认允许）。`password` 的值**必须加引号**：
```yaml
apiVersion: kubekey.kubesphere.io/v1
kind: Inventory
metadata:
  name: default
spec:
  hosts:
    master01:
      connector:
        type: ssh
        host: 192.168.85.101
        port: 22
        user: root
        password: "你的root密码"
      internal_ipv4: 192.168.85.101
    worker01:
      connector:
        type: ssh
        host: 192.168.85.102
        port: 22
        user: root
        password: "你的root密码"
      internal_ipv4: 192.168.85.102
    worker02:
      connector:
        type: ssh
        host: 192.168.85.103
        port: 22
        user: root
        password: "你的root密码"
      internal_ipv4: 192.168.85.103
  groups:
    k8s_cluster:
      groups:
      - kube_control_plane
      - kube_worker
    kube_control_plane:
      hosts:
      - master01
    kube_worker:
      hosts:
      - worker01
      - worker02
    etcd:
      hosts:
      - master01
  # ⚠️ etcd 组必须保留！KubeKey v4 的 precheck 强制「etcd group must not be empty」，
  # 且官方默认 inventory 的 etcd 组就指向 control-plane 节点（堆叠 etcd）。
  # v4 的做法：KubeKey 在 etcd 组节点上以 **systemd service** 自动部署 etcd，
  # 再由 kubeadm init 以外部 etcd 方式连接它（所以会有 ExternalEtcdVersion 检查）。
  # 若 kubeadm init 报 [ERROR ExternalEtcdVersion] 连 2379 失败，是 etcd service 没起来
  # （常见原因：首次装 etcd 数据/镜像问题，或上一次失败的残留），需清理
  # master01 的 /var/lib/etcd、/etc/kubernetes 后重跑，不要去删 etcd 组。
```

**方式 B：私钥免密（推荐）** — 先在 master01 生成密钥并分发到所有节点（含自己）：
```bash
ssh-keygen -t rsa
for ip in 192.168.85.101 192.168.85.102 192.168.85.103; do ssh-copy-id root@$ip; done
```
然后在每个 host 的 `connector` 下用 `private_key` 代替 `password`：
```yaml
    master01:
      connector:
        type: ssh
        host: 192.168.85.101
        port: 22
        user: root
        private_key: /root/.ssh/id_rsa
      internal_ipv4: 192.168.85.101
```
（worker01/worker02 同理，把 `password: "..."` 换成 `private_key: /root/.ssh/id_rsa`）
> KubeKey 在 master01 上运行，要能 SSH 到**自己**（192.168.85.101），所以 `ssh-copy-id root@192.168.85.101` 也要做。`password` / `private_key` 二选一。

---

## 5. 执行安装（两阶段：kk 装 K8s，Helm 装 KubeSphere v4）

> **【关键纠正】KubeKey v4.0.5 的 `kk create cluster` 也移除了 `--with-kubesphere`**（实测 `unknown flag: --with-kubesphere`）。
> 也就是说，在 v4.0.5 里 **`kk` 只负责建 K8s 集群，KubeSphere 由官方 Helm chart（ks-core）单独装到已存在的集群** —— 这是 KubeSphere v4（LuBan 架构）的标准分流安装方式，不依赖 kk 的集成 flag。

### 阶段一：用 kk 只装 K8s（去掉 `--with-kubesphere`）
```bash
kk create cluster -i inventory.yaml -c config.yaml
```
安装过程（约 10~20 分钟，视网速）：
- 自动装 containerd、初始化 K8s、装 Calico、把 3 个节点按 inventory 角色 join 进来
- 自动部署 NFS provisioner（指向 .104）并创建 `nfs-client` StorageClass —— **仅当 config.yaml 设了 `storage_class.nfs.enabled: true`**；若没设（本环境即如此），这步会被 skip，装完只有 `openebs-hostpath` 默认 SC，需按第 6.5 节手动补 `nfs-client`
- 装好后 `kubectl get nodes` 应看到 3 节点都 `Ready`

### 阶段二：用 Helm 装 KubeSphere v4.2.1（ks-core，走 OCI，不再用旧 charts 仓库）

> **【关键纠正 · 实测踩坑】**：KubeSphere v4 的 `ks-core` 图表 **不在** `charts.kubesphere.com.cn/main` 这个旧仓库里（实测 `helm search repo kubesphere/ks-core` 返回 `No results found`；那个仓库只剩 v3 用的 `ks-installer`）。v4 改用 **OCI 镜像仓库**分发：`oci://hub.kubesphere.com.cn/kse/ks-core`。所以**不要**再 `helm repo add kubesphere` + `helm search kubesphere/ks-core`，直接用下面的 OCI 地址装即可。你若已 `helm repo add kubesphere` 加过那个旧仓库，留着无害但用不到，可 `helm repo remove kubesphere` 清掉。

kk 已自带装好 Helm（config.yaml 里 `helm_version: v3.18.5`，`helm version` 可确认）。`helm` 在 `/usr/local/bin`，确认 PATH 已包含（否则先 `export PATH=$PATH:/usr/local/bin`）。

**先拉一下确认 OCI 图表可达（可选，验证用；拉完会生成 `ks-core-1.2.4.tgz`，可 `rm -f` 删掉）**：
```bash
helm pull oci://hub.kubesphere.com.cn/kse/ks-core --version 1.2.4
```

**正式安装（chart 版本 1.2.4 = KubeSphere v4.2.1；镜像走官方国内镜像 hub.kubesphere.com.cn）**：
```bash
helm upgrade --install -n kubesphere-system --create-namespace ks-core \
  oci://hub.kubesphere.com.cn/kse/ks-core --version 1.2.4 \
  --debug --wait --reset-values --take-ownership \
  --set global.imageRegistry=hub.kubesphere.com.cn \
  --set extension.imageRegistry=hub.kubesphere.com.cn
```
> 说明：`--reset-values --take-ownership` 是官方安装/升级文档推荐参数；`global.imageRegistry`/`extension.imageRegistry` 设 `hub.kubesphere.com.cn`（v4.2.x 官方国内镜像，**不要再填 swr 华为云那个**，避免镜像路径对不上）。扩展中心若为空，可额外加 `--set kseExtensionRepository.image.tag=v11.2.0`（指定扩展仓库版本）。
等待 ks-core 与各组件 Pod 起来：
```bash
kubectl get pods -n kubesphere-system     # 全部 Running 即可
```

**装完后控制台访问信息与初始账号密码**：
```
Console: http://192.168.85.101:30880
Account: admin
Password: P@88w0rd      # 首次登录强制改密码
```
> 镜像说明：ks-core 图表走 `oci://hub.kubesphere.com.cn/kse/ks-core`，组件镜像走官方国内镜像 `hub.kubesphere.com.cn`（v4.2.x 官方源）。若某节点拉取超时，检查该节点能否访问 `hub.kubesphere.com.cn`；如个别镜像拉不到，可把 `global.imageRegistry`/`extension.imageRegistry` 改为 `registry.cn-beijing.aliyuncs.com`（阿里云镜像）作为备选。

---

## 6. 验证集群与组件

> **⚠️ kubectl 路径坑（根因 + 两种修法）**：KubeKey v4 把 kubectl/kubeadm/kubelet 装到 `/usr/local/bin`，而 `/usr/local/bin` 本就在默认 PATH 里，**所以 `/usr/bin/kubectl` 这个软链本来就是多余的**。真正的坑是：系统里残留了一个**指向不存在路径的坏软链** `/usr/bin/kubectl`，因为 `/usr/bin` 在 PATH 中排在 `/usr/local/bin` 之前，shell 先命中坏链 → 报 `没有那个文件或目录`，真二进制根本轮不到。
>
> **✅ 推荐修法（最干净）：直接删掉多余/坏的 `/usr/bin` 软链**，让 PATH 自然找到 `/usr/local/bin/kubectl`：
> ```bash
> ls -l /usr/bin/kubectl          # 确认它只是个软链（且指向不存在的路径）
> rm -f /usr/bin/kubectl          # 只删链接，不动 /usr/local/bin 真二进制，安全
> hash -r; kubectl get nodes      # 应当正常，走 /usr/local/bin
> ```
> **🟡 备选修法（也能用，但留冗余）**：把坏链指回真身——`KUBECTL=$(find /usr/local/bin /opt/kubekey/bin -name kubectl|head -1); ln -sf "$KUBECTL" /usr/bin/kubectl; hash -r`。两种都行，但推荐上者（系统更干净，无多余链接）。
> 同理，若手敲 `kubeadm`/`kubelet` 也报类似"坏链/command not found"，八成是同一个套路——`ls -l /usr/bin/kubeadm` 看是不是也有坏软链，有就 `rm -f` 掉即可（KK 自己跑任务走绝对路径，不受影响）。

```bash
kubectl get nodes                      # 3 个节点都 Ready
kubectl get sc                         # 应看到 openebs-hostpath(default) 本地 SC；若开了 NFS 还会有 nfs-client（本次 NFS 被 skip，只有 openebs-hostpath）
kubectl get pods -A | grep -E 'kube-system|kubesphere'   # 核心 Pod 多为 Running
```

如节点未 Ready，先看 Calico：
```bash
kubectl get pods -n calico-system | grep calico
```

---

## 6.5 补装 NFS 存储类（可选：KK 未自动部署 nfs-client 时）

> 若 `kubectl get sc` 只有 `openebs-hostpath (default)`、没有 `nfs-client`，说明 KK 这趟没部署 NFS provisioner（常见于 config.yaml 未设 `storage_class.nfs.enabled: true`，本环境即如此）。按下面手动补即可，**不影响已运行的 KubeSphere**。
>
> ⚠️ **为什么不用 helm**：`helm install nfs-subdir-external-provisioner` 会去 `github.com/.../releases/download/...` 拉 chart 压缩包，而本环境对 `github.com` 主站是 `connection refused`（GitHub Pages `kubernetes-sigs.github.io` 能通、GitHub 主站不通）。所以**直接用 YAML 部署**，省掉下载 chart 这一步，只剩容器镜像要拉（已换国内镜像）。完整清单见仓库文件 `nfs-client-provisioner.yaml`。
>
> ⚠️ **镜像注意**：默认镜像 `registry.k8s.io/sig-storage/nfs-subdir-external-provisioner` 在国内拉不到，必须换成国内镜像 `swr.cn-north-4.myhuaweicloud.com/ddn-k8s/registry.k8s.io/sig-storage/nfs-subdir-external-provisioner:v4.0.2`（已实测可用）。若仍 ImagePullBackOff，备选镜像：`registry.cn-beijing.aliyuncs.com/kubesphereio/nfs-subdir-external-provisioner:v4.0.2`。

**0) 前置检查（确认 .104 的 NFS 已正确导出）**
```bash
showmount -e 192.168.85.104        # 应列出 /data/nfs 且允许 master01/worker 的 IP
# 若提示 command not found：yum install -y nfs-utils
# 若没有 /data/nfs 或权限不对，先去 .104 修 /etc/exports 并 exportfs -ra
```

**1) 部署**（把下面整段粘进 master01 终端执行，无需 helm）：
```bash
cat > /tmp/nfs-client-provisioner.yaml <<'EOF'
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: nfs-client
provisioner: k8s-sigs.io/nfs-subdir-external-provisioner
parameters:
  archiveOnDelete: "false"
reclaimPolicy: Delete
allowVolumeExpansion: true
volumeBindingMode: Immediate
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: nfs-client-provisioner
  namespace: kube-system
---
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: nfs-client-provisioner-runner
rules:
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["persistentvolumes"]
    verbs: ["get", "list", "watch", "create", "delete"]
  - apiGroups: [""]
    resources: ["persistentvolumeclaims"]
    verbs: ["get", "list", "watch", "update"]
  - apiGroups: ["storage.k8s.io"]
    resources: ["storageclasses"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["events"]
    verbs: ["create", "update", "patch"]
---
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: run-nfs-client-provisioner
subjects:
  - kind: ServiceAccount
    name: nfs-client-provisioner
    namespace: kube-system
roleRef:
  kind: ClusterRole
  name: nfs-client-provisioner-runner
  apiGroup: rbac.authorization.k8s.io
---
kind: Role
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: leader-locking-nfs-client-provisioner
  namespace: kube-system
rules:
  - apiGroups: [""]
    resources: ["endpoints"]
    verbs: ["get", "list", "watch", "create", "update", "patch"]
---
kind: RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: leader-locking-nfs-client-provisioner
  namespace: kube-system
subjects:
  - kind: ServiceAccount
    name: nfs-client-provisioner
    namespace: kube-system
roleRef:
  kind: Role
  name: leader-locking-nfs-client-provisioner
  apiGroup: rbac.authorization.k8s.io
---
kind: Deployment
apiVersion: apps/v1
metadata:
  name: nfs-client-provisioner
  namespace: kube-system
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: nfs-client-provisioner
  template:
    metadata:
      labels:
        app: nfs-client-provisioner
    spec:
      serviceAccountName: nfs-client-provisioner
      containers:
        - name: nfs-client-provisioner
          image: swr.cn-north-4.myhuaweicloud.com/ddn-k8s/registry.k8s.io/sig-storage/nfs-subdir-external-provisioner:v4.0.2
          volumeMounts:
            - name: nfs-root
              mountPath: /persistentvolumes
          env:
            - name: PROVISIONER_NAME
              value: k8s-sigs.io/nfs-subdir-external-provisioner
            - name: NFS_SERVER
              value: 192.168.85.104
            - name: NFS_PATH
              value: /data/nfs
      volumes:
        - name: nfs-root
          nfs:
            server: 192.168.85.104
            path: /data/nfs
EOF
kubectl apply -f /tmp/nfs-client-provisioner.yaml

# 2) 验证
kubectl get pods -n kube-system | grep nfs-client-provisioner
kubectl get sc        # 应看到 nfs-client + openebs-hostpath(default)
```

**3) 功能验证（建个 PVC 看是否自动 Bound）**：
```bash
cat > /tmp/test-nfs-pvc.yaml <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-nfs-pvc
spec:
  accessModes: [ReadWriteMany]
  storageClassName: nfs-client
  resources:
    requests:
      storage: 1Gi
EOF
kubectl apply -f /tmp/test-nfs-pvc.yaml
kubectl get pvc test-nfs-pvc        # STATUS 变 Bound 即成功
# 成功后去 .104 看 /data/nfs 下生成了以 PVC 命名的子目录，确认无误再删测试 PVC：
kubectl delete -f /tmp/test-nfs-pvc.yaml
```
> 之后要用 NFS 存储，PVC 直接写 `storageClassName: nfs-client` 即可。本部署**未**把 nfs-client 设为默认 SC（保持 openebs-hostpath 为默认，避免干扰已部署的 KubeSphere 组件）；若真要让 NFS 成为默认，给 SC 加注解 `storageclass.kubernetes.io/is-default-class: "true"` 即可（谨慎）。

---

## 7. 访问 KubeSphere 控制台

- 浏览器打开：`http://192.168.85.101:30880`（或任意节点 IP:30880）
- 账号：`admin`　密码：`P@88w0rd`
- 首次登录强制改密码

> ✅ **已实测验证（2026-08-12）**：按上面 OCI 命令装完后，`kubectl get pods -n kubesphere-system` 全部 Running（extensions-museum / ks-apiserver / ks-console / ks-console-embed / ks-controller-manager / ks-posthog），`curl -sI :30880` 返回 `302 Found`，控制台可直接访问。阶段一（KK 建 K8s v1.34.3）+ 阶段二（Helm 装 ks-core v1.2.4）**全链路跑通**。其中 `helm-install-ks-console-embed` 是一次性 Job，状态 `Completed` 属正常。

> v4 的新变化：核心（ks-core）只含最基础能力，** DevOps / 日志 / 监控 / 告警 / 网关 / 服务网格等是“扩展组件”**，需在扩展中心另行安装（见第 8 步）。

---

## 8. 安装扩展组件（v4 可插拔架构，核心特性）

v4 里功能以“扩展（Extension）”形式存在，两种方式安装：

### 方式 A：控制台扩展中心（推荐，纯 UI 操作）
1. 登录 → 左侧「扩展中心」
2. 找到要装的扩展（如 DevOps、日志、监控、告警、网关、服务网格等），点「安装」
3. 安装完成后在「应用」里启用并配置

### 方式 B：Helm 命令行（适合自动化）
KubeSphere v4 核心本身也是 Helm Chart，如需重装/指定国内镜像：
```bash
# KubeSphere v4.2.1 核心即 ks-core chart（国内镜像 hub.kubesphere.com.cn，需 Helm >= 3.17）
helm upgrade --install -n kubesphere-system --create-namespace ks-core \
  oci://hub.kubesphere.com.cn/kse/ks-core --version 1.2.4 \
  --debug --wait --reset-values --take-ownership \
  --set global.imageRegistry=hub.kubesphere.com.cn \
  --set extension.imageRegistry=hub.kubesphere.com.cn
```
> `ks-core` 的 chart 版本需与 KubeSphere 版本对应（v4.2.1 对应 ks-core 1.2.x，装前以官网文档为准）。各扩展组件的 Helm Chart 在 `https://github.com/kubesphere-extensions/ks-extensions`。

---

## 附录 A：如果已经用 kubeadm 手搭了 K8s，只想装最新版 KubeSphere

跳过第 3~5 步的 KubeKey 建集群，直接在已有集群上用 Helm 装 ks-core（前置：集群有默认 StorageClass，即第 2 步 NFS 已就绪）：

```bash
helm upgrade --install -n kubesphere-system --create-namespace ks-core \
  oci://hub.kubesphere.com.cn/kse/ks-core --version 1.2.4 --debug --wait --reset-values --take-ownership \
  --set global.imageRegistry=hub.kubesphere.com.cn \
  --set extension.imageRegistry=hub.kubesphere.com.cn

# 看进度
kubectl logs -n kubesphere-system -l app.kubernetes.io/name=ks-apiserver -f
# 或查看 ks-console 的 NodePort
kubectl get svc/ks-console -n kubesphere-system
```

---

## 附录 B：常见排障

> **⚠️ 清理残留铁律（踩坑总结）**：KubeKey v4 判定"组件已安装"靠**二进制是否存在**（不看 systemd 单元）。所以清理时**二进制和 systemd 单元必须一起删**；若只删单元保留二进制，KK 会判定组件已装而 skip 重新部署单元，留下"单元缺失/服务起不来"的坑（etcd 的 2379、kubelet 的 exit status 5 都源于此）。

| 现象 | 原因 | 处理 |
|------|------|------|
| 节点 `NotReady` | Calico 未就绪 / 网络不通 | `kubectl get pods -n kube-system \| grep calico` 排查 |
| `kubeadm`/KK 报 swap 开启 | 没关 swap | 第 1.5 步，`swapoff -a` + 注释 fstab |
| KubeSphere 起不来报无默认 SC | 没默认 StorageClass | 确认 config.yaml 里 `storage_class.local.default: true`（或 `nfs.default: true`）；`kubectl get sc` 看是否有 (default) 的 SC |
| 镜像拉取超时 `ImagePullBackOff` | 国内访问 docker.io 慢 | 设 `KKZONE=cn`；KK 装组件再用 `swr.cn-southwest-2.myhuaweicloud.com/ks` 镜像 |
| SSH 连接失败 | 没配免密也没填密码 | 第 1.7 步配 `ssh-copy-id`，或在 hosts 里填 `password` |
| 扩展中心装扩展失败 | 扩展仓库不可达 | 在扩展中心设置自定义扩展仓库地址，或走方式 B 的 Helm 安装 |
| `Kubernetes \| Ensure kubelet service is active` 全节点失败（`The kubelet service must be running and active when it is loaded`） | **上一次安装中途失败，kubelet 已被 KK 装成 systemd 单元（loaded）但没启动（inactive），重跑时 precheck 判定节点不干净**；常见诱因是之前 `kubeadm reset` 因路径错（`/usr/bin/kubeadm` 不存在）没真正执行，残留未清 | 在**所有节点**清理：① `systemctl stop/disable kubelet` ② 找真实路径 `command -v kubeadm \|\| ls /usr/local/bin/kubeadm` 后 `kubeadm reset -f` ③ `rm -rf /etc/kubernetes /var/lib/kubelet /var/lib/etcd /etc/etcd /etc/cni/net.d /var/lib/cni` ④ 删 kubelet systemd 单元 `rm -f /etc/systemd/system/kubelet.service /etc/systemd/system/kubelet.service.d/10-kubeadm.conf` ⑤ `systemctl daemon-reload`；确认 kubelet 单元不再 loaded 后重跑 `kk create cluster` |
| `ExternalEtcdVersion ... 2379 connection refused`（kubeadm init 阶段） | inventory 的 `etcd` 组节点上 etcd 没起来（2379 没监听）。**最常见诱因**：上一次安装残留的 etcd 二进制/systemd 单元仍在，KK 判定"etcd 已安装"而 **skip 了安装+启动步骤**，etcd 从未运行 | **保留** `etcd: hosts: [master01]`（绝不能删，v4 强制 etcd 组非空）。彻底清 etcd 残留：① `systemctl stop/disable etcd` ② `rm -f /usr/local/bin/etcd /usr/local/bin/etcdctl /usr/local/bin/etcdutl`（删二进制，KK 才会重装）③ `rm -f /etc/systemd/system/etcd.service /etc/etcd.env && rm -rf /etc/etcd /var/lib/etcd` ④ `systemctl daemon-reload`；确认 `command -v etcd` 无输出后重跑。**只删数据目录不删二进制/systemd 单元 = KK 仍 skip 启动，2379 仍不通** |
| 节点时间不同步 | 时钟漂移导致 etcd 异常 | 第 1.7 步 chrony 必须正常（`chronyc sources -v`） |
| `Run kubeadm init` 失败：`[kubelet-start] WARNING: unable to start the kubelet service: [exit status 5]` 随后 `kubelet is not healthy ... connection refused`(10248) | **kubelet 的 systemd unit 文件缺失**：之前清理残留时只删了 kubelet 单元、没删 kubelet 二进制；KK 的"Check if kubelet is installed"只看二进制 → 判定 kubelet 已装 → 整段 `Copy kubelet systemd service file / Reload and enable kubelet service` 被 skip → 单元一直缺 → `systemctl start kubelet` 报 **exit status 5**（= systemd 的 LSB "program is not installed"，即 unit 不存在）→ kubelet 起不来 → 控制平面卡在 `wait-control-plane` 4 分钟超时。日志里 `WARNING Service-Kubelet: kubelet service is not enabled` 也是同一信号 | **三节点都跑**：① `rm -f /usr/local/bin/kubelet`（删二进制，KK 才会重装单元）② `rm -f /etc/systemd/system/kubelet.service /usr/lib/systemd/system/kubelet.service; rm -rf /etc/systemd/system/kubelet.service.d; systemctl daemon-reload`；**master01 额外**：`kubeadm reset -f`（kubeadm 在 /usr/local/bin）+ `rm -rf /etc/kubernetes /var/lib/kubelet /etc/cni/net.d /var/lib/cni /var/run/kubernetes`。重跑前确认日志里 `Copy kubelet systemd service file` 从 `skip` 变成 `success`，再 `kk create cluster -i inventory.yaml -c config.yaml`。若 journalctl 显示是 swap/cgroup/SELinux 等其它原因，另行对症处理 |

---

## 一键自检清单（全部完成后应在 master01 上看到）

```bash
kubectl get nodes                                    # 3 Ready
kubectl get sc                                        # openebs-hostpath(default) 本地 SC（NFS 未启用则无 nfs-client）
kubectl get pods -A | grep -E 'kube-system|kubesphere'  # 大多 Running
curl -sI http://192.168.85.101:30880 | head -1       # HTTP 200/302
```
