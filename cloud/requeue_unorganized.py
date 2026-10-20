"""요약 없이 남은 카드(내용 부족, 또는 완료인데 요약이 빈 링크 카드)를 다시 정리 대기로 돌린다.
사진 카드는 요약을 비워 두는 게 정상이라 빼고, 모음 카드도 뺀다. 내용 부족 카드의 추측 태그는 이때 뗀다.
다시 정리하면 AI 결과로 제목·폴더가 바뀔 수 있다(사용자가 옮긴 폴더도). 반영 뒤 바뀐 폴더를 확인하고 필요하면 되돌린다.
기본은 미리보기(아무것도 쓰지 않음). --apply 를 붙이면 S3 데이터 파일에 조건부 쓰기(If-Match)로 반영한다.
사용: python3 cloud/requeue_unorganized.py [--apply]"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backfill_threads import BUCKET, KEY, aws, api  # noqa: E402


def fix(data):
    changes = []
    for x in data['items']:
        if x.get('deleted') or x.get('kind') in ('photo', 'collection'):
            continue
        empty = not (x.get('summary') or '').strip()
        if x.get('status') == 'needs_content' or (x.get('status') == 'ready' and empty):
            changes.append(f"[{x.get('status')}] {x.get('title', '')[:30]} — {x.get('url', '')[:60]}")
            if x.get('status') == 'needs_content':
                x['tags'] = '[]'
            api.requeue(x)
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
            print(f'다시 정리할 카드 {len(changes)}개')
            for c in changes:
                print(' -', c)
            if not changes or not apply:
                print('미리보기만 함 — 반영하려면 --apply' if changes else '다시 정리할 것 없음')
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
