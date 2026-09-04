# -*- coding: utf-8 -*-
import ctypes, ctypes.wintypes as wt
from PIL import Image, ImageGrab

ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32
H = 1838118
r = wt.RECT(); u.GetWindowRect(H, ctypes.byref(r))
print("main rect", (r.left, r.top, r.right - r.left, r.bottom - r.top))
im = ImageGrab.grab().convert("RGB")
im.save("_shot_main.png")
crop = im.crop((r.left, r.top, r.right, r.top + 70))
crop.save("_shot_topbar.png")
crop.resize((crop.width * 3, crop.height * 3), Image.NEAREST).save("_shot_topbar_x3.png")
print("saved")

# 扫描顶部条上的非背景像素团（图标）
bg = crop.getpixel((crop.width // 2, 5))
print("bg sample", bg)
cols = []
for x in range(crop.width):
    cnt = 0
    for y in range(0, 60):
        p = crop.getpixel((x, y))
        if abs(p[0]-bg[0]) + abs(p[1]-bg[1]) + abs(p[2]-bg[2]) > 60:
            cnt += 1
    cols.append(cnt)
# 找连续区间
runs = []
s = None
for x, c in enumerate(cols):
    if c >= 3 and s is None:
        s = x
    elif c < 3 and s is not None:
        if x - s >= 6:
            runs.append((s, x - 1))
        s = None
if s is not None:
    runs.append((s, len(cols) - 1))
print("icon runs (x0,x1,width):")
for a, b in runs:
    print(f"  {a:5d} {b:5d} w={b-a+1:3d}  center={(a+b)//2}")
