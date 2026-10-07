"""Run on the Mac; cloud credentials are a scoped worker token, never AWS default."""
import json
import sys
import time
import urllib.error
import urllib.request
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server import organize, extract_excerpt, summarize_memo, SummaryUnavailable

config=json.loads((ROOT/'data/cloud-worker.json').read_text())
if not config['api'].startswith('https://'):raise SystemExit('HTTPS API 주소가 필요합니다.')

def call(path,body):
    req=urllib.request.Request(config['api']+path,data=json.dumps(body).encode(),
        headers={'Authorization':'Bearer '+config['token'],'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as res:return json.load(res)

while True:
    try:
        job=call('/worker/claim',{})
        item=job.get('item')
        if not item:
            time.sleep(60)
            continue
        kind=item.get('kind')
        try:
            if kind=='memo-extract':
                out=extract_excerpt(item.get('instruction',''),item.get('source_snapshot',''))
                if out['sufficient'] and out['summary'].strip():
                    result={'status':'ready','title':out['title'][:160],'content':out['summary'][:100000]}
                else:
                    result={'status':'needs_content','error':'요청한 내용을 메모에서 찾지 못했습니다.'}
            elif kind=='memo-summary':
                out=summarize_memo(item.get('content',''))
                summary=out['summary'][:300] if out.get('sufficient') and out.get('summary','').strip() else ''
                result={'status':'ready','summary':summary}
            elif item.get('image_download'):
                with tempfile.TemporaryDirectory(prefix='photo-',dir=ROOT/'data') as temp:
                    urls=item.get('entries_download') or [item['image_download']]
                    photos=[]
                    for i,url in enumerate(urls):
                        photo=Path(temp)/f'image{i}.jpg'
                        with urllib.request.urlopen(url,timeout=30) as res:blob=res.read(10_000_001)
                        if len(blob)>10_000_000:raise ValueError('사진 용량 초과')
                        photo.write_bytes(blob)
                        photos.append(photo)
                    result=organize(item,folders=job['folders'],persist=False,image_path=photos if len(photos)>1 else photos[0])
            else:result=organize(item,folders=job['folders'],persist=False)
        except (SummaryUnavailable,subprocess.TimeoutExpired):
            if kind=='memo-extract':result={'status':'ai_waiting','error':'AI 추출 대기 중입니다. 1시간 뒤 다시 시도합니다.'}
            elif kind=='memo-summary':result={'status':'ai_waiting','summary':''}
            else:result={'status':'ai_waiting','error':'AI 요약 대기 중입니다. 링크는 저장되어 있으며 1시간 뒤 다시 시도합니다.'}
        except Exception:
            if kind=='memo-extract':result={'status':'needs_content','error':'추출 중 오류가 발생했습니다.'}
            elif kind=='memo-summary':result={'status':'ready','summary':''}
            else:result={'status':'needs_content','error':'본문을 충분히 읽지 못했습니다. 본문을 추가하면 다시 정리합니다.'}
        complete={'id':item['id'],'lease':item['lease'],'revision':item.get('revision',1),'result':result}
        if kind in ('memo-extract','memo-summary'):complete['kind']=kind
        call('/worker/complete',complete)
        print('처리 완료:',item['id'],result['status'],flush=True)
    except urllib.error.HTTPError as e:
        print('API 응답:',e.code,flush=True)
        time.sleep(60)
    except Exception as e:
        print('워커 연결 대기:',type(e).__name__,flush=True)
        time.sleep(60)
