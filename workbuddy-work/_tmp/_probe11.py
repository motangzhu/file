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

# 启动前窗口
before = set(h for h,t,c,r in list_vis())
mains = [(h,r) for h,t,c,r in list_vis() if c=="TXGuiFoundation" and t!="桌面歌词"]
mains.sort(key=lambda x: x[1][2]*x[1][3], reverse=True)
h_main = mains[0][0]
u.MoveWindow(h_main, 0, 0, 1200, 860, True); time.sleep(0.3)
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

import pyautogui
pyautogui.FAILSAFE = False

# 点击 x=1039 y=30 (那个"双气泡"图标)
print("click (1039, 30)...")
pyautogui.click(1039, 30)
time.sleep(1.5)

after = list_vis()
new = [w for w in after if w[0] not in before]
print("new windows after click:")
for h, t, c, r in new:
    print(f"  hwnd={h} class={c} title={t[:40]!r} rect={r}")
print()
print("all vis now:")
for h, t, c, r in after:
    print(f"  hwnd={h} class={c} title={t[:40]!r} rect={r}")

# 截图保存当前状态
im = ImageGrab.grab().convert("RGB")
im.save("_after_click.png")
print("screenshot saved")
