# -*- coding: utf-8 -*-
import ctypes, ctypes.wintypes as wt
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32
EnumWindows = u.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
GetWindowTextLength = u.GetWindowTextLengthW
GetWindowTextW = u.GetWindowTextW

def title(h):
    n = GetWindowTextLength(h)
    b = ctypes.create_unicode_buffer(n + 1)
    GetWindowTextW(h, b, n + 1)
    return b.value

out = []
def cb(h, l):
    if u.IsIconic(h):
        u.ShowWindow(h, 9)
        out.append((h, title(h)))
    return True
EnumWindows(EnumWindowsProc(cb), 0)
for h, t in out:
    print("restored", h, t[:40])
