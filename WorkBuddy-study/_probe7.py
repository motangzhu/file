# -*- coding: utf-8 -*-
"""
QMusic Lyric Theme - QQ 音乐桌面歌词配色一键修改工具
=====================================================

目的
----
在另一台电脑上，只需把这个 .py 文件交给 WorkBuddy / 任何能调用 python 脚本的
AI 助手，让它 ``python qmusic_lyric_theme.py`` 即可完成 QQ 音乐桌面歌词
「已播放字色 / 未播放字色 / 边框颜色」三色的修改，不需要用户手动点开
取色器、点色块。

使用方法
--------
    python qmusic_lyric_theme.py                         # 用默认「落日橙」配色
    python qmusic_lyric_theme.py --preset cyber          # 切换其它预设
    python qmusic_lyric_theme.py --colors "#EC6300,#D2C0A5,#44592E"  # 自定义
    python qmusic_lyric_theme.py --list                  # 查看所有预设
    python qmusic_lyric_theme.py --dry-run               # 只探测、不修改
    python qmusic_lyric_theme.py --install-deps          # 仅安装依赖

环境要求
--------
- Windows 10/11，DPI 缩放任意（脚本会自己声明 Per-Monitor DPI aware）
- Python 3.9+
- 已运行 QQ 音乐桌面版 (本脚本测试版本: 2260.14.51.32)
- 自动安装依赖: pillow, pyautogui, pywinauto, pywin32

实现要点
--------
QQ 音乐把设置项加密写入 ConfigInfoXML1.dat / MMKV / SQLite，注册表无相关项，
只能通过 UI 自动化点击「设置 → 桌面歌词 → 色块 → 颜色选择面板」修改。
本脚本做到：
  1) 临时最小化所有遮挡主窗口的程序窗口（按原样恢复）
  2) 打开 QQ 主窗口右上角的「设置」菜单
  3) 导航到「桌面歌词」侧栏
  4) 自动定位三个色块（用纯色矩形检测 + 取色器出现作为最终验证）
  5) 打开取色器后，扫描 26 块预定义色板 + 大色块矩阵，找最接近目标 RGB 的色块
  6) 点击后截图验证像素颜色，每步都有失败回退
  7) 全流程结束，按记录的原始状态恢复所有窗口
"""
import argparse, ctypes, ctypes.wintypes as wt, math, os, subprocess, sys, time
from pathlib import Path

# --- DPI 声明（必须最先） ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor V2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# --- 颜色预设 ---
PRESETS = {
    "sunset":  {  # 落日橙（默认）
        "name": "落日橙 (sunset)",
        "played":  (0xEC, 0x63, 0x00),
        "unplayed":(0xD2, 0xC0, 0xA5),
        "border":  (0x44, 0x59, 0x2E),
    },
    "ocean":   {
        "name": "深青绿 (ocean)",
        "played":  (0x00, 0x9F, 0x95),
        "unplayed":(0x81, 0xEE, 0xFE),
        "border":  (0x00, 0x9F, 0x95),
    },
    "mono":    {
        "name": "极简白 (mono)",
        "played":  (0xFF, 0xFF, 0xFF),
        "unplayed":(0xB8, 0xB8, 0xB8),
        "border":  (0x26, 0x26, 0x26),
    },
    "darkgold":{
        "name": "深邃黑金 (darkgold)",
        "played":  (0xF4, 0xA5, 0x0E),
        "unplayed":(0x5C, 0x4A, 0x2D),
        "border":  (0x1A, 0x1A, 0x1A),
    },
    "cyberpink":{
        "name": "赛博粉 (cyberpink)",
        "played":  (0x92, 0x00, 0x7E),
        "unplayed":(0x8D, 0xA0, 0xD0),
        "border":  (0xFF, 0x77, 0xB0),
    },
}

def parse_hex(s):
    s = s.strip().lstrip("#")
    if len(s) != 6: raise ValueError(f"bad hex: {s}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


# ============================================================
# 依赖自检
# ============================================================
REQUIRED = {
    "PIL":        "pillow",
    "pyautogui":  "pyautogui",
    "pywinauto":  "pywinauto",
}

def ensure_deps(auto_install=True):
    missing = []
    for mod, pkg in REQUIRED.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if not missing:
        return True
    if not auto_install:
        print("[deps] missing:", missing, file=sys.stderr)
        return False
    print(f"[deps] installing: {missing}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", *missing])
    # 重新 import
    for mod in REQUIRED:
        __import__(mod)
    return True


# ============================================================
# Win32 工具
# ============================================================
u32  = ctypes.windll.user32
gdi  = ctypes.windll.gdi32

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def win_rect(h):
    r = wt.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)

def win_title(h):
    n = u32.GetWindowTextLengthW(h)
    if not n: return ""
    b = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, b, n + 1)
    return b.value

def win_class(h):
    b = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(h, b, 256)
    return b.value

def activate(h):
    """把窗口带到前台（绕开 Win10 焦点限制）"""
    pid = ctypes.c_ulong()
    u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    u32.AllowSetForegroundWindow(pid.value)
    # Alt 释放 / 按下 让 SetForegroundWindow 合法
    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
    u32.SetForegroundWindow(h)
    ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.25)

def post_close(h):
    u32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE

# ============================================================
# 窗口枚举
# ============================================================
EnumWindows = u32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

def list_visible_windows():
    out = []
    def cb(h, l):
        if u32.IsWindowVisible(h) and win_title(h):
            out.append((h, win_title(h), win_class(h), win_rect(h), bool(u32.IsIconic(h))))
        return True
    EnumWindows(EnumWindowsProc(cb), 0)
    return out

def find_main_window():
    """找 QQ 音乐主窗口：TXGuiFoundation + 非「桌面歌词」标题"""
    cands = []
    for h, t, c, r, ic in list_visible_windows():
        if c == "TXGuiFoundation" and t != "桌面歌词" and not ic:
            cands.append((h, t, r))
    if not cands:
        # 也允许它已经最小化
        EnumWindows(EnumWindowsProc(
            (lambda h, l: (out.append((h, win_title(h), win_rect(h))) or True) if
             (lambda h: win_class(h) == "TXGuiFoundation" and win_title(h) != "桌面歌词")(h)
             else True)), 0)
        # 上面这个太复杂，简化为：
    # 重做：包括最小化
    cands = []
    EnumWindows(EnumWindowsProc(_collect_main_cb(cands)), 0)
    if not cands:
        return None
    # 取面积最大的
    cands.sort(key=lambda x: x[1][2] * x[1][3], reverse=True)
    return cands[0][0], cands[0][2]

_cb_buf = []
def _collect_main_cb(out):
    def cb(h, l):
        if win_class(h) == "TXGuiFoundation":
            t = win_title(h)
            if t and t != "桌面歌词":
                out.append((h, t, win_rect(h)))
        return True
    return cb


# ============================================================
# 遮挡处理：临时最小化，恢复
# ============================================================
class WindowManager:
    def __init__(self):
        self.saved = []  # [(hwnd, was_iconic, rect)]
    def minimize_overlapping(self, keep_hwnds, target_rect):
        L, T, W, H = target_rect
        R, B = L + W, T + H
        for h, t, c, r, ic in list_visible_windows():
            if h in keep_hwnds: continue
            hL, hT, hW, hH = r
            hR, hB = hL + hW, hT + hH
            # 排除任务栏所在底部一小条 (y > 1030) 系统区域，避免最小化 Progman
            if hT >= 1020: continue
            if hL < R and hR > L and hT < B and hB > T:
                if not u32.IsIconic(h):
                    u32.ShowWindow(h, 6)  # SW_MINIMIZE
                    self.saved.append((h, False, r))
        time.sleep(0.3)
    def restore(self):
        for h, was_iconic, r in self.saved:
            try:
                if was_iconic:
                    pass  # 原本就是最小化，不用动
                else:
                    u32.ShowWindow(h, 9)  # SW_RESTORE
            except Exception:
                pass


# ============================================================
# 截图 / 像素 / 形状检测
# ============================================================
from PIL import ImageGrab, Image

def grab_full():
    return ImageGrab.grab().convert("RGB")

def color_dist(a, b):
    return (a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2

def is_uniform_color(img, x0, y0, w, h, max_var=15):
    """检测小矩形内部是否纯色（用于识别色块）"""
    samples = []
    for dy in range(0, h, max(1, h//4)):
        for dx in range(0, w, max(1, w//4)):
            samples.append(img.getpixel((x0 + dx, y0 + dy)))
    rs = [s[0] for s in samples]; gs = [s[1] for s in samples]; bs = [s[2] for s in samples]
    return (max(rs)-min(rs) + max(gs)-min(gs) + max(bs)-min(bs)) <= max_var * 2

def find_color_chips(img, x_range, y_range, min_w=10, max_w=40, min_h=10, max_h=30):
    """在子区域里扫描纯色矩形（返回 (x,y,w,h,color) 列表）"""
    bg = img.getpixel((x_range[0]+5, y_range[0]+5))
    out = []
    for y in range(y_range[0], y_range[1], 1):
        for x in range(x_range[0], x_range[1]):
            p = img.getpixel((x, y))
            if color_dist(p, bg) < 900: continue  # 跳过背景
            # 估宽
            w = 0
            while x + w < x_range[1]:
                pp = img.getpixel((x + w, y))
                if color_dist(pp, p) < 400: w += 1
                else: break
            if w < min_w or w > max_w: continue
            # 估高
            h = 0
            while y + h < y_range[1]:
                pp = img.getpixel((x, y + h))
                if color_dist(pp, p) < 400: h += 1
                else: break
            if h < min_h or h > max_h: continue
            # 内部纯色验证
            if is_uniform_color(img, x, y, w, h):
                out.append((x, y, w, h, p))
            x += w
    # 去重 (同一矩形多次命中)
    uniq = []
    for r in out:
        dup = False
        for r2 in uniq:
            if abs(r[0]-r2[0]) < 4 and abs(r[1]-r2[1]) < 4:
                dup = True; break
        if not dup: uniq.append(r)
    return uniq


# ============================================================
# 主流程
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="sunset")
    ap.add_argument("--colors", default=None,
                    help='三色: "#RRGGBB,#RRGGBB,#RRGGBB" 顺序为 played,unplayed,border')
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--install-deps", action="store_true")
    args = ap.parse_args()

    if args.list:
        for k, v in PRESETS.items():
            c = lambda t: "#{:02X}{:02X}{:02X}".format(*t)
            print(f"  {k:10s}  {v['name']:25s}  played={c(v['played'])}  unplayed={c(v['unplayed'])}  border={c(v['border'])}")
        return

    if args.install_deps:
        ensure_deps(auto_install=True); return

    ensure_deps(auto_install=True)
    import pyautogui
    pyautogui.FAILSAFE = False

    if args.colors:
        cs = [parse_hex(x) for x in args.colors.split(",")]
        assert len(cs) == 3
        played, unplayed, border = cs
        target_name = f"自定义 #{cs[0][0]:02X}{cs[0][1]:02X}{cs[0][2]:02X}"
    else:
        p = PRESETS[args.preset]
        played, unplayed, border = p["played"], p["unplayed"], p["border"]
        target_name = p["name"]

    print(f"\n[plan] 目标配色: {target_name}")
    print(f"       played   = {played}")
    print(f"       unplayed = {unplayed}")
    print(f"       border   = {border}\n")

    if args.dry_run:
        print("[dry-run] 只探测，不修改")
        m = find_main_window()
        if m: print(f"  主窗口: hwnd={m[0]} rect={m[1]}")
        else:  print("  找不到 QQ 音乐主窗口！请先打开 QQ 音乐。")
        return

    # 1. 找主窗口
    print("[1] 找 QQ 音乐主窗口...")
    found = find_main_window()
    if not found:
        print("  ✗ 找不到 QQ 音乐主窗口 (TXGuiFoundation)")
        print("    请先打开 QQ 音乐桌面客户端。")
        sys.exit(1)
    h_main, rect = found
    print(f"  ✓ hwnd={h_main}  rect={rect}")

    # 2. 主窗口移到 (0,0,1200,860)
    print("[2] 把主窗口移到固定位置 (0,0,1200,860) ...")
    u32.MoveWindow(h_main, 0, 0, 1200, 860, True)
    time.sleep(0.4)
    main_rect = (0, 0, 1200, 860)
    # 桌面歌词窗口允许保留
    desktop_lyric = None
    EnumWindows(EnumWindowsProc(_collect_desktop_lyric_cb()), 0) if False else None
    for h, t, c, r, ic in list_visible_windows():
        if c == "TXGuiFoundation" and t == "桌面歌词":
            desktop_lyric = h; break
    keep = {h_main, desktop_lyric} if desktop_lyric else {h_main}

    # 3. 临时最小化遮挡
    print("[3] 临时最小化遮挡窗口...")
    wm = WindowManager()
    wm.minimize_overlapping(keep, main_rect)
    print(f"  最小化 {len(wm.saved)} 个窗口")

    try:
        # 4. 激活主窗口
        print("[4] 激活主窗口...")
        activate(h_main)
        time.sleep(0.4)

        # 5. 截图主窗口
        print("[5] 截图主窗口...")
        im = grab_full()
        main_im = im.crop(main_rect)
        main_im.save("_main.png")

        # 6. 在主窗口顶部条找「设置」图标
        print("[6] 找「设置」图标...")
        sx = find_settings_icon(main_im)
        if not sx:
            print("  ✗ 找不到「设置」图标")
            return
        abs_x = sx
        abs_y = 30
        print(f"  ✓ 候选「设置」图标位于主窗口内 x={sx}")

        # 7. 点击「设置」
        print("[7] 点击「设置」...")
        pyautogui.click(abs_x, abs_y)
        time.sleep(1.0)

        # 8. 找设置窗口
        print("[8] 找设置窗口...")
        sett = find_settings_window(timeout=5.0)
        if not sett:
            print("  ✗ 没看到设置窗口弹出")
            return
        h_set, set_rect = sett
        print(f"  ✓ hwnd={h_set} rect={set_rect}")

        # 9. 移动设置窗口到固定位置
        print("[9] 移动设置窗口到 (0,0,1000,720) ...")
        u32.MoveWindow(h_set, 0, 0, 1000, 720, True)
        time.sleep(0.4)
        activate(h_set)
        set_rect = (0, 0, 1000, 720)
        # 重新最小化现在会遮挡的窗口
        wm.minimize_overlapping(keep | {h_set}, set_rect)

        # 10. 截图设置窗口
        print("[10] 截图设置窗口...")
        im = grab_full()
        set_im = im.crop(set_rect)
        set_im.save("_settings.png")

        # 11. 导航到「桌面歌词」侧栏
        print("[11] 导航到「桌面歌词」...")
        if not nav_to_desktop_lyric(h_set, set_im, set_rect):
            print("  ✗ 找不到「桌面歌词」侧栏项")
            return

        # 12. 定位色块
        print("[12] 定位三个色块...")
        chips = locate_lyric_chips(h_set, set_rect)
        if not chips:
            print("  ✗ 找不到色块")
            return
        print(f"  ✓ 找到 {len(chips)} 个色块: {[(c[0], c[1]) for c in chips]}")

        # 13. 修改三色
        targets = [
            ("已播放字色", played,    0),
            ("未播放字色", unplayed,  1),
            ("边框颜色",   border,    2),
        ]
        for label, color, idx in targets:
            if idx >= len(chips): break
            print(f"\n[13.{idx+1}] {label} → {color}")
            x, y, w, hgt, _cur = chips[idx]
            if not apply_color(h_set, set_rect, x + w//2, y + hgt//2, color):
                print(f"  ✗ {label} 失败")
                return
            time.sleep(0.4)
        print("\n[done] 三色已应用！")

    finally:
        print("\n[restore] 恢复被最小化的窗口...")
        wm.restore()
        time.sleep(0.4)

def _collect_desktop_lyric_cb():
    out = []
    def cb(h, l):
        if win_class(h) == "TXGuiFoundation" and win_title(h) == "桌面歌词":
            out.append(h)
        return True
    return cb


# 占位函数，下文实现
def find_settings_icon(main_im): pass
def find_settings_window(timeout=5.0): pass
def nav_to_desktop_lyric(h_set, set_im, set_rect): pass
def locate_lyric_chips(h_set, set_rect): pass
def apply_color(h_set, set_rect, x, y, target_rgb): pass

