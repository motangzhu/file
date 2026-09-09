# -*- coding: utf-8 -*-
import ctypes, ctypes.wintypes as wt, time
from PIL import ImageGrab, Image
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32

# 找精简模式窗口
EnumWindows = u.EnumWindows
Proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
results = []
def cb(h, l):
    b = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, b, 256)
    if b.value == 'TXGuiFoundation':
        n = u.GetWindowTextLengthW(h)
        tb = ctypes.create_unicode_buffer(n+1)
        if n: u.GetWindowTextW(h, tb, n+1)
        if '精简' in tb.value:
            r = wt.RECT(); u.GetWindowRect(h, ctypes.byref(r))
            results.append((h, tb.value, r))
    return True
EnumWindows(Proc(cb), 0)
print("simplified mode windows:", results)
if not results:
    print("no simplified mode window found")
    import sys; sys.exit(0)
h, t, r = results[0]
print("target hwnd", h, "rect", (r.left, r.top, r.right - r.left, r.bottom - r.top))

# 截图
im = ImageGrab.grab().convert("RGB")
crop = im.crop((r.left, r.top, r.right, r.bottom))
crop.save("_simplified.png")
crop.resize((crop.width*3, crop.height*3), Image.NEAREST).save("_simplified_x3.png")
print("saved simplified mode screenshot")
