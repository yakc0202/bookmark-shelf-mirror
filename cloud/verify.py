import json,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
o=json.loads((ROOT/'data/cloud-build/outputs.json').read_text())
token=(ROOT/'data/token').read_text().strip()
def call(path,body=None,auth=True):
 req=urllib.request.Request(o['ApiURL']+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token if auth else '', 'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
rows=call('/api/items');expected=json.loads((ROOT/'data/cloud-build/cards.json').read_text())['items']
assert len(rows)==len(expected)
for row in rows:
 old=next(x for x in expected if x['id']==row['id'])
 assert all(old[k]==v for k,v in row.items())
try:call('/api/items',auth=False);raise AssertionError('unauthorized access')
except urllib.error.HTTPError as e:assert e.code==401
first=rows[0]
assert call('/api/items',{'url':first['url']})['id']==first['id']
try:
 call('/api/delete',{'id':first['id']})
 assert len(call('/api/items'))==len(rows)-1
finally:call('/api/restore',{'id':first['id']})
assert call('/api/items')==rows
req=urllib.request.Request(o['ApiURL']+'/api/items',method='OPTIONS',headers={'Origin':'http://<SITE_DOMAIN>','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
with urllib.request.urlopen(req) as r:assert r.headers['Access-Control-Allow-Origin']=='http://<SITE_DOMAIN>'
with urllib.request.urlopen(o['WebsiteURL']) as r:assert r.status==200
try:urllib.request.urlopen('https://s3.<AWS_REGION>.amazonaws.com/<SITE_DOMAIN>/data/cards.json');raise AssertionError('public data')
except urllib.error.HTTPError as e:assert e.code==403
print('PASS: 16 cards preserved, auth, duplicate, delete/restore, CORS, website, private JSON')
