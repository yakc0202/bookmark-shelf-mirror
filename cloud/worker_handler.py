"""Lambda entry point for the serverless worker.

Mirrors cloud/worker.py's claim -> organize/extract -> complete loop, but bounded
(drains the queue up to a limit or until time runs out) instead of an infinite
polling loop, since Lambda is invoked on demand rather than run continuously.
Credentials for Codex/Claude Code are pulled from SSM Parameter Store
(AUTH_PARAM_PREFIX, two SecureString parameters) into /tmp on cold start
(Lambda's filesystem is read-only outside /tmp). AUTH_SECRET_ARN (Secrets
Manager) is the old location, still read when AUTH_PARAM_PREFIX is unset so a
rollback is just an env var change.
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
PARAM_PREFIX = os.environ.get('AUTH_PARAM_PREFIX')
SECRET_ARN = os.environ.get('AUTH_SECRET_ARN')

CODEX_AUTH = Path('/tmp/.codex/auth.json')

def load_auth():
    """(codex auth.json dict, claude token). SSM이 기본, 없으면 예전 Secrets Manager."""
    import boto3
    if PARAM_PREFIX:
        names = [PARAM_PREFIX + 'codex-auth', PARAM_PREFIX + 'claude-token']
        out = boto3.client('ssm').get_parameters(Names=names, WithDecryption=True)
        if out.get('InvalidParameters'):
            raise RuntimeError('missing SSM parameters: ' + ', '.join(out['InvalidParameters']))
        values = {p['Name']: p['Value'] for p in out['Parameters']}
        return json.loads(values[names[0]]), values[names[1]]
    secret = json.loads(boto3.client('secretsmanager').get_secret_value(SecretId=SECRET_ARN)['SecretString'])
    return secret['codex_auth'], secret['claude_token']

def bootstrap_credentials():
    """실행마다 SSM에서 로그인 정보를 받아 /tmp에 둔다(다른 실행이 갱신해 저장한 Codex 토큰을 쓰도록). 받은 Codex 값을 돌려준다."""
    codex_auth, claude_token = load_auth()
    CODEX_AUTH.parent.mkdir(parents=True, exist_ok=True)
    CODEX_AUTH.write_text(json.dumps(codex_auth))
    CODEX_AUTH.chmod(0o600)
    os.environ['CLAUDE_CODE_OAUTH_TOKEN'] = claude_token
    return codex_auth

def save_refreshed_codex_auth(before):
    """Codex가 실행 중 토큰을 갱신했으면 새 값을 SSM에 다시 저장한다(갱신 토큰은 한 번만 쓸 수 있어, 안 그러면 다음 실행이 옛 값으로 실패)."""
    if not PARAM_PREFIX:
        return
    try:
        after = json.loads(CODEX_AUTH.read_text())
    except (OSError, ValueError):
        return
    if after == before or not isinstance(after, dict) or 'tokens' not in after:
        return
    import boto3
    try:
        boto3.client('ssm').put_parameter(Name=PARAM_PREFIX + 'codex-auth', Value=json.dumps(after, separators=(',', ':')),
                                          Type='SecureString', Tier='Intelligent-Tiering', Overwrite=True)
        print('codex 로그인 갱신분을 SSM에 저장', flush=True)
    except Exception as e:
        print('codex 로그인 갱신분 저장 실패:', type(e).__name__, str(e)[:160], flush=True)

def call(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)

def handler(event, context):
    codex_before = bootstrap_credentials()
    try:
        return drain(context)
    finally:
        save_refreshed_codex_auth(codex_before)

def drain(context):
    from server import organize, extract_excerpt, summarize_memo, extract_bookings, extract_wishes, SummaryUnavailable
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
            elif kind in ('schedule-import', 'wish-import'):
                with tempfile.TemporaryDirectory(prefix='capture-', dir='/tmp') as temp:
                    photo = Path(temp) / 'capture.jpg'
                    with urllib.request.urlopen(item['image_download'], timeout=30) as res:
                        photo.write_bytes(res.read(10_000_001))
                    result = ({'status': 'ready', 'bookings': extract_bookings(photo)} if kind == 'schedule-import'
                              else {'status': 'ready', 'items': extract_wishes(photo)})
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
        except (SummaryUnavailable, subprocess.TimeoutExpired) as e:
            print('ai_waiting', kind or 'card', item['id'][:6], type(e).__name__, str(e)[:200], flush=True)
            if kind == 'memo-extract':
                result = {'status': 'ai_waiting', 'error': 'AI 추출 대기 중입니다. 1시간 뒤 다시 시도합니다.'}
            elif kind == 'memo-summary':
                result = {'status': 'ai_waiting', 'summary': ''}
            elif kind in ('schedule-import', 'wish-import'):
                result = {'status': 'ai_waiting', 'error': 'AI가 바빠서 1시간 뒤 다시 읽습니다.'}
            else:
                result = {'status': 'ai_waiting', 'error': 'AI 요약 대기 중입니다. 링크는 저장되어 있으며 1시간 뒤 다시 시도합니다.'}
        except Exception:
            if kind == 'memo-extract':
                result = {'status': 'needs_content', 'error': '추출 중 오류가 발생했습니다.'}
            elif kind == 'memo-summary':
                result = {'status': 'ready', 'summary': ''}
            elif kind == 'schedule-import':
                result = {'status': 'needs_content', 'error': '캡처에서 예약을 읽지 못했어요.'}
            elif kind == 'wish-import':
                result = {'status': 'needs_content', 'error': '사진에서 상품을 읽지 못했어요.'}
            else:
                result = {'status': 'needs_content', 'error': '본문을 충분히 읽지 못했습니다. 본문을 추가하면 다시 정리합니다.'}
        complete = {'id': item['id'], 'lease': item['lease'], 'revision': item.get('revision', 1), 'result': result}
        if kind in ('memo-extract', 'memo-summary', 'schedule-import', 'wish-import'):
            complete['kind'] = kind
        try:
            call('/worker/complete', complete)
        except (urllib.error.URLError, OSError):
            break
        processed += 1
    return {'processed': processed}
