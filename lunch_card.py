# -*- coding: utf-8 -*-
"""午餐小抄卡片產生器。
讀 lunch_note.txt 的簡單標記，排成漂亮的分區卡片(整頁 HTML)。
標記格式(每天我幫她填)：
    DATE: 6/24
    LEAD: 大盤一句話…
    # red | ① 真的要動手
    - 汎銓 → 清掉 | 反彈破底失敗…（"|"前是股名/動作，後是說明；沒有"|"就只有股名）
    # orange | ② 太燙…
    - 世界先進 / 長榮航 | 各賣一點…
    SUMMARY: 今天唯一非做不可…
顏色：red 橘 orange 藍 blue 灰 gray（對應動手/賣強/看著/抱著）。
"""
import os

COLORS = {
    "red": "#ff4b5c",     # 鮮明活力珊瑚紅
    "orange": "#ff9300",  # 溫暖明亮橘
    "blue": "#2f6fe0",    # 科技感亮藍
    "gray": "#7f8c8d"     # 沉穩質感灰
}

# 緊湊手帳風排版，採用 em 相對字級，方便 JavaScript 動態放大縮小
CARD_CSS = """
  *{box-sizing:border-box}
  body{
    margin:0;
    background:#f5f6f9;
    color:#2c3e50;
    font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans TC',sans-serif;
    padding:8px 16px 24px;
    font-size:14px; /* 基底字型大小 */
    line-height:1.45
  }
  .lh{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px}
  .lh h1{
    font-size:1.8em;
    margin:0;
    font-weight:900;
    letter-spacing:0.5px;
    background:linear-gradient(135deg, #6c5ce7, #a862ea);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    display:flex;
    align-items:center;
    gap:4px
  }
  .lh h1::before{content:"🍱";font-size:1.1em}
  .lh .date{
    font-size:0.9em;
    color:#64748b;
    font-weight:800;
    background:#e2e8f0;
    padding:2px 8px;
    border-radius:999px
  }
  .zoom-ctrl{
    margin-left:auto;
    display:flex;
    gap:4px
  }
  .zoom-btn{
    border:1px solid #cbd5e1;
    background:#ffffff;
    border-radius:6px;
    padding:2px 8px;
    font-weight:900;
    cursor:pointer;
    font-size:11px;
    display:flex;
    align-items:center;
    justify-content:center;
    box-shadow:0 1px 2px rgba(0,0,0,0.05);
    color:#64748b;
    user-select:none;
    -webkit-user-select:none
  }
  .zoom-btn:active{background:#f1f5f9}
  .lead{
    color:#475569;
    font-size:0.93em;
    margin:4px 0 8px;
    line-height:1.5;
    background:#ffffff;
    padding:8px 10px;
    border-radius:10px;
    border:1px solid #e2e8f0;
    box-shadow:0 2px 6px rgba(0,0,0,0.01)
  }
  .rule{margin-bottom:2px}
  .sec{
    background:#ffffff;
    border-radius:12px;
    padding:10px 12px;
    margin:8px 0;
    border:1px solid #e2e8f0;
    box-shadow:0 3px 10px rgba(0,0,0,0.02)
  }
  .sh{display:flex;align-items:center;gap:6px;font-size:1.15em;font-weight:900;margin-bottom:6px;color:#1e293b}
  .bar{width:4px;height:16px;border-radius:99px;flex:0 0 auto}
  .item{
    margin:4px 0 4px 8px;
    padding-bottom:4px;
    border-bottom:1px dashed #f1f5f9
  }
  .item:last-child{border-bottom:none;padding-bottom:0;margin-bottom:0}
  .nm{font-weight:900;font-size:1.05em;display:flex;align-items:center;gap:4px}
  .dt{color:#475569;font-size:0.93em;margin-top:2px;line-height:1.45;padding-left:2px}
  .sumbox{
    margin-top:12px;
    background:#ecfdf5;
    border:1.5px dashed #34d399;
    border-radius:12px;
    padding:10px 12px;
    box-shadow:0 2px 8px rgba(52,211,153,0.05)
  }
  .sumbox .lbl{
    color:#059669;
    font-size:0.85em;
    font-weight:900;
    margin-bottom:2px;
    text-transform:uppercase;
    letter-spacing:0.5px;
    display:flex;
    align-items:center;
    gap:3px
  }
  .sumbox .lbl::before{content:"💡"}
  .sumbox .txt{font-weight:800;font-size:1.0em;line-height:1.5;color:#065f46}
"""


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def parse(text):
    date = lead = summary = ""
    sections = []
    cur = None
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("DATE:"):
            date = s[5:].strip()
        elif s.startswith("LEAD:"):
            lead = s[5:].strip()
        elif s.startswith("SUMMARY:"):
            summary = s[8:].strip()
        elif s.startswith("#"):
            parts = s[1:].split("|", 1)
            color = COLORS.get(parts[0].strip().lower(), "#8a9099")
            title = parts[1].strip() if len(parts) > 1 else ""
            cur = {"color": color, "title": title, "items": []}
            sections.append(cur)
        elif s.startswith("-") and cur is not None:
            parts = s[1:].split("|", 1)
            names = parts[0].strip()
            detail = parts[1].strip() if len(parts) > 1 else ""
            cur["items"].append({"names": names, "detail": detail})
    return date, lead, sections, summary


def render_card(text):
    date, lead, sections, summary = parse(text)
    date_span = f'<span class="date">{_esc(date)}</span>' if date else ""
    
    # 加入字體大小縮放控制按鈕 (A+ / A-)
    zoom_ctrl = (
        '<div class="zoom-ctrl">'
        '<button class="zoom-btn" onclick="zoom(0.1)">A+</button>'
        '<button class="zoom-btn" onclick="zoom(-0.1)">A-</button>'
        '</div>'
    )
    
    body = f'<div class="lh"><h1>午餐小抄</h1>{date_span}{zoom_ctrl}</div>'
    if lead:
        body += f'<div class="lead">{_esc(lead)}</div>'
    body += '<div class="rule"></div>'
    for sec in sections:
        c = sec["color"]
        body += f'<div class="sec"><div class="sh"><span class="bar" style="background:{c}"></span><span>{_esc(sec["title"])}</span></div>'
        for it in sec["items"]:
            body += f'<div class="item"><div class="nm" style="color:{c}">{_esc(it["names"])}</div>'
            if it["detail"]:
                body += f'<div class="dt">{_esc(it["detail"])}</div>'
            body += '</div>'
        body += '</div>'
    if summary:
        body += f'<div class="sumbox"><div class="lbl">一句話</div><div class="txt">{_esc(summary)}</div></div>'
        
    # 動態變更基底字型大小的 JavaScript 函數
    zoom_js = """
<script>
  var curScale = 1.0;
  window.zoom = function(delta) {
    curScale = Math.max(0.7, Math.min(1.6, curScale + delta));
    document.body.style.fontSize = (curScale * 14) + 'px';
  };
</script>
"""
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-TW\"><head>\n"
        "<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        "<meta name=\"robots\" content=\"noindex, nofollow, noarchive, nosnippet\">\n"
        "<title>午餐小抄</title>\n<style>" + CARD_CSS + "</style></head><body>\n" + body + zoom_js + "\n</body></html>"
    )
