# -*- coding: utf-8 -*-
"""按探测前的初始状态还原所有窗口位置"""
import ctypes, ctypes.wintypes as wt, time
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.windll.user32

# hwnd -> 初始 rect (left, top, width, height)，None 表示只需从最小化恢复
RESTORE = {
    1377622: (688, 0, 662, 97),        # 桌面歌词
    131774:  (0, 0, 169, 1080),        # montab
    132674:  (414, 127, 1130, 763),    # 企业微信
    264678:  (163, -8, 1765, 1096),    # WorkBuddy
    1903262: (421, 132, 1148, 817),    # 微信
    200290:  (161, -8, 1767, 1096),    # Ubuntu
    1838118: (517, 77, 1100, 800),     # QQ 音乐主窗口
    68210:   (161, -8, 1767, 1096),    # CodeBuddy
    68024:   (161, -8, 1767, 1096),    # VS Code
    67696:   (161, -8, 1767, 1096),    # Chrome
    920062:  (652, 173, 1096, 777),    # 文件资源管理器
    9506662: (0, 1, 958, 880),         # 系统设置
    2953280: (169, 84, 974, 889),      # 系统设置
    66478:   (0, 0, 1920, 1080),       # Windows 输入体验
}

for hwnd, rect in RESTORE.items():
    if not u.IsWindow(hwnd):
        print(f"  skip  {hwnd} (window gone)")
        continue
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, 9)   # SW_RESTORE
        time.sleep(0.15)
    l, t, w, h = rect
    u.MoveWindow(hwnd, l, t, w, h, True)
    time.sleep(0.1)
    r = wt.RECT(); u.GetWindowRect(hwnd, ctypes.byref(r))
    print(f"  ok    {hwnd:<9} -> ({(r.left, r.top, r.right-r.left, r.bottom-r.top)})")

print("\ndone")
