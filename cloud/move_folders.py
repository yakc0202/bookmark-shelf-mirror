"""정해 둔 카드들의 폴더를 한 번에 옮긴다(폴더 정리용).
계획 파일 data/cloud-build/folder-moves.json: {"카드 id": {"from": "지금 폴더", "to": "옮길 폴더"}}
미리보기: 계획대로 옮길 카드와 현재 상태를 보여준다(데이터는 안 씀).
--apply: S3 데이터 파일에 조건부 쓰기. 그사이 폴더가 바뀐 카드(지금 폴더가 from과 다름)는 건너뛴다.
사용: python3 cloud/move_folders.py [--apply]"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backfill_threads import BUCKET, KEY, aws  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'data/cloud-build/folder-moves.json'


def main():
    plan = json.loads(PLAN.read_text())
    apply = '--apply' in sys.argv
    with tempfile.TemporaryDirectory() as tmp:
        for attempt in range(3):
            src, dst = Path(tmp) / 'cur.json', Path(tmp) / 'new.json'
            etag = aws('s3api', 'get-object', '--bucket', BUCKET, '--key', KEY, str(src), '--query', 'ETag', '--output', 'text')
            version = aws('s3api', 'head-object', '--bucket', BUCKET, '--key', KEY, '--query', 'VersionId', '--output', 'text')
            data = json.loads(src.read_text())
            n = 0
            for x in data['items']:
                move = plan.get(x['id'])
                if not move or x.get('deleted'):
                    continue
                if x.get('folder') != move['from']:
                    print(f"  건너뜀 [{x.get('title', '')[:30]}] 지금 폴더가 {x.get('folder')!r}")
                    continue
                print(f"  [{x.get('title', '')[:30]}] {move['from']} → {move['to']}")
                x['folder'] = move['to']
                x['revision'] = x.get('revision', 1) + 1
                n += 1
            if not apply or not n:
                print(f'옮길 카드 {n}개' + (' — 반영하려면 --apply' if n and not apply else ''))
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
            print(f'{n}개 옮김. 되돌리려면 이전 버전 {version}을 복원하면 됩니다.')
            return


if __name__ == '__main__':
    main()
