"""이미 저장된 모음(이어진 글) 카드의 주제를 정리 작업과 같은 AI 프롬프트로 추론해 채운다(주제만, 제목·요약·폴더는 그대로).
미리보기: 이 맥의 Codex/Claude CLI로 주제를 추론해 data/cloud-build/thread-topics.json에 저장하고 목록을 보여준다(데이터는 안 씀).
--apply: 저장된 목록 그대로 S3 데이터 파일에 조건부 쓰기(If-Match). 사용자가 직접 정한 주제는 덮어쓰지 않는다.
사용: python3 cloud/backfill_topics.py [--apply]"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backfill_threads import BUCKET, KEY, aws  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'data/cloud-build/thread-topics.json'
# 2026-10-07 작성자 이름으로 자동으로 넣었던 주제(사용자가 정한 게 아님) — 추론한 주제로 교체 대상
AUTHOR_TOPICS = {'Ai로 부업 알려주는 사람', 'JobPT', '옆집 인사팀 부장형', '📝 자소서Lab', '생각등대', '자소서체크', '딸깍'}


def targets(data):
    for x in data['items']:
        if x.get('deleted') or x.get('kind') == 'collection':
            continue
        if not any(e.get('kind') == 'link' for e in x.get('entries') or []):
            continue
        if not x.get('topic') or x['topic'] in AUTHOR_TOPICS:
            yield x


def preview(data):
    sys.path.insert(0, str(ROOT))
    import server
    folders = sorted({i['folder'] for i in data['items'] if not i.get('deleted')})
    plan = {}
    for x in targets(data):
        item = {k: x.get(k) for k in ('id', 'url', 'entries')}
        item['note'] = x.get('note') or ''
        try:
            topic = server.organize(item, folders=folders, persist=False).get('topic', '').strip()[:30]
        except Exception as e:
            print(f"  [{x.get('title', '')[:24]}] 추론 실패: {type(e).__name__}")
            continue
        if topic:
            plan[x['id']] = topic
            print(f"  [{x.get('title', '')[:24]}] {x.get('topic') or '(없음)'} → {topic}")
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    print(f'주제 {len(plan)}개를 {PLAN.relative_to(ROOT)}에 저장. 반영하려면 --apply')


def apply():
    plan = json.loads(PLAN.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        for attempt in range(3):
            src, dst = Path(tmp) / 'cur.json', Path(tmp) / 'new.json'
            etag = aws('s3api', 'get-object', '--bucket', BUCKET, '--key', KEY, str(src), '--query', 'ETag', '--output', 'text')
            version = aws('s3api', 'head-object', '--bucket', BUCKET, '--key', KEY, '--query', 'VersionId', '--output', 'text')
            data = json.loads(src.read_text())
            n = 0
            for x in targets(data):
                if x['id'] in plan:
                    x['topic'] = plan[x['id']]
                    x['revision'] = x.get('revision', 1) + 1
                    n += 1
            if not n:
                print('반영할 것 없음')
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
            print(f'주제 {n}개 반영 완료. 되돌리려면 이전 버전 {version}을 복원하면 됩니다.')
            return


if __name__ == '__main__':
    tmp_data = None
    if '--apply' in sys.argv:
        apply()
    else:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cur.json'
            aws('s3api', 'get-object', '--bucket', BUCKET, '--key', KEY, str(path))
            preview(json.loads(path.read_text()))
