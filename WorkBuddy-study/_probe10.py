# -*- coding: utf-8 -*-
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

mains = [(h,r) for h,t,c,r in list_vis() if c=="TXGuiFoundation" and t!="桌面歌词"]
mains.sort(key=lambda x: x[1][2]*x[1][3], reverse=True)
h_main = mains[0][0]
u.MoveWindow(h_main, 0, 0, 1200, 860, True); time.sleep(0.3)

# 激活+最小化
pid = ctypes.c_ulong(); u.GetWindowThreadProcessId(h_main, ctypes.byref(pid))
u.AllowSetForegroundWindow(pid.value)
ctypes.windll.user32.keybd_event(0x12, 0, 0, 0); u.SetForegroundWindow(h_main)
ctypes.windll.user32.keybd_event(0x12, 0, 2, 0); time.sleep(0.3)
def overlap(a, b): return not (a[2]<=b[0] or b[2]<=a[0] or a[3]<=b[1] or b[3]<=a[1])
for h, t, c, r in list_vis():
    if h == h_main: continue
    if r[1] >= 1020: continue
    if overlap(r, (0,0,1200,860)) and not u.IsIconic(h):
        u.ShowWindow(h, 6)
time.sleep(0.5)

im = ImageGrab.grab().convert("RGB")
# 扩大扫描
bg = im.getpixel((50, 30))
hot = []
for x in range(600, 1200):
    cnt = 0
    for y in range(15, 60):
        p = im.getpixel((x, y))
        if abs(p[0]-bg[0])+abs(p[1]-bg[1])+abs(p[2]-bg[2]) > 80:
            cnt += 1
    if cnt > 0: hot.append((x, cnt))
runs = []; s = None
for x, c in hot:
    if s is None: s = (x, x)
    elif x == s[1] + 1: s = (s[0], x)
    elif x <= s[1] + 5: s = (s[0], x)  # 允许小间隔
    else: runs.append(s); s = (x, x)
if s: runs.append(s)
print("icon runs (600-1200):", runs)
# 保存高分辨率图
im.crop((400, 0, 1200, 90)).resize((1600, 180), Image.NEAREST).save("_top6_x2.png")
