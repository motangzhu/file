# -*- coding: utf-8 -*-
import ctypes, ctypes.wintypes as wt
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32

# 找主窗口
EnumWindows = u.EnumWindows
Proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
results = []
def cb(h, l):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    if b.value == "TXGuiFoundation":
        n = u.GetWindowTextLengthW(h)
        tb = ctypes.create_unicode_buffer(n+1)
        if n: u.GetWindowTextW(h, tb, n+1)
        results.append((h, tb.value, bool(u.IsWindowVisible(h)), bool(u.IsIconic(h))))
    return True
EnumWindows(Proc(cb), 0)
for h, t, v, ic in results:
    print(f"hwnd={h} title={t!r} visible={v} iconic={ic}")
# 恢复任意非"桌面歌词"的可见主窗口
for h, t, v, ic in results:
    if t and t != "桌面歌词" and (not v or ic):
        u.ShowWindow(h, 9)
        print("restored", h, t)
        # 激活
        pid = ctypes.c_ulong(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        u.AllowSetForegroundWindow(pid.value)
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
        u.SetForegroundWindow(h)
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
        break
