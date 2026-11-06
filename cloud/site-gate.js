// CloudFront viewer-request 함수(cloudfront-js-2.0). 기본 동작(photos/* 제외)에 연결한다.
// __SESSION_SECRET__ 은 cloud/deploy_gate.py 가 배포 시 API Lambda 환경변수 값으로 채운다.
// __API_BASE__ 는 같은 스크립트가 배포된 config.js의 API 주소로 채운다.
// HOST 자리는 cloud/deploy_gate.py 가 cloud/site.json 의 site_domain 으로 채운다(그 외 호스트는 이 도메인으로 301).
import crypto from 'crypto';

const HOST = '__SITE_DOMAIN__';
const SECRET = '__SESSION_SECRET__';
const API = '__API_BASE__';
const PUBLIC = ['/apple-touch-icon.png', '/apple-touch-icon-precomposed.png', '/favicon.ico'];

function gatePage(bad) {
  return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>서랍</title>' +
    '<link rel="icon" type="image/png" href="/photos/site-favicon-v1.png"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png?v=3">' +
    '<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f7f7f2;color:#232b28;font:15px -apple-system,BlinkMacSystemFont,sans-serif}' +
    'form{background:#fff;border:1px solid #e0e4da;border-radius:18px;padding:22px;width:min(92vw,420px);box-sizing:border-box}b{display:block;font-size:18px;margin-bottom:6px}' +
    'p{color:#6b756c;margin:0 0 14px}.err{color:#b5433a}.row{display:flex;gap:8px}.box{position:relative;flex:1;min-width:0}input{width:100%;box-sizing:border-box;padding:13px 38px 13px 13px;border:1px solid #dbe0d7;border-radius:10px;font-size:16px}' +
    '#x{position:absolute;right:6px;top:50%;transform:translateY(-50%);width:28px;height:28px;padding:0;background:none;color:#6b756c;font-size:18px}' +
    'button{border:0;border-radius:12px;padding:0 18px;background:#314f3a;color:#fff;font:inherit}</style>' +
    '<form id="f"><b>서랍</b><p id="m">비밀번호를 입력하세요.</p><div class="row"><div class="box"><input id="k" type="password" placeholder="비밀번호" autocomplete="current-password" required><button id="x" type="button" aria-label="지우기">×</button></div><button id="o">열기</button></div></form>' +
    '<script>const bad=' + (bad ? 'true' : 'false') + ',API="' + API + '",$=i=>document.getElementById(i);' +
    'function go(t){document.cookie="shelf_key="+encodeURIComponent(t)+"; Path=/; Max-Age=31536000; Secure; SameSite=Lax";localStorage.setItem("shelf-key",t);location.reload()}' +
    'function say(t){$("m").textContent=t;$("m").className="err"}' +
    'const saved=localStorage.getItem("shelf-key");' +
    'if(bad||(saved&&!saved.startsWith("s1."))){localStorage.removeItem("shelf-key");document.cookie="shelf_key=; Path=/; Max-Age=0; Secure; SameSite=Lax"}else if(saved)go(saved);' +
    '$("x").onclick=()=>{$("k").value="";$("k").focus()};' +
    '$("f").onsubmit=async e=>{e.preventDefault();$("o").disabled=true;try{const r=await fetch(API+"/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:$("k").value})}),out=await r.json();if(r.ok)return go(out.token);say(out.error||"로그인하지 못했어요.")}catch(x){say("연결하지 못했어요. 잠시 후 다시 시도해 주세요.")}$("o").disabled=false}</script>';
}

function validSession(value) {
  const parts = value.split('.');
  if (parts.length !== 3 || parts[0] !== 's1' || !(Number(parts[1]) > Date.now() / 1000)) return false;
  return crypto.createHmac('sha256', SECRET).update('s1.' + parts[1]).digest('hex') === parts[2];
}

async function handler(event) {
  const req = event.request;
  const host = req.headers.host ? req.headers.host.value : '';
  if (host !== HOST) {
    return { statusCode: 301, statusDescription: 'Moved Permanently', headers: { location: { value: 'https://' + HOST + req.uri } } };
  }
  if (PUBLIC.includes(req.uri) || req.uri.startsWith('/shortcuts/')) return req;
  const cookie = req.cookies.shelf_key;
  if (cookie && cookie.value) {
    let value = '';
    try { value = decodeURIComponent(cookie.value); } catch (e) { value = ''; }
    if (validSession(value)) return req;
  }
  return {
    statusCode: 200,
    statusDescription: 'OK',
    headers: { 'content-type': { value: 'text/html; charset=utf-8' }, 'cache-control': { value: 'no-store' } },
    body: { encoding: 'text', data: gatePage(!!(cookie && cookie.value)) },
  };
}
