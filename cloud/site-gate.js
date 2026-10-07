// CloudFront viewer-request 함수(cloudfront-js-2.0). 기본 동작(photos/* 제외)에 연결한다.
// __CLIENT_TOKEN_HASH__ 는 cloud/deploy_gate.py 가 배포 시 API Lambda 환경변수 값으로 채운다.
import crypto from 'crypto';

const HOST = '<SITE_DOMAIN>';
const KEY_HASH = '__CLIENT_TOKEN_HASH__';
const PUBLIC = ['/apple-touch-icon.png', '/apple-touch-icon-precomposed.png', '/favicon.ico'];

function gatePage(bad) {
  const msg = bad ? '<p class="err">접속 키가 맞지 않아요. 다시 입력해 주세요.</p>' : '<p>접속 키를 입력하세요.</p>';
  return '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>서랍</title>' +
    '<link rel="icon" type="image/png" href="/photos/site-favicon-v1.png"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png?v=3">' +
    '<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f7f7f2;color:#232b28;font:15px -apple-system,BlinkMacSystemFont,sans-serif}' +
    'form{background:#fff;border:1px solid #e0e4da;border-radius:18px;padding:22px;width:min(92vw,420px);box-sizing:border-box}b{display:block;font-size:18px;margin-bottom:6px}' +
    'p{color:#6b756c;margin:0 0 14px}.err{color:#b5433a}.row{display:flex;gap:8px}input{flex:1;min-width:0;padding:13px;border:1px solid #dbe0d7;border-radius:10px;font-size:16px}' +
    'button{border:0;border-radius:12px;padding:0 18px;background:#314f3a;color:#fff;font:inherit}</style>' +
    '<form id="f"><b>서랍</b>' + msg + '<div class="row"><input id="k" type="password" placeholder="접속 키" autocomplete="current-password"><button>열기</button></div></form>' +
    '<script>const bad=' + (bad ? 'true' : 'false') + ';function go(k){document.cookie="shelf_key="+encodeURIComponent(k)+"; Path=/; Max-Age=31536000; Secure; SameSite=Lax";localStorage.setItem("shelf-key",k);location.reload()}' +
    'const saved=localStorage.getItem("shelf-key");if(saved&&!bad)go(saved);' +
    'document.getElementById("f").onsubmit=e=>{e.preventDefault();const k=document.getElementById("k").value.trim();if(k)go(k)}</script>';
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
    let key = '';
    try { key = decodeURIComponent(cookie.value); } catch (e) { key = ''; }
    if (crypto.createHash('sha256').update(key).digest('hex') === KEY_HASH) return req;
  }
  return {
    statusCode: 200,
    statusDescription: 'OK',
    headers: { 'content-type': { value: 'text/html; charset=utf-8' }, 'cache-control': { value: 'no-store' } },
    body: { encoding: 'text', data: gatePage(!!(cookie && cookie.value)) },
  };
}
