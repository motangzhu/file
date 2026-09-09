# -*- coding: utf-8 -*-
# 把工作区里的个人学习整理 md 渲染为 A4 打印友好的 HTML（放大排版）
import re
import pathlib
import markdown

BASE = pathlib.Path(r"D:\files\WorkBuddy-study")
FILES = [
    "Kong网关与TKE-Ingress梳理.md",
    "Service-Ingress与Kong服务路由概念对照.md",
    "CLB类型Ingress学习整理.md",
    "TKE网络管理学习整理.md",
]

CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
  background: #f5f6f7; color: #1f2328; line-height: 1.85; font-size: 17px;
}
.page {
  max-width: 1040px; margin: 24px auto; background: #fff;
  padding: 60px 72px; box-shadow: 0 1px 4px rgba(0,0,0,.08); border-radius: 6px;
}
h1 { font-size: 32px; border-bottom: 3px solid #1f2328; padding-bottom: 14px; margin-bottom: 22px; }
h2 {
  font-size: 24px; margin: 38px 0 14px; padding: 8px 0 8px 14px;
  border-left: 4px solid #1f2328; background: #fafafa;
}
h3 { font-size: 20px; margin: 26px 0 10px; }
h4 { font-size: 17px; margin: 20px 0 8px; }
p { margin: 10px 0; }
ul, ol { margin: 10px 0 10px 26px; }
li { margin: 6px 0; }
a { color: #0b57d0; text-decoration: none; word-break: break-all; }
a:hover { text-decoration: underline; }
table { border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 16px; }
th, td { border: 1px solid #d9dce1; padding: 10px 12px; text-align: left; vertical-align: top; word-break: break-word; }
th { background: #f0f1f3; font-weight: 600; }
tr:nth-child(even) td { background: #fbfbfc; }
code {
  font-family: Consolas, "Courier New", monospace; font-size: 15px;
  background: #f2f2f2; color: #24292e; padding: 1px 5px; border-radius: 3px;
  word-break: break-all;
}
pre {
  background: #f6f6f6; border: 1px solid #e0e0e0; border-radius: 4px;
  padding: 14px 16px; overflow-x: auto; margin: 12px 0;
}
pre code { background: none; padding: 0; font-size: 15px; line-height: 1.7; word-break: normal; white-space: pre; }
blockquote {
  border-left: 4px solid #d0d3d9; background: #f7f7f8;
  padding: 10px 14px; margin: 12px 0; color: #333;
}
strong { font-weight: 600; }
hr { border: none; border-top: 1px solid #d9dce1; margin: 30px 0; }
"""

TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="page">
{body}
</div>
</body>
</html>
"""

for name in FILES:
    md_path = BASE / name
    text = md_path.read_text(encoding="utf-8")
    m = re.match(r"#\s+(.+)", text)
    title = m.group(1).strip() if m else md_path.stem
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    html = TPL.format(title=title, body=body, css=CSS)
    out = md_path.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print("generated:", out.name)
