# -*- coding: utf-8 -*-
"""
關卡小工具「加密網頁」產生器 —— 只在本機跑(它會讀含成本的 xxx_levels.py)。
把關卡輸出用密碼(環境變數 LEVELS_PW)加密成亂碼，寫進 levels.html。
上傳公開倉庫的只有亂碼；原始成本檔與密碼都不上傳。手機端輸入同一組密碼，
在瀏覽器裡當場 PBKDF2+AES-GCM 解密還原。

用法(本機)：  LEVELS_PW=你的密碼  python build_levels_page.py
※ 絕不要把 xxx_levels.py / 密碼 提交到公開倉庫。
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
<title>關卡小工具（加密）</title>
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
  <div class="t">&#128274; 關卡小工具（私人加密）</div>
  <div class="s">輸入專屬密碼才會解開你的成本與關卡</div>
  <div class="box">
    <input id="pw" type="password" placeholder="專屬密碼" autocomplete="off">
    <span id="eye" title="顯示/隱藏">&#128065;</span>
  </div>
  <button id="go">解開</button>
  <div id="err"></div>
</div>
<div id="content" style="display:none">
  <div class="hd">&#127919; 關卡小工具</div>
  <div class="wrap"><pre id="txt"></pre></div>
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
      document.getElementById('txt').textContent=new TextDecoder().decode(pt);
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


def main():
    pw = os.environ.get('LEVELS_PW')
    if not pw:
        print("未設定 LEVELS_PW，跳過(不覆蓋現有 levels.html)。用法: LEVELS_PW=密碼 python build_levels_page.py")
        return
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            levels_watch.run()
        except Exception as e:
            print(f"(關卡產生出錯：{e})")
    text = buf.getvalue()
    salt, iv, ct = encrypt(text, pw)
    html = (HTML.replace("__SALT__", salt).replace("__IV__", iv)
                .replace("__CT__", ct).replace("__ITER__", str(ITER)))
    out = os.path.join(HERE, "levels.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已產生加密 levels.html（原文 {len(text)} 字 → 密文 base64 {len(ct)} 字，含成本資料都在密文裡）")


if __name__ == "__main__":
    main()
