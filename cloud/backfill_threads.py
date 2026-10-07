"""이미 저장된 Threads 하위 글의 제목·썸네일을 새 규칙(cloud/api.py fetch_link_preview)으로 보정한다.
기본은 미리보기(아무것도 쓰지 않음). --apply 를 붙이면 S3 데이터 파일에 조건부 쓰기(If-Match)로 반영한다.
사용: python3 cloud/backfill_threads.py [--apply]"""
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUCKET, KEY = '<SITE_DOMAIN>', 'data/cards.json'
AWS = ['--profile', '<AWS_PROFILE>', '--region', '<AWS_REGION>']

sys.modules.setdefault('boto3', types.SimpleNamespace(client=lambda *a, **kw: None))
sys.modules.setdefault('botocore', types.ModuleType('botocore'))
sys.modules.setdefault('botocore.config', types.SimpleNamespace(Config=lambda **kw: None))
sys.modules.setdefault('botocore.exceptions', types.SimpleNamespace(ClientError=type('ClientError', (Exception,), {})))
import os
os.environ.setdefault('DATA_BUCKET', BUCKET)
spec = importlib.util.spec_from_file_location('api', ROOT / 'cloud/api.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


def aws(*args):
    r = subprocess.run(['aws', *args, *AWS], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return r.stdout.strip()


def fix(data):
    changes = []
    for x in data['items']:
        if x.get('deleted'):
            continue
        threads = [e for e in x.get('entries') or [] if e.get('kind') == 'link' and re.search(r'threads\.(com|net)', e.get('url', ''))]
        if not threads:
            continue
        touched = False
        for e in threads:
            _, title = api.fetch_link_preview(e['url'])
            if title and re.search(r' on Threads$', e.get('title', '')):
                changes.append(f"[{x.get('title', '')[:20]}] 하위 글 제목: {title[:40]}")
                e['title'] = title
                touched = True
            if '&amp;' in e.get('thumbnail', ''):
                e['thumbnail'] = e['thumbnail'].replace('&amp;', '&')
                touched = True
        if touched:
            x['revision'] = x.get('revision', 1) + 1
    return changes


def main():
    apply = '--apply' in sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        for attempt in range(3):
            src, dst = Path(tmp) / 'cur.json', Path(tmp) / 'new.json'
            etag = aws('s3api', 'get-object', '--bucket', BUCKET, '--key', KEY, str(src), '--query', 'ETag', '--output', 'text')
            version = aws('s3api', 'head-object', '--bucket', BUCKET, '--key', KEY, '--query', 'VersionId', '--output', 'text')
            data = json.loads(src.read_text())
            changes = fix(data)
            print(f'바뀔 항목 {len(changes)}개')
            for c in changes:
                print(' -', c)
            if not changes or not apply:
                print('미리보기만 함 — 반영하려면 --apply' if changes else '고칠 것 없음')
                return
            dst.write_text(json.dumps(data, ensure_ascii=False))
            try:
                aws('s3api', 'put-object', '--bucket', BUCKET, '--key', KEY, '--body', str(dst),
                    '--content-type', 'application/json', '--if-match', etag)
            except RuntimeError as e:
                if 'PreconditionFailed' in str(e) and attempt < 2:
                    print('그사이 데이터가 바뀌어 다시 시도합니다')
                    continue
                raise
            print(f'반영 완료. 되돌리려면 이전 버전 {version}을 복원하면 됩니다.')
            return


if __name__ == '__main__':
    main()
