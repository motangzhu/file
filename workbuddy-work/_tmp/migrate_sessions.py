# -*- coding: utf-8 -*-
# 把 WorkBuddy 数据库里挂在旧工作区的 45 条会话迁移到新工作区
# 用法：完全退出 WorkBuddy 客户端（托盘图标右键 -> 退出）后运行：
#   python "D:\files\workbuddy-work\_tmp\migrate_sessions.py"
import datetime
import shutil
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DB_DIR = Path.home() / ".workbuddy"
DB = DB_DIR / "workbuddy.db"
OLD = r"D:\files\WorkBuddy-study"
NEW = r"D:\files\workbuddy-work"

# 0) 基本检查
assert DB.exists(), f"找不到数据库: {DB}"
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# 1) 备份三件套（db / -wal / -shm）
for suffix in ["", "-wal", "-shm"]:
    src = DB_DIR / (DB.name + suffix)
    if src.exists():
        dst = DB_DIR / (DB.name + suffix + f".bak_{stamp}")
        shutil.copy2(src, dst)
        print(f"已备份: {dst.name}")

# 2) 独占写锁探测——客户端没退出会在这里报错，不会写坏数据
con = sqlite3.connect(DB, timeout=3)
try:
    con.execute("BEGIN IMMEDIATE")
except sqlite3.OperationalError as e:
    print(f"数据库被占用，WorkBuddy 可能还没完全退出：{e}")
    print("请从托盘右键退出客户端后重试。数据未做任何修改。")
    sys.exit(1)

try:
    cur = con.cursor()
    n1 = cur.execute(
        "UPDATE sessions SET cwd = ? WHERE cwd = ?", (NEW, OLD)
    ).rowcount
    n2 = cur.execute(
        "DELETE FROM workspaces WHERE path = ?", (OLD,)
    ).rowcount
    con.commit()
    print(f"完成：{n1} 条会话已迁到 {NEW}")
    print(f"完成：旧空间注册删除 {n2} 条")
    print("现在可以重新打开 WorkBuddy 了。如需回滚，把 .bak_"
          + stamp + " 三个文件改回原名即可。")
except Exception as e:
    con.rollback()
    print(f"出错已回滚：{e}")
finally:
    con.close()
