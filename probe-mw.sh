#!/bin/bash
# ==============================================================================
#  probe-mw.sh —— 中间件隔离模型自查脚本
#  对应《SaaS四集群接手清单.md》第 0.2 节的四个问题
#
#  设计原则：
#    1. 全程只读 —— 不创建、不修改、不删除任何资源
#    2. 自动跳过密码 / 密钥类字段，不打印明文
#    3. 不自动 exec 进业务容器（第 7 段只打印命令模板，由你确认后手动执行）
#
#  用法：
#    ./probe-mw.sh <业务命名空间>                 # 用当前 context
#    ./probe-mw.sh <业务命名空间> <kube-context>  # 指定集群
#
#  建议：三套业务环境各跑一遍，输出存文件后做 diff
#    ./probe-mw.sh app-sit  ctx-sit  > sit.mw.txt  2>&1
#    ./probe-mw.sh app-uat  ctx-uat  > uat.mw.txt  2>&1
#    ./probe-mw.sh app-prod ctx-prod > prod.mw.txt 2>&1
#    diff sit.mw.txt prod.mw.txt
#
#  首次在 Linux 上跑之前，如提示 ^M 错误，先执行：
#    sed -i 's/\r$//' probe-mw.sh
# ==============================================================================

set -u

NS="${1:-}"
CTX="${2:-}"

if [ -z "$NS" ]; then
  echo "用法: $0 <业务命名空间> [kube-context]"
  echo "例:   $0 app-prod ctx-prod > prod.mw.txt 2>&1"
  echo
  echo "不知道命名空间叫什么？先跑："
  echo "  kubectl get ns"
  exit 1
fi

K="kubectl"
[ -n "$CTX" ] && K="kubectl --context=$CTX"

# 敏感字段：命中这些关键字的行一律不打印
SKIP='password|passwd|pwd|secret|token|accesskey|secretkey|private|credential|apikey|api_key|ak|sk'

# 中间件关键字
MW='mysql|redis|mongo|kafka|rocketmq|rabbit|nacos|consul|polaris|zookeeper|elastic|clickhouse|tdsql|jdbc|amqp|dubbo|mq'

hr() { echo; echo "==================== $* ===================="; }

# ------------------------------------------------------------------------------
hr "0. 当前集群（动手前先确认没跑错环境）"
# ------------------------------------------------------------------------------
$K config current-context
$K cluster-info 2>/dev/null | head -2
echo "采集时间: $(date '+%F %T')"

# ------------------------------------------------------------------------------
hr "1. 我的权限边界（先知道能看多少）"
# ------------------------------------------------------------------------------
$K auth can-i --list 2>/dev/null | head -30

# ------------------------------------------------------------------------------
hr "2. 命名空间 $NS 下的 ConfigMap / Secret 清单"
# ------------------------------------------------------------------------------
$K -n "$NS" get cm -o name 2>/dev/null
$K -n "$NS" get secret -o name 2>/dev/null

# ------------------------------------------------------------------------------
hr "3. ConfigMap 中的中间件连接信息"
# ------------------------------------------------------------------------------
for cm in $($K -n "$NS" get cm -o name 2>/dev/null); do
  out=$($K -n "$NS" get "$cm" -o yaml 2>/dev/null \
        | grep -iE "$MW" | grep -viE "$SKIP")
  if [ -n "$out" ]; then
    echo "--- $cm ---"
    echo "$out"
  fi
done

# ------------------------------------------------------------------------------
hr "4. Secret 中的中间件连接信息（已过滤密码/密钥字段）"
# ------------------------------------------------------------------------------
for s in $($K -n "$NS" get secret -o name 2>/dev/null); do
  if command -v jq >/dev/null 2>&1; then
    out=$($K -n "$NS" get "$s" -o json 2>/dev/null \
          | jq -r '.data // {} | to_entries[] | "\(.key) = \(.value | @base64d)"' 2>/dev/null \
          | grep -iE "$MW" | grep -viE "$SKIP")
  else
    out=$($K -n "$NS" get "$s" -o json 2>/dev/null \
          | grep -oE '"[A-Za-z0-9_.-]+": *"[A-Za-z0-9+/=]{8,}"' \
          | while IFS='"' read -r _ k _ v _; do
              echo "$k = $(echo "$v" | base64 -d 2>/dev/null)"
            done \
          | grep -iE "$MW" | grep -viE "$SKIP")
  fi
  if [ -n "$out" ]; then
    echo "--- $s ---"
    echo "$out"
  fi
done

# ------------------------------------------------------------------------------
hr "5. 工作负载的 env（写死在 YAML 里的配置最难发现，必须单独看）"
# ------------------------------------------------------------------------------
$K -n "$NS" get deploy,sts -o yaml 2>/dev/null \
  | grep -iE "$MW" \
  | grep -viE "$SKIP" \
  | grep -E '^\s*(- )?(name|value):' | sort -u | head -80

echo
echo "--- 引用的 ConfigMap / Secret 名称（Helm 部署时用来对关系）---"
$K -n "$NS" get deploy,sts -o yaml 2>/dev/null \
  | grep -E 'configMapRef|secretRef|configMapKeyRef|secretKeyRef' -A1 \
  | grep -E 'name:' | sort -u

# ------------------------------------------------------------------------------
hr "6. Service 与 Endpoints（找指向集群外的出口 + 空端点）"
# ------------------------------------------------------------------------------
echo "--- Service 列表（重点看 ExternalName 与 LoadBalancer）---"
$K -n "$NS" get svc -o custom-columns='NAME:.metadata.name,TYPE:.spec.type,CLUSTER-IP:.spec.clusterIP,EXTERNAL-NAME:.spec.externalName,PORTS:.spec.ports[*].port' 2>/dev/null

echo
echo "--- 空 Endpoints（必然 502，重点排查）---"
if command -v jq >/dev/null 2>&1; then
  $K -n "$NS" get endpoints -o json 2>/dev/null \
    | jq -r '.items[] | select(.subsets==null) | "\(.metadata.namespace)/\(.metadata.name)   EMPTY"'
else
  $K -n "$NS" get endpoints 2>/dev/null | awk '$2=="<none>"'
fi

# ------------------------------------------------------------------------------
hr "7. 需要进 Pod 实测的部分（脚本不自动执行，请确认后手动跑）"
# ------------------------------------------------------------------------------
cat <<'EOF'
下面这些要在业务 Pod 里跑，属于只读命令，但会进入业务容器。
建议在 sit 上先跑一遍，prod 上确认无影响再执行。

# 进容器（只读命令，不修改任何东西；容器没有 sh 就换 bash）
kubectl -n <ns> exec -it <pod> -- sh

# 1) 域名解析成什么 —— 判断是 CLB VIP 还是 Pod IP 直连
nslookup <中间件域名>

# 2) 看跳数 —— 判断是否经过 CEN 云联网 / 对等连接
#    一跳直达 = 同 VPC 直连；两跳以上 = 经过网关
traceroute -n -w 2 <IP> 2>/dev/null || tracepath -n <IP>

# 3) TCP 连通性
nc -zv <IP> <port> -w 3

# 4) 延迟基线 —— 同地域 <2ms / 同城跨地域 5-10ms / 远距离跨地域 30ms 左右
for i in 1 2 3; do
  curl -s -o /dev/null -w "connect=%{time_connect}  total=%{time_total}\n" http://<IP>:<port>/
done

# 5) Pod 出网路由
ip route

# 6) 解析不出来时，先看集群 DNS 是否正常
nslookup kubernetes.default.svc.cluster.local
cat /etc/resolv.conf
EOF

# ------------------------------------------------------------------------------
hr "8. 判定提示（人工看输出结果）"
# ------------------------------------------------------------------------------
cat <<'EOF'
把 sit / uat / prod 三份输出摆在一起，逐项对比：

  host / addr 相同          → 三环境共用同一实例 → 继续看第 2 项
  host / addr 不同          → 独立实例，风险低

  jdbc URL 里的库名         → 同为 app：完全共用（风险最高）
                              sit_app / uat_app / prod_app：同实例不同库（风险高）
  redis://host:6379/N 的 N  → 三环境同 N：Redis 无隔离（注意 FLUSHALL、
                              内存打满、连接数打满都是实例级的，index 隔离是假隔离）
  MQ topic / group 前缀     → 无前缀：共用，消费组会互相抢消息
  Nacos namespace / group   → 空或同为 public：服务列表全串在一起

  注意：同实例不同库 / 不同 db index 都只是"逻辑隔离"，
  实例级的 CPU、连接数、内存、IO 依然互相影响。

以下四项集群内查不到，必须走控制台或问人：
  1. 云托管中间件（TDSQL-C / Redis）的规格、连接数上限、慢查询阈值
     → 云数据库控制台
  2. 跨地域：业务集群地域 vs 中间件地域
     → 容器服务 / 云数据库控制台的「地域」字段
  3. CEN 带宽包水位与限速阈值
     → 云联网 → 带宽管理
  4. 历史事故：sit 压测有没有打到过生产库
     → 只能问前任
EOF

echo
echo "采集完成。建议：三环境各跑一份后 diff，不一致的地方就是要问的问题。"
