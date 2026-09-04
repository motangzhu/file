# -*- coding: utf-8 -*-
import ctypes, ctypes.wintypes as wt, time
from PIL import Image, ImageGrab

ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32
H = 1838118

EnumWindows = u.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
GetWindowTextLength = u.GetWindowTextLengthW
GetWindowTextW = u.GetWindowTextW
IsWindowVisible = u.IsWindowVisible
ShowWindow = u.ShowWindow
SW_MINIMIZE, SW_RESTORE = 6, 9

def rect(h):
    r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)

def title(h):
    n = GetWindowTextLength(h)
    b = ctypes.create_unicode_buffer(n + 1)
    GetWindowTextW(h, b, n + 1)
    return b.value

allw = []
def cb(h, l):
    if IsWindowVisible(h) and title(h):
        allw.append((h, title(h), rect(h)))
    return True
EnumWindows(EnumWindowsProc(cb), 0)

tr = rect(H)
print("qq rect", tr)
print("overlapping windows:")
def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])
for h, t, r in allw:
    if h != H and overlap(r, tr):
        print(f"  hwnd={h:<10} {t[:40]:<42} {r}")

# 最小化遮挡者
saved = []
for h, t, r in allw:
    if h != H and overlap(r, tr):
        ShowWindow(h, SW_MINIMIZE)
        saved.append((h, t))
print("minimized:", [t for _, t in saved])

# 激活 QQ
u.AllowSetForegroundWindow(ctypes.c_ulong(u.GetWindowThreadProcessId(H, None)))
ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
u.SetForegroundWindow(H)
ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
time.sleep(0.8)
print("fg hwnd:", u.GetForegroundWindow(), "target:", H)

im = ImageGrab.grab().convert("RGB")
im.save("_shot_full.png")
crop = im.crop((tr[0], tr[1], tr[2], tr[1] + 70))
crop.save("_shot_topbar.png")
crop.resize((crop.width * 3, crop.height * 3), Image.NEAREST).save("_shot_topbar_x3.png")

bg = crop.getpixel((crop.width // 2, 5))
print("bg", bg)
runs = []; s = None
for x in range(crop.width):
    c = sum(1 for y in range(0, 60) if sum(abs(a - b) for a, b in zip(crop.getpixel((x, y)), bg)) > 60)
    if c >= 3 and s is None: s = x
    elif c < 3 and s is not None:
        if x - s >= 5: runs.append((s, x - 1))
        s = None
print("icon runs:")
for a, b in runs:
    print(f"  x {a:5d}-{b:5d} w={b-a+1:3d} center={(a+b)//2}")
