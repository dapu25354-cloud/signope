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
<title>看盤總表</title>
<style>
  html,body{margin:0;height:100%;background:#0d1117;font-family:'Noto Sans TC',sans-serif}
  body{display:flex;flex-direction:column}
  .topbar{flex:0 0 auto;background:#0d1117;border-bottom:1px solid #212835;padding:8px 8px 0}
  .tabbar{display:flex;gap:6px;overflow-x:auto;-webkit-overflow-scrolling:touch}
  .tab{flex:0 0 auto;padding:10px 16px;font-size:15px;font-weight:700;color:#8b949e;background:#161b22;border:1px solid #212835;border-bottom:none;border-radius:10px 10px 0 0;cursor:pointer;white-space:nowrap}
  .tab:hover{text-decoration:underline;color:#e6edf3}
  .tab.active{color:#fff;background:#1f6feb;border-color:#1f6feb}
  .stkrow{display:flex;align-items:center;gap:8px;padding:8px 2px 6px}
  .stkrow label{color:#8b949e;font-size:13px;white-space:nowrap}
  #stk{appearance:none;-webkit-appearance:none;background:transparent;border:none;color:transparent;font-size:0;text-indent:-999px;cursor:pointer;width:28px;height:30px;padding:0;align-self:center;margin-left:2px;flex:0 0 auto;background-image:url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="13" height="9"><path d="M0 0l6.5 9 6.5-9z" fill="%2358a6ff"/></svg>');background-repeat:no-repeat;background-position:center}
  #stk option{background:#161b22;color:#e6edf3;font-size:14px;text-indent:0;font-weight:400}
  iframe{flex:1 1 auto;width:100%;border:0;background:#0d1117}
</style></head><body>
  <div class="topbar">
    <div class="tabbar" id="tabbar">__TABS__<select id="stk" onchange="apply()" title="選一檔只看它" style="display:none"><option value="__NONE__">選股票…</option></select></div>
  </div>
  <iframe id="fr" src="home.html?v=__VER__" onload="af()"></iframe>
<script>
  var VER="__VER__", mem={}, cur="home.html", FILTER=__FILTER__, TABSTK=__TABSTK__;   // TABSTK:各頁籤固定股單
  // 把下拉▼移到「當前頁籤」右邊；非篩選頁(盤前等)則隱藏
  function place(){
    var sel=document.getElementById('stk'), act=document.querySelector('.tab.active');
    if(act && FILTER.indexOf(cur)>=0){ act.parentNode.insertBefore(sel, act.nextSibling); sel.style.display=''; }
    else { sel.style.display='none'; }
  }
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
  // 首頁點工具→切到那個頁籤
  function goTab(url){var t=document.querySelectorAll('.tab');for(var i=0;i<t.length;i++){var oc=t[i].getAttribute('onclick');if(oc&&oc.indexOf("'"+url+"'")>=0){show(t[i],url);return;}}}
  window.goTab=goTab;
  function show(btn,url){var t=document.querySelectorAll('.tab');for(var i=0;i<t.length;i++)t[i].classList.remove('active');btn.classList.add('active');cur=url;place();document.getElementById('fr').src=url+'?v='+VER;}
  function af(){place();fillSel();flt(document.getElementById('stk').value);}
  place();
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

# 首頁的工具選單(分組)：(檔案, 顯示名, 一句說明)
HOME_GROUPS = [
    ("📊 每日盯盤", [
        ("radar.html", "庫存股雷達", "每檔短線強弱＋體質(真鑽石/石頭)"),
        ("add_zone.html", "🔒 加碼區", "拉回到哪可以加碼(私人，需密碼)"),
        ("premarket.html", "盤前國際盤", "昨夜美股/油價 → 台股開盤偏多或偏空"),
        ("chips.html", "法人籌碼", "外資/投信買賣超"),
        ("rotation.html", "輪動雷達", "類股分組強弱、看資金輪動"),
        ("cpo.html", "CPO觀察", "矽光子觀察股(華星光/上詮/日月光)"),
    ]),
    ("⚔️ 獵殺掃描", [
        ("diamonds.html", "真鑽石篩選", "分真鑽石／鍍金／石頭，別買錯"),
        ("turning.html", "轉折燈", "五關轉折：該上車還是下車"),
        ("cold.html", "冷血獵殺", "抄超賣的強勢股"),
        ("panic.html", "恐慌接刀", "崩盤時接被錯殺的好股"),
        ("secondleg.html", "第二腳", "回測前低、站得住的接點"),
    ]),
    ("🔒 私人(需密碼 yushu178861)", [
        ("support.html", "守線小幫手", "各檔防守線＋策略"),
        ("levels.html", "關卡小工具", "你的成本＋操作關卡"),
    ]),
]

HOME_TPL = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">
<title>看盤總表 首頁</title>
<style>
  body{margin:0;background:#0d1117;color:#e6edf3;font-family:'Noto Sans TC',sans-serif;padding:16px 14px 40px}
  h1{font-size:24px;margin:4px 0 2px}
  .upd{color:#8b949e;font-size:12px;margin-bottom:18px;line-height:1.6}
  .hgroup{margin-bottom:20px}
  .gtitle{font-size:15px;font-weight:700;color:#58a6ff;margin:0 0 8px;padding-left:2px}
  .hitem{display:block;background:#161b22;border:1px solid #212835;border-radius:12px;padding:13px 15px;margin-bottom:9px;cursor:pointer;transition:.12s}
  .hitem:hover{border-color:#1f6feb;background:#1a2333}
  .hname{font-size:16px;font-weight:700}
  .hdesc{font-size:12.5px;color:#8b949e;margin-top:3px;line-height:1.5}
</style></head><body>
  <h1>📊 看盤總表</h1>
  <div class="upd">更新：__UPD__（台灣時間）<br>點下面工具進入，或用最上面那排頁籤切換</div>
  __CARDS__
</body></html>"""


def home_page(upd):
    cards = ""
    for gtitle, items in HOME_GROUPS:
        rows = ""
        for url, nm, desc in items:
            rows += (f'<div class="hitem" onclick="parent.goTab(\'{url}\')">'
                     f'<div class="hname">{esc(nm)}</div><div class="hdesc">{esc(desc)}</div></div>')
        cards += f'<div class="hgroup"><div class="gtitle">{esc(gtitle)}</div>{rows}</div>'
    return lock_inject(HOME_TPL.replace("__UPD__", upd).replace("__CARDS__", cards))


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
    btns = ""
    for i, (name, url) in enumerate(TABS):
        cls = "tab active" if i == 0 else "tab"
        btns += f'<button class="{cls}" onclick="show(this,\'{url}\')">{name}</button>'
    ver = datetime.now(TW).strftime('%Y%m%d%H%M')  # 版本記號=防快取，每次更新換一個號
    import json
    # 只有這些頁籤才顯示下拉(有個股可篩)。盤前=國際盤沒個股→不顯示
    watch_tabs = ["radar.html", "diamonds.html", "turning.html", "chips.html", "rotation.html",
                  "cold.html", "panic.html", "secondleg.html"]
    enc_tabs = ["add_zone.html", "support.html", "levels.html"]   # 加密頁：解密後才由 encReady 填股單
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
    return (SHELL_TPL.replace("__TABS__", btns)
                     .replace("__VER__", ver)
                     .replace("__FILTER__", filterable)
                     .replace("__TABSTK__", json.dumps(tabstk, ensure_ascii=False)))


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
