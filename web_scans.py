# -*- coding: utf-8 -*-
"""
把 CLI 工具(真鑽石篩選 / 轉折燈)的文字輸出包成網頁，並產生「頁籤外框」index.html，
把 庫存股雷達 / 加碼區 / 真鑽石篩選 / 轉折燈 用頁籤整合成一頁(一個網址、原地切換不跳頁)。

架構：
- radar.html      ← holdings_radar.py 產生
- add_zone.html   ← add_zone.py 產生
- diamonds.html   ← 本檔(真鑽石篩選輸出)
- turning.html    ← 本檔(轉折燈輸出)
- index.html      ← 本檔(頁籤外框，預設載入 radar.html，其餘頁籤切換 iframe)
密碼鎖放在各內頁；外框沒鎖，第一次載入時內頁(雷達)會跳鎖，輸一次同源全部解鎖。
"""
import io
import os
import sys
import contextlib
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TW = timezone(timedelta(hours=8))

from page_lock import inject as lock_inject
import diamond_scanner
import turning_point


def now_str():
    return datetime.now(TW).strftime('%Y-%m-%d %H:%M')


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def capture(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            fn()
        except Exception as e:
            print(f"(這頁產生時出錯：{e})")
    return buf.getvalue()


PAGE_TPL = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">
<title>__TITLE__</title>
<style>
  body{margin:0;background:#0d1117;color:#e6edf3;font-family:'Noto Sans TC',sans-serif}
  .hd{padding:14px 16px 4px;font-size:18px;font-weight:700}
  .upd{padding:0 16px 10px;color:#8b949e;font-size:12px}
  .wrap{padding:0 10px 40px;overflow-x:auto}
  pre{font-family:Consolas,'Courier New',monospace;font-size:13px;line-height:1.55;white-space:pre;margin:0;color:#dbe1e8}
</style></head><body>
  <div class="hd">__TITLE__</div>
  <div class="upd">最後更新：__UPD__（台灣時間）</div>
  <div class="wrap"><pre>__BODY__</pre></div>
</body></html>"""

SHELL_TPL = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">
<title>看盤總表</title>
<style>
  html,body{margin:0;height:100%;background:#0d1117;font-family:'Noto Sans TC',sans-serif}
  .tabbar{display:flex;gap:6px;padding:8px 8px 0;overflow-x:auto;-webkit-overflow-scrolling:touch;border-bottom:1px solid #212835}
  .tab{flex:0 0 auto;padding:10px 16px;font-size:15px;font-weight:700;color:#8b949e;background:#161b22;border:1px solid #212835;border-bottom:none;border-radius:10px 10px 0 0;cursor:pointer;white-space:nowrap}
  .tab.active{color:#fff;background:#1f6feb;border-color:#1f6feb}
  iframe{border:0;width:100%;height:calc(100vh - 53px);display:block;background:#0d1117}
</style></head><body>
  <div class="tabbar">__TABS__</div>
  <iframe id="fr" src="radar.html"></iframe>
<script>
  function show(btn,url){document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('active');});btn.classList.add('active');document.getElementById('fr').src=url;}
</script>
</body></html>"""

TABS = [
    ("庫存股雷達", "radar.html"),
    ("加碼區", "add_zone.html"),
    ("真鑽石篩選", "diamonds.html"),
    ("轉折燈", "turning.html"),
]


def text_page(title, body_text, upd):
    html = (PAGE_TPL.replace("__TITLE__", title)
                    .replace("__UPD__", upd)
                    .replace("__BODY__", esc(body_text)))
    return lock_inject(html)


def shell():
    btns = ""
    for i, (name, url) in enumerate(TABS):
        cls = "tab active" if i == 0 else "tab"
        btns += f'<button class="{cls}" onclick="show(this,\'{url}\')">{name}</button>'
    return SHELL_TPL.replace("__TABS__", btns)


def main():
    upd = now_str()
    print("產生 真鑽石篩選 頁…")
    diamonds_txt = capture(diamond_scanner.run)
    print("產生 轉折燈 頁…")
    turning_txt = capture(turning_point.main)

    with open(os.path.join(HERE, "diamonds.html"), "w", encoding="utf-8") as f:
        f.write(text_page("💎 真鑽石篩選", diamonds_txt, upd))
    with open(os.path.join(HERE, "turning.html"), "w", encoding="utf-8") as f:
        f.write(text_page("🚦 轉折燈", turning_txt, upd))
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(shell())
    print("已產生 diamonds.html / turning.html / index.html(頁籤外框)")


if __name__ == "__main__":
    main()
