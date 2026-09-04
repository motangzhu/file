# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
"""
探测脚本 v4：把主窗口移动到固定位置，用 PrintWindow 抓取顶部条（绕开遮挡），
识别右上角"设置"图标，点击后验证是否弹出 QQ 音乐设置窗口。
"""
import ctypes, ctypes.wintypes as wt, time, sys
from PIL import Image

ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32
H_MAIN = 1838118  # QQ 音乐主窗口

# 把主窗口放到固定位置 / 大小
def move(h, x, y, w, hgt):
    u.MoveWindow(h, x, y, w, hgt, True)
move(H_MAIN, 0, 0, 1200, 860)
time.sleep(0.5)

# PrintWindow 抓取
PW_RENDERFULLCONTENT = 0x00000002
def grab(h, bbox=None):
    r = wt.RECT()
    u.GetClientRect(h, ctypes.byref(r))
    L, T, R, B = r.left, r.top, r.right, r.bottom
    w, hgt = R - L, B - T
    bmp = ctypes.create_string_buffer(w * hgt * 4)
    hdc_window = u.GetDC(h)
    hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_window)
    hbmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc_window, w, hgt)
    ctypes.windll.gdi32.SelectObject(hdc_mem, hbmp)
    # PW requires top-level hwnd to be visible; client hwnd won't work for childless windows
    # We grab the window by hwnd directly:
    ctypes.windll.user32.PrintWindow(h, hdc_mem, PW_RENDERFULLCONTENT)
    # read pixels via GetDIBits
    BI_RGB = 0
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                    ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                    ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                    ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                    ("biClrImportant", ctypes.c_uint32)]
    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -hgt  # top-down
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = BI_RGB
    ctypes.windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, hgt, bmp, ctypes.byref(bi), 0)
    ctypes.windll.gdi32.DeleteObject(hbmp)
    ctypes.windll.gdi32.DeleteDC(hdc_mem)
    u.ReleaseDC(h, hdc_window)
    img = Image.frombuffer("RGBA", (w, hgt), bmp, "raw", "BGRA", 0, 0).convert("RGB")
    if bbox: img = img.crop(bbox)
    return img

img = grab(H_MAIN)
print("grabbed", img.size)
img.save("_pw_main.png")
top = img.crop((0, 0, img.width, 80))
top.save("_pw_top.png")
top.resize((top.width * 2, top.height * 2), Image.NEAREST).save("_pw_top_x2.png")
