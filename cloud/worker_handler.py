"""Lambda entry point for the serverless worker.

Mirrors cloud/worker.py's claim -> organize/extract -> complete loop, but bounded
(drains the queue up to a limit or until time runs out) instead of an infinite
polling loop, since Lambda is invoked on demand rather than run continuously.
Credentials for Codex/Claude Code are pulled from Secrets Manager into /tmp on
cold start (Lambda's filesystem is read-only outside /tmp).
"""
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

os.environ.setdefault('SHELF_DATA_DIR', '/tmp/data')
os.environ['HOME'] = '/tmp'

API = os.environ['API_URL']
TOKEN = os.environ['WORKER_TOKEN']
SECRET_ARN = os.environ['AUTH_SECRET_ARN']

_bootstrapped = False

def bootstrap_credentials():
    global _bootstrapped
    if _bootstrapped:
        return
    import boto3
    secret = json.loads(boto3.client('secretsmanager').get_secret_value(SecretId=SECRET_ARN)['SecretString'])
    codex_dir = Path('/tmp/.codex')
    codex_dir.mkdir(parents=True, exist_ok=True)
    auth_path = codex_dir / 'auth.json'
    auth_path.write_text(json.dumps(secret['codex_auth']))
    auth_path.chmod(0o600)
    os.environ['CLAUDE_CODE_OAUTH_TOKEN'] = secret['claude_token']
    _bootstrapped = True

def call(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)

def handler(event, context):
    bootstrap_credentials()
    from server import organize, extract_excerpt, summarize_memo, SummaryUnavailable
    processed = 0
    while processed < 20 and context.get_remaining_time_in_millis() > 30000:
        try:
            job = call('/worker/claim', {})
        except (urllib.error.URLError, OSError):
            break
        item = job.get('item')
        if not item:
            break
        kind = item.get('kind')
        try:
            if kind == 'memo-extract':
                out = extract_excerpt(item.get('instruction', ''), item.get('source_snapshot', ''))
                if out['sufficient'] and out['summary'].strip():
                    result = {'status': 'ready', 'title': out['title'][:160], 'content': out['summary'][:100000]}
                else:
                    result = {'status': 'needs_content', 'error': '요청한 내용을 메모에서 찾지 못했습니다.'}
            elif kind == 'memo-summary':
                out = summarize_memo(item.get('content', ''))
                summary = out['summary'][:300] if out.get('sufficient') and out.get('summary', '').strip() else ''
                result = {'status': 'ready', 'summary': summary}
            elif item.get('image_download'):
                with tempfile.TemporaryDirectory(prefix='organize-', dir='/tmp') as temp:
                    urls = item.get('entries_download') or [item['image_download']]
                    photos = []
                    for i, url in enumerate(urls):
                        photo = Path(temp) / f'image{i}.jpg'
                        with urllib.request.urlopen(url, timeout=30) as res:
                            blob = res.read(10_000_001)
                        if len(blob) > 10_000_000:
                            raise ValueError('사진 용량 초과')
                        photo.write_bytes(blob)
                        photos.append(photo)
                    result = organize(item, folders=job['folders'], persist=False,
                                       image_path=photos if len(photos) > 1 else photos[0])
            else:
                result = organize(item, folders=job['folders'], persist=False)
        except (SummaryUnavailable, subprocess.TimeoutExpired):
            if kind == 'memo-extract':
                result = {'status': 'ai_waiting', 'error': 'AI 추출 대기 중입니다. 1시간 뒤 다시 시도합니다.'}
            elif kind == 'memo-summary':
                result = {'status': 'ai_waiting', 'summary': ''}
            else:
                result = {'status': 'ai_waiting', 'error': 'AI 요약 대기 중입니다. 링크는 저장되어 있으며 1시간 뒤 다시 시도합니다.'}
        except Exception:
            if kind == 'memo-extract':
                result = {'status': 'needs_content', 'error': '추출 중 오류가 발생했습니다.'}
            elif kind == 'memo-summary':
                result = {'status': 'ready', 'summary': ''}
            else:
                result = {'status': 'needs_content', 'error': '본문을 충분히 읽지 못했습니다. 본문을 추가하면 다시 정리합니다.'}
        complete = {'id': item['id'], 'lease': item['lease'], 'revision': item.get('revision', 1), 'result': result}
        if kind in ('memo-extract', 'memo-summary'):
            complete['kind'] = kind
        try:
            call('/worker/complete', complete)
        except (urllib.error.URLError, OSError):
            break
        processed += 1
    return {'processed': processed}
