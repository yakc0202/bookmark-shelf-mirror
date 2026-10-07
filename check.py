import json
import urllib.request
import urllib.error
from pathlib import Path

key = (Path(__file__).parent / 'data/token').read_text().strip()
def request(path, data=None, auth=True):
    req = urllib.request.Request('http://127.0.0.1:8787' + path,
        data=json.dumps(data).encode() if data else None,
        headers={'Content-Type':'application/json', **({'Authorization':'Bearer '+key} if auth else {})})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=10) as res:
        return res.status, json.load(res)

try:
    request('/api/items', auth=False)
    raise AssertionError('인증 누락')
except urllib.error.HTTPError as e:
    assert e.code == 401
payload = {'text':'https://example.com/link-shelf-car-demo',
           'note':'[시제품 테스트용 가상 게시물] 전기차 시승 후기. 도심에서는 실내가 조용하고 가속이 부드러웠다. 뒷좌석 공간은 넓었지만 고속 주행에서는 타이어 소음이 들렸다. 충전 환경을 확인한 다음 구매를 결정하는 편이 좋겠다.'}
a,b = request('/api/items', payload)
assert a in (200,201)
c,d = request('/api/items', payload)
assert c == 200 and b['id'] == d['id']
a,items = request('/api/items')
assert any(x['id'] == b['id'] for x in items)
print('PASS: authentication, save, deduplication, list. Test card queued for real Codex processing.')
