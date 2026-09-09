#!/bin/bash

# 切换到项目目录
cd /d/files || { echo "❌ 目录不存在！"; exit 1; }

echo "当前目录：$(pwd)"

# 1. 暂存所有变化（包括新文件、修改、删除）
git add -A

# 2. 检查暂存区是否有内容
if git diff --cached --quiet; then
    echo "✅ 没有需要提交的更改（可能没有任何文件变化）。"
    exit 0
fi

# 3. 生成提交信息
timestamp=$(date "+%Y-%m-%d %H:%M:%S")
read -p "请输入提交信息（直接回车使用默认）：" msg
if [ -z "$msg" ]; then
    msg="自动同步 $timestamp"
fi

# 4. 提交
git commit -m "$msg"

# 5. 推送
if git push; then
    echo "✅ 推送完成！时间：$timestamp"
else
    echo "❌ 推送失败，请检查错误信息"
fi

read -p "按回车退出"