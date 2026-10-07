"""Upload snapshot and web assets using only the explicitly authorized bookmark profile."""
import json,sqlite3,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
env=os.environ.copy()
for key in ('AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN','AWS_SECURITY_TOKEN','AWS_PROFILE','AWS_DEFAULT_PROFILE'):env.pop(key,None)
def aws(*args):
 return subprocess.check_output(['aws',*args,'--profile','<AWS_PROFILE>','--region','<AWS_REGION>'],env=env,text=True)
outputs=json.loads(aws('cloudformation','describe-stacks','--stack-name','<API_STACK_NAME>','--query','Stacks[0].Outputs'))
out={x['OutputKey']:x['OutputValue'] for x in outputs}
out['ApiURL']=out['ApiURL'].rstrip('/')
build=ROOT/'data/cloud-build'
c=sqlite3.connect('data/shelf.db');c.row_factory=sqlite3.Row
with sqlite3.connect(build/'migration-backup.db') as dst:c.backup(dst)
deleted={r[0] for r in c.execute('SELECT id FROM deleted_items')}
rows=[dict(r) for r in c.execute('SELECT * FROM items')]
for r in rows:
 r.update(revision=1,deleted=r['id'] in deleted)
 if r['status']=='processing':r['status']='queued'
f=build/'cards.json';f.write_text(json.dumps({'version':1,'items':rows},ensure_ascii=False));f.chmod(0o600)
# Only create the cloud snapshot once: never overwrite subsequent online edits.
aws('s3api','put-object','--bucket',out['DataBucket'],'--key','data/cards.json','--body',str(f),'--content-type','application/json','--if-none-match','*')
check=build/'verified-cards.json'
aws('s3api','get-object','--bucket',out['DataBucket'],'--key','data/cards.json',str(check))
assert json.loads(check.read_text())==json.loads(f.read_text())
(build/'config.js').write_text('window.SHELF_API_BASE = '+json.dumps(out['ApiURL'])+';\n')
for local,key in [(ROOT/'static/index.html','index.html'),(build/'config.js','config.js')]:
 aws('s3api','put-object','--bucket',out['WebsiteBucket'],'--key',key,'--body',str(local),'--content-type','text/html; charset=utf-8' if key.endswith('html') else 'application/javascript','--cache-control','no-cache')
worker=ROOT/'data/cloud-worker.json'
worker.write_text(json.dumps({'api':out['ApiURL'],'token':(ROOT/'data/cloud-worker-token').read_text().strip()}));worker.chmod(0o600)
(build/'outputs.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'outputs':out,'migrated':len(rows),'visible':len(rows)-len(deleted),'verified':True},ensure_ascii=False))
