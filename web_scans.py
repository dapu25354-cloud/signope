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
  <iframe id="fr" src="radar.html?v=__VER__" onload="af()"></iframe>
<script>
  var VER="__VER__", mem={}, cur="radar.html", FILTER=__FILTER__;   // mem:每頁記住選的股; FILTER:哪些頁籤才有下拉
  // 把下拉▼移到「當前頁籤」右邊；非篩選頁(盤前等)則隱藏
  function place(){
    var sel=document.getElementById('stk'), act=document.querySelector('.tab.active');
    if(act && FILTER.indexOf(cur)>=0){ act.parentNode.insertBefore(sel, act.nextSibling); sel.style.display=''; }
    else { sel.style.display='none'; }
  }
  function flt(v){try{var w=document.getElementById('fr').contentWindow;if(w&&w.filt)w.filt(v);}catch(e){}}
  // 抓「當前頁」實際有的股票(文字頁看 data-stk、雷達卡片看 data-name)
  function tabStocks(){
    var set={}, out=[];
    try{
      var doc=document.getElementById('fr').contentWindow.document;
      var els=doc.querySelectorAll('[data-stk]');
      for(var i=0;i<els.length;i++){var s=els[i].getAttribute('data-stk');if(s&&s!=='__hdr__'&&!set[s]){set[s]=1;out.push(s);}}
      if(out.length===0){var cs=doc.querySelectorAll('[data-name]');for(var j=0;j<cs.length;j++){var n=cs[j].getAttribute('data-name');if(n&&!set[n]){set[n]=1;out.push(n);}}}
    }catch(e){}
    return out;
  }
  function fillSel(){
    var stocks=tabStocks(), sel=document.getElementById('stk');
    var html='<option value="__NONE__">選股票…</option><option value="__ALL__">全部</option>';
    for(var i=0;i<stocks.length;i++){html+='<option value="'+stocks[i]+'">'+stocks[i]+'</option>';}
    sel.innerHTML=html;
    var want=mem[cur]||'__NONE__', ok=false;   // 預設不選、不顯示結果，選了才出現
    for(var k=0;k<sel.options.length;k++){if(sel.options[k].value===want){ok=true;break;}}
    sel.value=ok?want:'__NONE__';
  }
  function apply(){var v=document.getElementById('stk').value;mem[cur]=v;flt(v);}
  function show(btn,url){var t=document.querySelectorAll('.tab');for(var i=0;i<t.length;i++)t[i].classList.remove('active');btn.classList.add('active');cur=url;place();document.getElementById('fr').src=url+'?v='+VER;}
  function af(){place();fillSel();flt(document.getElementById('stk').value);}
  place();
</script>
</body></html>"""

TABS = [
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
    # 只有這些頁籤才顯示下拉(有個股可篩)。盤前=國際盤沒個股→不顯示。下拉選項在前端依當前頁自動抓
    filterable = json.dumps(["radar.html", "diamonds.html", "turning.html", "chips.html", "rotation.html",
                             "cpo.html", "cold.html", "panic.html", "secondleg.html"])
    return (SHELL_TPL.replace("__TABS__", btns)
                     .replace("__VER__", ver)
                     .replace("__FILTER__", filterable))


def main():
    upd = now_str()
    names = load_names()
    # CPO 的股(華星光/上詮/日月光投控…)不在觀察名單裡，補進來才切得出段、下拉才列得對
    try:
        names = names + [nm for (_c, nm, _r) in cpo_watch.WATCH if nm not in names]
    except Exception:
        pass
    for title, fname, fn in TEXT_TOOLS:
        print(f"產生 {title} 頁…")
        txt = capture(fn)
        with open(os.path.join(HERE, fname), "w", encoding="utf-8") as f:
            f.write(text_page(title, txt, upd, names))
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(shell())
    print("已產生所有工具頁 + index.html(頁籤外框)")


if __name__ == "__main__":
    main()
