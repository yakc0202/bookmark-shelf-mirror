"""메모 본문에 절대 주소로 박힌 사진(https://<도메인>/photos/<32자>.jpg)을 사이트 기준 상대 주소(/photos/…)로 바꾼다.
상대 주소는 어느 도메인에서 열어도 그 사이트의 photos/ 에서 불러오므로, 도메인을 바꿔도 메모 사진이 깨지지 않는다.
기본은 미리보기(아무것도 쓰지 않음). --apply 를 붙이면 S3 데이터 파일에 조건부 쓰기(If-Match)로 반영한다.
사용: python3 cloud/relink_memo_photos.py [--apply]"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backfill_threads import BUCKET, KEY, aws  # noqa: E402

PHOTO = re.compile(r'\]\(https://[A-Za-z0-9.-]+(/photos/[a-f0-9]{32}\.jpg)\)')


def fix(data):
    changes = []
    for m in data.get('memos', []):
        content = m.get('content') or ''
        new, n = PHOTO.subn(r'](\1)', content)
        if n:
            m['content'] = new
            m['revision'] = m.get('revision', 1) + 1
            changes.append(f"[{(m.get('title') or '')[:20]}] 사진 주소 {n}개")
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
            print(f'바뀔 메모 {len(changes)}개')
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
