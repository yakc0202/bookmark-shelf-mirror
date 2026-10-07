"""Explicit online smoke test: create a temporary photo, test sharing, then soft-delete it."""
import json,base64,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out=json.loads((ROOT/'data/cloud-build/outputs.json').read_text());key=(ROOT/'data/token').read_text().strip()
def call(path,body=None):
 req=urllib.request.Request(out['ApiURL']+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
original={x['id'] for x in call('/api/items')};item_id=None
try:
 photo=base64.b64encode(Path('/tmp/shelf-photo-test.jpg').read_bytes()).decode()
 item_id=call('/api/photos',{'image':photo})['id']
 rows=call('/api/items');item=next(x for x in rows if x['id']==item_id)
 assert item['kind']=='photo'
 with urllib.request.urlopen(item['thumbnail']) as r:assert r.headers['Content-Type']=='image/jpeg'
 token=call('/api/share',{'id':item_id})['token']
 with urllib.request.urlopen(out['ApiURL']+'/s/'+token) as r:
  page=r.read().decode();assert '공유받은 북마크' in page;assert r.headers['Referrer-Policy']=='no-referrer'
 call('/api/unshare',{'id':item_id})
 try:urllib.request.urlopen(out['ApiURL']+'/s/'+token);raise AssertionError('share not revoked')
 except urllib.error.HTTPError as e:assert e.code==404
 print('PASS: photo upload/private signed image/share/revoke',flush=True)
 for _ in range(42):
  item=next(x for x in call('/api/items') if x['id']==item_id)
  if item['status'] not in ('queued','processing'):break
  time.sleep(5)
 print('Photo classification:',item['status'],item['folder'],flush=True)
finally:
 if item_id:call('/api/delete',{'id':item_id})
 assert {x['id'] for x in call('/api/items')}==original
 print('PASS: original bookmarks retained; temporary card deleted',flush=True)
