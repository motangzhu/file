#!/bin/bash
# 自动切换到项目目录
cd /d/files || { echo "❌ 目录不存在！"; exit 1; }

echo "📂 当前目录：$(pwd)"

# 检查是否有更改需要提交
if git diff --quiet && git diff --cached --quiet; then
    echo "💡 没有需要提交的更改，直接推送..."
    git push
    echo "✅ 完成！"
    read -p "按回车退出"
    exit 0
fi

# 提交更改
timestamp=$(date "+%Y-%m-%d %H:%M:%S")
read -p "请输入提交信息（直接回车使用默认）: " msg
if [ -z "$msg" ]; then
    msg="自动同步 $timestamp"
fi

git add .
git commit -m "$msg"
git push

if [ $? -eq 0 ]; then
    echo "✅ 推送完成！时间：$timestamp"
else
    echo "❌ 推送失败，请检查错误信息"
fi

read -p "按回车退出"