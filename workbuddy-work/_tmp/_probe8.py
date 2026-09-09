# -*- coding: utf-8 -*-
"""完整版临时测试（最终会把这份精简后写到 qmusic_lyric_theme.py）"""
import ctypes, ctypes.wintypes as wt, time, sys, math
from PIL import ImageGrab, Image

try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
except: ctypes.windll.user32.SetProcessDPIAware()

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
    EnumWindows = u.EnumWindows
    Proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, l):
        if u.IsWindowVisible(h) and title(h):
            out.append((h, title(h), cls(h), rect(h)))
        return True
    EnumWindows(Proc(cb), 0); return out
def activate(h):
    pid = ctypes.c_ulong(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    u.AllowSetForegroundWindow(pid.value)
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
    u.SetForegroundWindow(h)
    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.3)

# ---- 1) 主窗口：TXGuiFoundation，非"桌面歌词"，取面积最大 ----
mains = [(h,r) for h,t,c,r in list_vis() if c=="TXGuiFoundation" and t!="桌面歌词"]
mains.sort(key=lambda x: x[1][2]*x[1][3], reverse=True)
h_main, mr = mains[0]
print("main hwnd", h_main, "rect", mr)

# 2) 桌面歌词
desktop_lyric = None
for h,t,c,r in list_vis():
    if c=="TXGuiFoundation" and t=="桌面歌词":
        desktop_lyric = h; break
print("desktop lyric hwnd", desktop_lyric)

# 3) 移动主窗口到 (0,0,1200,860)，激活
u.MoveWindow(h_main, 0, 0, 1200, 860, True); time.sleep(0.4)
activate(h_main)

# 4) 临时最小化与主窗口矩形相交的可见窗口（排除主窗口+桌面歌词+任务栏所在区域）
def rects_overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
saved_min = []  # (h, orig_rect, orig_iconic)
for h,t,c,r in list_vis():
    if h in (h_main, desktop_lyric): continue
    if r[1] >= 1020: continue  # 任务栏/系统区
    if rects_overlap(r, (0,0,1200,860)):
        was_iconic = bool(u.IsIconic(h))
        if not was_iconic:
            u.ShowWindow(h, 6)
        saved_min.append((h, r, was_iconic))
print("minimized:", len(saved_min))
time.sleep(0.5)

# 5) 截图
im = ImageGrab.grab().convert("RGB")
print("screen", im.size)
top = im.crop((0, 0, 1200, 90))
top.save("_top4.png")
top.resize((top.width*2, top.height*2), Image.NEAREST).save("_top4_x2.png")
print("top saved")
