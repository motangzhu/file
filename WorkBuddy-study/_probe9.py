# -*- coding: utf-8 -*-
"""点击右上角矩形按钮，验证是否弹出设置窗口"""
import ctypes, ctypes.wintypes as wt, time
from PIL import ImageGrab, Image

ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32

def rect(h):
    r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)
def title(h):
    n = u.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n+1); u.GetWindowTextW(h, b, n+1); return b.value
def cls(h):
    b = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, b, 256); return b.value
def list_vis():
    out = []
    Proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, l):
        if u.IsWindowVisible(h) and title(h):
            out.append((h, title(h), cls(h), rect(h)))
        return True
    u.EnumWindows(Proc(cb), 0); return out

# 启动前：列出已有窗口
before = list_vis()
print("BEFORE windows:", len(before))
for h,t,c,r in before:
    if c == "TXGuiFoundation":
        print(f"  hwnd={h} class={c} title={t[:40]} rect={r}")

# 主窗口
mains = [(h,r) for h,t,c,r in before if c=="TXGuiFoundation" and t!="桌面歌词"]
mains.sort(key=lambda x: x[1][2]*x[1][3], reverse=True)
h_main = mains[0][0]
print("\nmain hwnd", h_main, "rect", mains[0][1])

u.MoveWindow(h_main, 0, 0, 1200, 860, True); time.sleep(0.3)
activate_pid = ctypes.c_ulong()
u.GetWindowThreadProcessId(h_main, ctypes.byref(activate_pid))
u.AllowSetForegroundWindow(activate_pid.value)
ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
u.SetForegroundWindow(h_main)
ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
time.sleep(0.3)

# 临时最小化遮挡者
def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
saved = []
for h, t, c, r in list_vis():
    if h == h_main: continue
    if r[1] >= 1020: continue
    if overlap(r, (0, 0, 1200, 860)):
        if not u.IsIconic(h):
            u.ShowWindow(h, 6)
            saved.append((h, r))
time.sleep(0.5)

import pyautogui
pyautogui.FAILSAFE = False

# 截图当前主窗口
im = ImageGrab.grab().convert("RGB")
im.crop((0, 0, 1200, 90)).resize((2400, 180), Image.NEAREST).save("_top5_x2.png")
# 找到那个矩形按钮的中心: x≈1080, y≈30
# 但先精确扫描：找右半部分 y 范围 15-50 的暗色（皮肤淡蓝）外最显著的按钮
# 浅蓝皮肤上按钮的图标是深色（比背景暗）
bg = im.getpixel((50, 30))  # 已知背景色
print("bg", bg)
# 扫描 y=20-50 找与背景色差 > 80 的像素
hot_cols = []
for x in range(900, 1200):
    cnt = 0
    for y in range(20, 55):
        p = im.getpixel((x, y))
        if abs(p[0]-bg[0]) + abs(p[1]-bg[1]) + abs(p[2]-bg[2]) > 80:
            cnt += 1
    if cnt > 0: hot_cols.append((x, cnt))
print("hot cols (x, count):", hot_cols[:30], "...", hot_cols[-10:] if len(hot_cols) > 30 else "")

# 分组连续区间
runs = []; s = None
for x, c in hot_cols:
    if s is None: s = (x, x)
    elif x == s[1] + 1: s = (s[0], x)
    else: runs.append(s); s = (x, x)
if s: runs.append(s)
print("icon runs:", runs)
