# -*- coding: utf-8 -*-
import ctypes, ctypes.wintypes as wt, time
from PIL import Image

ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32
H_MAIN = 1838118
u.MoveWindow(H_MAIN, 0, 0, 1200, 860, True)
time.sleep(0.4)

def grab_window(h):
    r = wt.RECT(); u.GetClientRect(h, ctypes.byref(r))
    w, hgt = r.right - r.left, r.bottom - r.top
    hdc = u.GetDC(h); mdc = ctypes.windll.gdi32.CreateCompatibleDC(hdc)
    hb = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc, w, hgt)
    ctypes.windll.gdi32.SelectObject(mdc, hb)
    ctypes.windll.user32.PrintWindow(h, mdc, 0x00000002)
    BI_RGB = 0
    class BIH(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32),("biWidth", ctypes.c_int32),("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16),("biBitCount", ctypes.c_uint16),("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32),("biXPelsPerMeter", ctypes.c_int32),("biYPelsPerMeter", ctypes.c_int32),
                    ("biClrUsed", ctypes.c_uint32),("biClrImportant", ctypes.c_uint32)]
    class BI(ctypes.Structure):
        _fields_ = [("h", BIH), ("c", ctypes.c_uint32 * 3)]
    bi = BI(); bi.h.biSize = ctypes.sizeof(BIH); bi.h.biWidth = w; bi.h.biHeight = -hgt
    bi.h.biPlanes = 1; bi.h.biBitCount = 32; bi.h.biCompression = BI_RGB
    buf = ctypes.create_string_buffer(w * hgt * 4)
    ctypes.windll.gdi32.GetDIBits(mdc, hb, 0, hgt, buf, ctypes.byref(bi), 0)
    ctypes.windll.gdi32.DeleteObject(hb); ctypes.windll.gdi32.DeleteDC(mdc); u.ReleaseDC(h, hdc)
    return Image.frombuffer("RGBA", (w, hgt), buf, "raw", "BGRA", 0, 0).convert("RGB")

img = grab_window(H_MAIN)
top = img.crop((0, 0, img.width, 80))
top.save("_top2.png")
# 找按钮 (背景是 (30,30,30) 附近, 按钮图标较亮)
bg = (30, 30, 30)
# 在右半部分扫描
def is_btn_pixel(p, bg):
    return p[0] > 100 or p[1] > 100 or p[2] > 100  # 较亮
# 找连通 x 范围，按列累计
col_score = []
for x in range(800, 1200):
    s = 0
    for y in range(15, 55):
        p = top.getpixel((x, y))
        if (p[0] + p[1] + p[2]) > 360:  # 亮
            s += 1
    col_score.append((x, s))
# 输出 x with s>0
runs = []; s = None
for x, c in col_score:
    if c > 0 and s is None: s = x
    elif c == 0 and s is not None:
        runs.append((s, x - 1))
        s = None
if s is not None: runs.append((s, col_score[-1][0]))
print("icon runs in right half (x_start,x_end,center,width):")
for a, b in runs:
    print(f"  {a:4d}-{b:4d}  c={(a+b)//2:4d}  w={b-a+1}")
