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
import premarket
import institutional_chips
import rotation_radar
import cpo_watch
import cold_blooded_hunter
import panic_bottom_hunter
import second_leg_hunter


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
    # \r(進度列 end='\r') 正規化成 \n，否則多檔黏成一行、切段只認得第一檔
    return buf.getvalue().replace('\r', '\n')


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
  <div class="wrap"><pre id="pre">__BODY__</pre></div>
<script>
  // 由外框頁籤列的下拉呼叫(af→這頁的 filt)。全部/某檔切換顯示。
  function filt(v){
    var ns=document.querySelectorAll('#pre span[data-stk]');
    for(var i=0;i<ns.length;i++){var o=ns[i].getAttribute('data-stk');
      ns[i].style.display=(o==='__hdr__'||v==='__ALL__'||(o===v&&v!=='__NONE__'))?'':'none';}
  }
</script>
</body></html>"""

SHELL_TPL = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 44 44'><circle cx='9' cy='35' r='5' fill='%2358a6ff'/><path d='M9 21 A14 14 0 0 1 23 35' fill='none' stroke='%2358a6ff' stroke-width='4' stroke-linecap='round'/><path d='M9 11 A24 24 0 0 1 33 35' fill='none' stroke='%2358a6ff' stroke-width='4' stroke-linecap='round' opacity='.55'/></svg>">
<title>描訊理財網 Signope</title>
<style>
  html,body{margin:0;height:100%;background:#0d1117;font-family:'Noto Sans TC',sans-serif}
  body{display:flex;flex-direction:column}
  .topbar{flex:0 0 auto;display:flex;align-items:center;gap:12px;background:#0d1117;border-bottom:1px solid #212835;padding:10px 14px}
  .homebtn{color:#58a6ff;font-weight:700;font-size:15px;cursor:pointer;white-space:nowrap}
  .homebtn:hover{text-decoration:underline}
  #curtitle{font-weight:700;font-size:16px;color:#e6edf3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #stk{appearance:none;-webkit-appearance:none;background:transparent;border:none;color:transparent;font-size:0;text-indent:-999px;cursor:pointer;width:26px;height:28px;padding:0;margin-left:-6px;flex:0 0 auto;background-image:url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="13" height="9"><path d="M0 0l6.5 9 6.5-9z" fill="%2358a6ff"/></svg>');background-repeat:no-repeat;background-position:center}
  #stk option{background:#161b22;color:#e6edf3;font-size:14px;text-indent:0;font-weight:400}
  iframe{flex:1 1 auto;width:100%;border:0;background:#0d1117}
</style></head><body>
  <div class="topbar" id="topbar" style="display:none">
    <span class="homebtn" onclick="goHome()">🏠 首頁</span>
    <span id="curtitle"></span>
    <select id="stk" onchange="apply()" title="選一檔只看它" style="display:none"><option value="__NONE__">選股票…</option></select>
  </div>
  <iframe id="fr" src="home.html?v=__VER__" onload="af()"></iframe>
<script>
  var VER="__VER__", mem={}, cur="home.html", FILTER=__FILTER__, TABSTK=__TABSTK__, TNAME=__TNAME__;
  function selVis(){ document.getElementById('stk').style.display=(FILTER.indexOf(cur)>=0)?'':'none'; }
  function flt(v){try{var w=document.getElementById('fr').contentWindow;if(w&&w.filt)w.filt(v);}catch(e){}}
  function fillSel(){
    var stocks=TABSTK[cur]||[], sel=document.getElementById('stk');
    var html='<option value="__NONE__">選股票…</option><option value="__ALL__">全部</option>';
    for(var i=0;i<stocks.length;i++){html+='<option value="'+stocks[i]+'">'+stocks[i]+'</option>';}
    sel.innerHTML=html;
    var want=mem[cur]||'__NONE__', ok=false;   // 預設不選、不顯示結果，選了才出現
    for(var k=0;k<sel.options.length;k++){if(sel.options[k].value===want){ok=true;break;}}
    sel.value=ok?want:'__NONE__';
  }
  function apply(){var v=document.getElementById('stk').value;mem[cur]=v;flt(v);}
  // 加密頁解密後，內頁呼叫這個把它的股單填進下拉(股名只在解密後才出現，不進公開HTML)
  function encReady(stocks){ if(stocks&&stocks.length){ TABSTK[cur]=stocks; fillSel(); } }
  window.encReady=encReady;
  function goHome(){ cur="home.html"; document.getElementById('topbar').style.display='none'; document.getElementById('fr').src="home.html?v="+VER; }
  window.goHome=goHome;
  // 首頁點方塊→進工具(頁籤隱藏，上面只留 🏠首頁 返回 + 該篩的▼)
  function goTab(url){ cur=url; document.getElementById('curtitle').textContent=TNAME[url]||''; document.getElementById('topbar').style.display='flex'; selVis(); document.getElementById('fr').src=url+'?v='+VER; }
  window.goTab=goTab;
  function af(){ if(cur==='home.html'){ document.getElementById('topbar').style.display='none'; return; } selVis(); fillSel(); flt(document.getElementById('stk').value); }
</script>
</body></html>"""

TABS = [
    ("🏠 首頁", "home.html"),
    ("庫存股雷達", "radar.html"),
    ("加碼區", "add_zone.html"),
    ("真鑽石篩選", "diamonds.html"),
    ("轉折燈", "turning.html"),
    ("盤前國際盤", "premarket.html"),
    ("法人籌碼", "chips.html"),
    ("輪動雷達", "rotation.html"),
    ("CPO觀察", "cpo.html"),
    ("冷血獵殺", "cold.html"),
    ("恐慌接刀", "panic.html"),
    ("第二腳", "secondleg.html"),
    ("🍱午餐小抄", "lunch.html"),  # 私人加密頁(含部位，密文)
    ("🛡️守線", "support.html"),   # 私人加密頁(防守線+策略，密文)
    ("🔒關卡", "levels.html"),     # 私人加密頁(成本/持股，密文)
]

# 文字型工具：(頁面標題, 輸出檔, 要跑的函式)。加新工具在這裡加一行即可。
TEXT_TOOLS = [
    ("💎 真鑽石篩選", "diamonds.html", lambda: diamond_scanner.run()),
    ("🚦 轉折燈", "turning.html", lambda: turning_point.main()),
    ("🌏 盤前國際盤", "premarket.html", lambda: premarket.run()),
    ("💰 法人籌碼", "chips.html", lambda: institutional_chips.run()),
    ("📡 庫存輪動雷達", "rotation.html", lambda: rotation_radar.run()),
    ("🔭 CPO矽光子觀察", "cpo.html", lambda: cpo_watch.run()),
    ("⚔️ 冷血獵殺", "cold.html", lambda: cold_blooded_hunter.run_full_scan()),
    ("🌋 恐慌接刀", "panic.html", lambda: panic_bottom_hunter.run_panic_scan()),
    ("🐺 第二腳獵殺", "secondleg.html", lambda: second_leg_hunter.run_hunter()),
]

# 首頁九宮格：(檔案, emoji, 顯示名, 短說明, 主色)
HOME_GROUPS = [
    ("📊 每日盯盤", "#1f6feb", [
        ("radar.html", "📡", "庫存股雷達", "強弱＋體質"),
        ("premarket.html", "🌏", "盤前國際盤", "開盤偏多空"),
        ("chips.html", "💰", "法人籌碼", "外資投信"),
        ("rotation.html", "🔄", "輪動雷達", "類股輪動"),
        ("cpo.html", "🔭", "CPO觀察", "矽光子股"),
    ]),
    ("⚔️ 獵殺掃描", "#8957e5", [
        ("diamonds.html", "💎", "真鑽石篩選", "分真假"),
        ("turning.html", "🚦", "轉折燈", "上車下車"),
        ("cold.html", "⚔️", "冷血獵殺", "抄超賣"),
        ("panic.html", "🌋", "恐慌接刀", "崩盤接"),
        ("secondleg.html", "🐺", "第二腳", "回測接點"),
    ]),
    ("🔒 寶挖挖", "#2ea043", [
        ("lunch.html", "🍱", "午餐小抄", "盤中看這張"),
        ("add_zone.html", "📈", "加碼區", "拉回加碼點"),
        ("support.html", "🛡️", "守線小幫手", "防守線"),
        ("levels.html", "🎯", "關卡小工具", "成本關卡"),
    ]),
]

HOME_TPL = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 44 44'><circle cx='9' cy='35' r='5' fill='%2358a6ff'/><path d='M9 21 A14 14 0 0 1 23 35' fill='none' stroke='%2358a6ff' stroke-width='4' stroke-linecap='round'/><path d='M9 11 A24 24 0 0 1 33 35' fill='none' stroke='%2358a6ff' stroke-width='4' stroke-linecap='round' opacity='.55'/></svg>">
<title>描訊理財網 Signope</title>
<style>
  body{margin:0;background:#0d1117;color:#e6edf3;font-family:'Noto Sans TC',sans-serif;padding:14px 12px 40px}
  .brand{display:flex;align-items:center;gap:11px;margin:4px 0 3px}
  .logo{width:44px;height:44px;flex:0 0 auto}
  .cn{font-size:21px;font-weight:800;line-height:1.1;color:#e6edf3}
  .en{font-size:11px;color:#58a6ff;letter-spacing:4px;font-weight:700;margin-top:3px;text-transform:uppercase}
  .upd{color:#8b949e;font-size:11.5px;margin-bottom:16px}
  .gtitle{font-size:13px;font-weight:700;margin:12px 0 6px;padding-left:2px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(78px,1fr));gap:5px}
  .tile{background:transparent;border:1px solid rgba(255,255,255,.16);border-radius:4px;padding:4px 2px;text-align:center;cursor:pointer;transition:border-color .12s,background .12s}
  .tile:hover,.tile:active{border-color:rgba(255,255,255,.4);background:rgba(255,255,255,.04)}
  .emoji{font-size:15px;line-height:1}
  .tname{font-size:11px;font-weight:700;margin-top:2px}
  .tdesc{font-size:8.5px;color:#8b949e;margin-top:0;line-height:1.3}
</style></head><body>
  <div class="brand">
    <svg class="logo" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
      <circle cx="9" cy="35" r="3.6" fill="#58a6ff"/>
      <path d="M9 23 A12 12 0 0 1 21 35" fill="none" stroke="#58a6ff" stroke-width="3.2" stroke-linecap="round" opacity=".85"/>
      <path d="M9 15 A20 20 0 0 1 29 35" fill="none" stroke="#58a6ff" stroke-width="3.2" stroke-linecap="round" opacity=".55"/>
      <path d="M9 7 A28 28 0 0 1 37 35" fill="none" stroke="#58a6ff" stroke-width="3.2" stroke-linecap="round" opacity=".3"/>
    </svg>
    <div>
      <div class="cn">描訊理財網</div>
      <div class="en">Signope</div>
    </div>
  </div>
  <div class="upd">更新 __UPD__ · 點方塊進入工具，工具頁左上角「🏠首頁」可回來</div>
  __CARDS__
</body></html>"""


def home_page(upd):
    blocks = ""
    for gtitle, color, items in HOME_GROUPS:
        tiles = ""
        for url, emo, nm, desc in items:
            tiles += (f'<div class="tile" style="--c:{color}" onclick="parent.goTab(\'{url}\')">'
                      f'<div class="emoji">{emo}</div><div class="tname">{esc(nm)}</div>'
                      f'<div class="tdesc">{esc(desc)}</div></div>')
        blocks += (f'<div class="gtitle" style="color:{color}">{esc(gtitle)}</div>'
                   f'<div class="grid">{tiles}</div>')
    return lock_inject(HOME_TPL.replace("__UPD__", upd).replace("__CARDS__", blocks))


def load_names():
    import json
    try:
        data = json.load(open(os.path.join(HERE, "watch_list.json"), encoding="utf-8"))
        return [it["name"] for it in data if it.get("name")]
    except Exception:
        return []


def segment_html(text, names):
    """把報表文字依股名切成區塊，每塊包成 <span data-stk=股名>，下拉可只顯示某一檔。
    沒股名的開頭/標題行歸 __hdr__(永遠顯示)；接在某股名後面的說明行歸該股。"""
    lines = text.split("\n")
    segs = []            # (owner, [lines])
    owner, cur = "__hdr__", []
    for ln in lines:
        found = next((nm for nm in names if nm and nm in ln), None)
        if found:
            if cur:
                segs.append((owner, cur))
            owner, cur = found, [ln]
        else:
            cur.append(ln)
    if cur:
        segs.append((owner, cur))
    parts = []
    for own, ls in segs:
        chunk = "\n".join(ls) + "\n"
        parts.append('<span data-stk="%s">%s</span>' % (esc(own), esc(chunk)))
    return "".join(parts)


def text_page(title, body_text, upd, names):
    body = segment_html(body_text, names)   # 切段標股名，供外框下拉篩選
    html = (PAGE_TPL.replace("__TITLE__", title)
                    .replace("__UPD__", upd)
                    .replace("__BODY__", body))
    return lock_inject(html)


def shell():
    ver = datetime.now(TW).strftime('%Y%m%d%H%M')  # 版本記號=防快取，每次更新換一個號
    import json
    # 只有這些頁籤才顯示下拉(有個股可篩)。盤前=國際盤沒個股→不顯示
    watch_tabs = ["radar.html", "diamonds.html", "turning.html", "chips.html", "rotation.html",
                  "cold.html", "panic.html", "secondleg.html"]
    enc_tabs = ["lunch.html", "add_zone.html", "support.html", "levels.html"]   # 加密頁：解密後才由 encReady 填股單
    filterable = json.dumps(watch_tabs + ["cpo.html"] + enc_tabs)
    # 各頁籤的「固定股單」：觀察24檔 / CPO那幾檔。下拉選項用這個，才會完整(不靠內容硬抓)
    watch = load_names()
    try:
        cpo = [nm for (_c, nm, _r) in cpo_watch.WATCH]
    except Exception:
        cpo = []
    tabstk = {u: watch for u in watch_tabs}
    tabstk["cpo.html"] = cpo
    for u in enc_tabs:
        tabstk[u] = []   # 空的，等解密後前端補
    tname = {url: name for (name, url) in TABS if url != "home.html"}   # 工具頁上方顯示的標題
    return (SHELL_TPL.replace("__VER__", ver)
                     .replace("__FILTER__", filterable)
                     .replace("__TABSTK__", json.dumps(tabstk, ensure_ascii=False))
                     .replace("__TNAME__", json.dumps(tname, ensure_ascii=False)))


def main():
    upd = now_str()
    names = load_names()
    # CPO 的股(華星光/上詮/日月光投控…)不在觀察名單裡，補進來才切得出段、下拉才列得對
    try:
        names = names + [nm for (_c, nm, _r) in cpo_watch.WATCH if nm not in names]
    except Exception:
        pass
    import time
    for title, fname, fn in TEXT_TOOLS:
        print(f"產生 {title} 頁…")
        txt = capture(fn)
        tries = 0
        # 間歇性抓失敗(如法人籌碼的TWSE)就自動重試，避免卡成錯誤頁
        while ("產生時出錯" in txt or len(txt.strip()) < 30) and tries < 3:
            time.sleep(4)
            txt = capture(fn)
            tries += 1
        with open(os.path.join(HERE, fname), "w", encoding="utf-8") as f:
            f.write(text_page(title, txt, upd, names))
    with open(os.path.join(HERE, "home.html"), "w", encoding="utf-8") as f:
        f.write(home_page(upd))
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(shell())
    print("已產生所有工具頁 + home.html + index.html(頁籤外框)")


if __name__ == "__main__":
    main()
