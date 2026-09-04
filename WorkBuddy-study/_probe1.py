# -*- coding: utf-8 -*-
import ctypes, ctypes.wintypes as wt, sys
from PIL import ImageGrab

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

u = ctypes.windll.user32
EnumWindows = u.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
GetWindowTextLength = u.GetWindowTextLengthW
GetWindowText = u.GetWindowTextW
IsWindowVisible = u.IsWindowVisible
GetClassName = u.GetClassNameW
GetWindowThreadProcessId = u.GetWindowThreadProcessId

def rect(h):
    r = wt.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)

rows = []
def cb(h, l):
    if IsWindowVisible(h):
        n = GetWindowTextLength(h)
        if n:
            b = ctypes.create_unicode_buffer(n + 1)
            GetWindowText(h, b, n + 1)
            cn = ctypes.create_unicode_buffer(256)
            GetClassName(h, cn, 256)
            pid = ctypes.c_ulong()
            GetWindowThreadProcessId(h, ctypes.byref(pid))
            rows.append((h, b.value, cn.value, pid.value, rect(h)))
    return True

EnumWindows(EnumWindowsProc(cb), 0)
print("=== visible windows with title ===")
for h, t, cn, pid, r in rows:
    print(f"hwnd={h:<10} pid={pid:<7} class={cn:<28} title={t[:40]:<42} rect={r}")
print()
print("screen:", u.GetSystemMetrics(0), u.GetSystemMetrics(1))
print("dpi aware ctx:", ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(ctypes.c_int())) if hasattr(ctypes.windll, 'shcore') else 'n/a')
