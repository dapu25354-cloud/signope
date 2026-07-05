# -*- coding: utf-8 -*-
"""
私人加密網頁產生器 —— 只在本機跑(會讀含成本/防守策略的 xxx_levels.py / support_level.py)。
把「關卡小工具」「守線小幫手」的輸出，用密碼(環境變數 LEVELS_PW)加密成亂碼寫進 HTML。
上傳公開倉庫的只有亂碼；原始檔與密碼都不上傳。手機端輸入同一組密碼在瀏覽器解密還原。

用法(本機)：  LEVELS_PW=你的密碼  python build_levels_page.py
※ 絕不要把 xxx_levels.py / support_level.py / 密碼 提交到公開倉庫(已用 .gitignore 擋)。
"""
import io
import os
import sys
import base64
import contextlib

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ITER = 200000

import levels_watch
import support_level
import add_zone


def _lunch_note():
    # 午餐小抄：每天 Claude 幫她寫、存進本機 lunch_note.txt(含部位，gitignore 不上傳)。
    p = os.path.join(HERE, "lunch_note.txt")
    if os.path.exists(p):
        print(open(p, encoding="utf-8").read())
    else:
        print("（今天的午餐小抄還沒更新）")


# (顯示名, 輸出檔, 要跑的函式)。這些都是私人內容、都會加密。
PAGES = [
    ("午餐小抄", "lunch.html", _lunch_note),
    ("關卡小工具", "levels.html", lambda: levels_watch.run()),
    ("守線小幫手", "support.html", lambda: support_level.main()),
]


def _b64(b):
    return base64.b64encode(b).decode()


def encrypt(plaintext, password):
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(password.encode())
    ct = AESGCM(key).encrypt(iv, plaintext.encode('utf-8'), None)  # ct = ciphertext || 16-byte tag
    return _b64(salt), _b64(iv), _b64(ct)


HTML = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">
<title>__NAME__（加密）</title>
<style>
  body{margin:0;background:#0d1117;color:#e6edf3;font-family:'Noto Sans TC',sans-serif}
  #gate{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px}
  #gate .t{font-size:18px;margin-bottom:6px;text-align:center}
  #gate .s{font-size:12px;color:#8b949e;margin-bottom:14px;text-align:center}
  .box{position:relative;width:240px}
  #pw{padding:12px 44px 12px 16px;font-size:16px;border-radius:10px;border:1px solid #30363d;background:#161b22;color:#e6edf3;width:100%;box-sizing:border-box;text-align:center;outline:none}
  #eye{position:absolute;right:12px;top:50%;transform:translateY(-50%);cursor:pointer;font-size:19px;user-select:none}
  #go{margin-top:14px;padding:11px 28px;font-size:15px;border:0;border-radius:10px;background:#8957e5;color:#fff;font-weight:700;cursor:pointer}
  #err{color:#f85149;font-size:13px;margin-top:12px;height:16px}
  .hd{padding:14px 16px 4px;font-size:18px;font-weight:700}
  .wrap{padding:0 10px 40px;overflow-x:auto}
  pre{font-family:Consolas,'Courier New',monospace;font-size:13px;line-height:1.55;white-space:pre;margin:0;color:#dbe1e8}
</style></head><body>
<div id="gate">
  <div class="t">&#128274; __NAME__（私人加密）</div>
  <div class="s">輸入專屬密碼才會解開私人內容</div>
  <div class="box">
    <input id="pw" type="password" placeholder="專屬密碼" autocomplete="off">
    <span id="eye" title="顯示/隱藏">&#128065;</span>
  </div>
  <button id="go">解開</button>
  <div id="err"></div>
</div>
<div id="content" style="display:none">
  <div class="hd">__NAME__</div>
  <div class="wrap"><pre id="txt"></pre></div>
</div>
<script>
  var SALT="__SALT__", IV="__IV__", CT="__CT__", ITER=__ITER__, NAMES=__NAMES__;
  function b64d(s){var bin=atob(s);var a=new Uint8Array(bin.length);for(var i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i);return a;}
  function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  window.filt=function(v){var ns=document.querySelectorAll('#txt span[data-stk]');for(var i=0;i<ns.length;i++){var o=ns[i].getAttribute('data-stk');ns[i].style.display=(o==='__hdr__'||v==='__ALL__'||(o===v&&v!=='__NONE__'))?'':'none';}};
  async function decrypt(){
    var pw=document.getElementById('pw').value;
    try{
      var km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pw),'PBKDF2',false,['deriveKey']);
      var key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:b64d(SALT),iterations:ITER,hash:'SHA-256'},km,{name:'AES-GCM',length:256},false,['decrypt']);
      var pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:b64d(IV)},key,b64d(CT));
      var plain=new TextDecoder().decode(pt).replace(/\\r/g,'\\n');
      // 依股名把內容切成 span，供下拉篩選
      var lines=plain.split('\\n'), out=[], owner='__hdr__', cur=[];
      function flush(){ if(cur.length){ out.push('<span data-stk="'+owner+'">'+esc(cur.join('\\n')+'\\n')+'</span>'); } }
      for(var i=0;i<lines.length;i++){ var ln=lines[i], f=null; for(var k=0;k<NAMES.length;k++){ if(ln.indexOf(NAMES[k])>=0){f=NAMES[k];break;} } if(f){ flush(); cur=[ln]; owner=f; } else { cur.push(ln); } }
      flush();
      document.getElementById('txt').innerHTML=out.join('');
      var present=[]; for(var k=0;k<NAMES.length;k++){ if(plain.indexOf(NAMES[k])>=0) present.push(NAMES[k]); }
      try{ window.parent.encReady(present); }catch(e){}
      document.getElementById('gate').style.display='none';
      document.getElementById('content').style.display='block';
    }catch(e){ document.getElementById('err').textContent='密碼錯誤或解密失敗，再試一次'; }
  }
  document.getElementById('go').onclick=decrypt;
  document.getElementById('pw').addEventListener('keydown',function(e){if(e.key==='Enter')decrypt();});
  var inp=document.getElementById('pw'),eye=document.getElementById('eye');
  eye.onclick=function(){ if(inp.type==='password'){inp.type='text';eye.innerHTML='&#128584;';}else{inp.type='password';eye.innerHTML='&#128065;';} inp.focus(); };
</script>
</body></html>"""


def _watch_names():
    import json
    try:
        d = json.load(open(os.path.join(HERE, "watch_list.json"), encoding="utf-8"))
        return [it["name"] for it in d if it.get("name")]
    except Exception:
        return []


def build_page(name, run_fn, outfile, pw):
    import json
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            run_fn()
        except Exception as e:
            print(f"(產生時出錯：{e})")
    text = buf.getvalue().replace('\r', '\n')   # 進度列 \r 正規化，切段才切得對
    salt, iv, ct = encrypt(text, pw)
    html = (HTML.replace("__NAME__", name).replace("__SALT__", salt)
                .replace("__IV__", iv).replace("__CT__", ct).replace("__ITER__", str(ITER))
                .replace("__NAMES__", json.dumps(_watch_names(), ensure_ascii=False)))
    with open(os.path.join(HERE, outfile), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已產生加密 {outfile}（{name}，原文 {len(text)} 字）")


# 加碼區是整頁 HTML(含成本/持股)，用 document.write 版解密還原
HTML_DOC = """<!DOCTYPE html>
<html lang="zh-TW"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">
<title>__NAME__（加密）</title>
<style>
  body{margin:0;background:#0d1117;color:#e6edf3;font-family:'Noto Sans TC',sans-serif}
  #gate{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px}
  #gate .t{font-size:18px;margin-bottom:6px;text-align:center}
  #gate .s{font-size:12px;color:#8b949e;margin-bottom:14px;text-align:center}
  .box{position:relative;width:240px}
  #pw{padding:12px 44px 12px 16px;font-size:16px;border-radius:10px;border:1px solid #30363d;background:#161b22;color:#e6edf3;width:100%;box-sizing:border-box;text-align:center;outline:none}
  #eye{position:absolute;right:12px;top:50%;transform:translateY(-50%);cursor:pointer;font-size:19px;user-select:none}
  #go{margin-top:14px;padding:11px 28px;font-size:15px;border:0;border-radius:10px;background:#8957e5;color:#fff;font-weight:700;cursor:pointer}
  #err{color:#f85149;font-size:13px;margin-top:12px;height:16px}
</style></head><body>
<div id="gate">
  <div class="t">&#128274; __NAME__（私人加密）</div>
  <div class="s">輸入專屬密碼才會解開私人內容</div>
  <div class="box">
    <input id="pw" type="password" placeholder="專屬密碼" autocomplete="off">
    <span id="eye" title="顯示/隱藏">&#128065;</span>
  </div>
  <button id="go">解開</button>
  <div id="err"></div>
</div>
<script>
  var SALT="__SALT__", IV="__IV__", CT="__CT__", ITER=__ITER__;
  function b64d(s){var bin=atob(s);var a=new Uint8Array(bin.length);for(var i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i);return a;}
  async function decrypt(){
    var pw=document.getElementById('pw').value;
    try{
      var km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pw),'PBKDF2',false,['deriveKey']);
      var key=await crypto.subtle.deriveKey({name:'PBKDF2',salt:b64d(SALT),iterations:ITER,hash:'SHA-256'},km,{name:'AES-GCM',length:256},false,['decrypt']);
      var pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:b64d(IV)},key,b64d(CT));
      var full=new TextDecoder().decode(pt);
      document.open();document.write(full);document.close();
    }catch(e){ document.getElementById('err').textContent='密碼錯誤或解密失敗，再試一次'; }
  }
  document.getElementById('go').onclick=decrypt;
  document.getElementById('pw').addEventListener('keydown',function(e){if(e.key==='Enter')decrypt();});
  var inp=document.getElementById('pw'),eye=document.getElementById('eye');
  eye.onclick=function(){ if(inp.type==='password'){inp.type='text';eye.innerHTML='&#128584;';}else{inp.type='password';eye.innerHTML='&#128065;';} inp.focus(); };
</script>
</body></html>"""


def build_htmlpage(name, outfile, gen_fn, pw):
    """加密『整頁 HTML』(如加碼區含成本)。gen_fn 會先產出明碼 outfile，讀進來加密後覆蓋。"""
    gen_fn()
    path = os.path.join(HERE, outfile)
    plain = open(path, encoding='utf-8').read()
    salt, iv, ct = encrypt(plain, pw)
    html = (HTML_DOC.replace("__NAME__", name).replace("__SALT__", salt)
                .replace("__IV__", iv).replace("__CT__", ct).replace("__ITER__", str(ITER)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已產生加密 {outfile}（{name}，整頁HTML {len(plain)} 字）")


def main():
    pw = os.environ.get('LEVELS_PW')
    if not pw:
        print("未設定 LEVELS_PW，跳過。用法: LEVELS_PW=密碼 python build_levels_page.py")
        return
    for name, outfile, fn in PAGES:
        build_page(name, fn, outfile, pw)
    build_htmlpage("加碼區", "add_zone.html", lambda: add_zone.main(), pw)


if __name__ == "__main__":
    main()
