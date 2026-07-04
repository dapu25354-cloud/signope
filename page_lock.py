# -*- coding: utf-8 -*-
"""
網頁密碼鎖(共用) — 兩頁(雷達/加碼區)都套同一個鎖，輸一次兩頁都通。
- 客戶端驗證：只存密碼的 SHA-256 指紋，明碼不進網路。
- 等級：擋一般人(親友/鄰居/隨手點連結)夠用；懂技術硬要看仍可繞(靜態網頁先天限制)。
- 要換密碼：改下面 PASSWORD_SHA256(用 python -c "import hashlib;print(hashlib.sha256('新密碼'.encode()).hexdigest())" 產生)。
"""

# radar888 的指紋(臨時密碼，之後可換)
PASSWORD_SHA256 = "1571d02308bd8adf980dc679f575a87cb0d1e2dbaab4cd32b6f6d37085db92bd"

_GATE = """
<div id="pw-gate" style="position:fixed;inset:0;background:#0d1117;z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'Noto Sans TC',sans-serif;padding:20px">
  <div style="color:#e6edf3;font-size:20px;margin-bottom:16px">&#128274; 請輸入密碼</div>
  <div style="position:relative;width:240px">
    <input id="pw-input" type="password" placeholder="密碼" autocomplete="off" style="padding:12px 44px 12px 16px;font-size:16px;border-radius:10px;border:1px solid #30363d;background:#161b22;color:#e6edf3;width:100%;box-sizing:border-box;text-align:center;outline:none">
    <span id="pw-eye" title="顯示/隱藏密碼" style="position:absolute;right:12px;top:50%;transform:translateY(-50%);cursor:pointer;font-size:19px;user-select:none">&#128065;</span>
  </div>
  <button id="pw-btn" style="margin-top:14px;padding:11px 28px;font-size:15px;border:0;border-radius:10px;background:#2ea043;color:#fff;font-weight:700;cursor:pointer">進入</button>
  <div id="pw-err" style="color:#f85149;font-size:13px;margin-top:12px;height:16px"></div>
</div>
<script>
(function(){
  var HASH="__HASH__";
  var gate=document.getElementById('pw-gate');
  function unlock(){ gate.style.display='none'; document.body.style.overflow=''; }
  if(localStorage.getItem('radar_ok')==='1'){ unlock(); }
  else { document.body.style.overflow='hidden'; }
  async function check(){
    var v=document.getElementById('pw-input').value;
    try{
      var buf=await crypto.subtle.digest('SHA-256', new TextEncoder().encode(v));
      var hex=Array.from(new Uint8Array(buf)).map(function(b){return b.toString(16).padStart(2,'0');}).join('');
      if(hex===HASH){ localStorage.setItem('radar_ok','1'); unlock(); }
      else { document.getElementById('pw-err').textContent='密碼錯誤，再試一次'; }
    }catch(e){ document.getElementById('pw-err').textContent='此瀏覽器不支援，請用 Chrome/Safari'; }
  }
  document.getElementById('pw-btn').onclick=check;
  document.getElementById('pw-input').addEventListener('keydown', function(e){ if(e.key==='Enter') check(); });
  var inp=document.getElementById('pw-input'), eye=document.getElementById('pw-eye');
  eye.onclick=function(){
    if(inp.type==='password'){ inp.type='text'; eye.innerHTML='&#128584;'; }
    else { inp.type='password'; eye.innerHTML='&#128065;'; }
    inp.focus();
  };
})();
</script>
"""


def inject(html, password_hash=PASSWORD_SHA256):
    """把密碼鎖插進 <body> 之後。已經有鎖就不重複插。"""
    if 'id="pw-gate"' in html:
        return html
    gate = _GATE.replace("__HASH__", password_hash)
    return html.replace("<body>", "<body>" + gate, 1)
