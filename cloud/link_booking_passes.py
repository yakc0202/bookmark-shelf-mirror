"""이용권이 연결되지 않은 운동 예약(pass_id 빈 값)을 cloud/api.py pick_pass와 같은 규칙으로 이용권에 연결한다.
2026-10-09 이전 캡처 가져오기는 수업 이름이 이용권 이름에 들어 있을 때만 연결해서, 예약이 남은 횟수에 안 잡혔다.
기본은 미리보기(아무것도 쓰지 않음). --apply 를 붙이면 S3 데이터 파일에 조건부 쓰기(If-Match)로 반영한다.
사용: python3 cloud/link_booking_passes.py [--apply]"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backfill_threads import BUCKET, KEY, aws  # noqa: E402


def norm_title(t):
    return re.sub(r'\s+', '', str(t or '')).lower()


def pick_pass(sched, booking):  # cloud/api.py pick_pass와 같은 규칙
    usable = [p for p in sched['passes'] if not p.get('expires') or p['expires'] >= booking['date']]
    if len(usable) == 1:
        return usable[0]['id']
    named = [p for p in usable if norm_title(booking['title']) and norm_title(booking['title']) in norm_title(p['title'])]
    return named[0]['id'] if len(named) == 1 else ''


def fix(data):
    sched = data.get('schedule') or {}
    names = {p['id']: p['title'] for p in sched.get('passes', [])}
    changes = []
    for b in sched.get('bookings', []):
        if b.get('pass_id'):
            continue
        pid = pick_pass(sched, b)
        if pid:
            b['pass_id'] = pid
            changes.append(f"{b['date']} {b['start']} {b['title']} ({b.get('status', 'booked')}) → {names[pid]}")
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
            print(f'연결할 예약 {len(changes)}개')
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
