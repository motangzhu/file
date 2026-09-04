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
    class BIH(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32),("biWidth", ctypes.c_int32),("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16),("biBitCount", ctypes.c_uint16),("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32),("biXPelsPerMeter", ctypes.c_int32),("biYPelsPerMeter", ctypes.c_int32),
                    ("biClrUsed", ctypes.c_uint32),("biClrImportant", ctypes.c_uint32)]
    class BI(ctypes.Structure):
        _fields_ = [("h", BIH), ("c", ctypes.c_uint32 * 3)]
    bi = BI(); bi.h.biSize = ctypes.sizeof(BIH); bi.h.biWidth = w; bi.h.biHeight = -hgt
    bi.h.biPlanes = 1; bi.h.biBitCount = 32; bi.h.biCompression = 0
    buf = ctypes.create_string_buffer(w * hgt * 4)
    ctypes.windll.gdi32.GetDIBits(mdc, hb, 0, hgt, buf, ctypes.byref(bi), 0)
    ctypes.windll.gdi32.DeleteObject(hb); ctypes.windll.gdi32.DeleteDC(mdc); u.ReleaseDC(h, hdc)
    return Image.frombuffer("RGBA", (w, hgt), buf, "raw", "BGRA", 0, 0).convert("RGB")

img = grab_window(H_MAIN)
top = img.crop((0, 0, img.width, 80))
top.save("_top3.png")
# 打印右半部分各列的亮度
for x in range(800, 1200, 10):
    samples = [top.getpixel((x, y)) for y in [10, 20, 30, 40, 50]]
    print(x, samples)
