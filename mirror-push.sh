#!/bin/sh
# 공개 미러(bookmark-shelf-mirror)로 이 저장소의 추적 파일을 내보낸다. 보안 관련 값은 하나도 내보내지 않는다.
#   ./mirror-push.sh                 미리보기: 미러 사본을 만들어 바뀔 파일·검사 결과만 보여주고 되돌림(push 안 함)
#   ./mirror-push.sh --push          사용자 확인을 받은 뒤 실제 커밋·push(일반 push, force-push 아님)
# 실제 값 목록은 data/mirror-redact.txt(커밋 안 됨). 남은 값이 하나라도 있으면 커밋·push 없이 멈춘다.
set -eu
MODE=${1:---check}
case "$MODE" in --check|--push) ;; *) echo "알 수 없는 옵션: $MODE"; exit 1 ;; esac
SRC=$(cd "$(dirname "$0")" && git rev-parse --show-toplevel)
MIRROR=${MIRROR_DIR:-"$HOME/Documents/Codex/bookmark-shelf-mirror"}
REDACT="$SRC/data/mirror-redact.txt"
[ -f "$REDACT" ] || { echo "중단: $REDACT 가 없음 (가릴 값 목록이 필요)"; exit 1; }
[ -d "$MIRROR/.git" ] || git clone -q https://github.com/<GITHUB_USER>/bookmark-shelf-mirror "$MIRROR"
git -C "$MIRROR" fetch -q origin
git -C "$MIRROR" checkout -q -f main
git -C "$MIRROR" reset -q --hard origin/main
git -C "$MIRROR" clean -fdq
restore() { git -C "$MIRROR" checkout -q -f main; git -C "$MIRROR" reset -q --hard origin/main; git -C "$MIRROR" clean -fdq; }

python3 - "$SRC" "$MIRROR" "$REDACT" <<'PY' || { restore; exit 1; }
import re, shutil, subprocess, sys
from pathlib import Path
src, mirror, redact = map(Path, sys.argv[1:])
# 공개하지 않는 파일: API 주소가 박힌 단축어(바이너리라 가릴 수 없음). REQUESTS.md 등 문서는 값을 가린 채로 올린다.
EXCLUDE = {'shortcuts/Save-to-Shelf-Cloud.shortcut', 'shortcuts/save-to-shelf-cloud-unsigned.shortcut'}
pairs = []
for line in redact.read_text().splitlines():
    if line.strip() and not line.lstrip().startswith('#') and '=>' in line:
        real, mask = (x.strip() for x in line.split('=>', 1))
        pairs.append((real, mask))
files = [f for f in subprocess.run(['git', 'ls-files', '-z'], cwd=src, capture_output=True, check=True).stdout.decode().split('\0') if f and f not in EXCLUDE]
keep = set(files)
for p in list(mirror.rglob('*')):
    rel = p.relative_to(mirror)
    if rel.parts[0] != '.git' and p.is_file() and str(rel) not in keep:
        p.unlink()
generic = [
    r'(?<![0-9])[0-9]{12}(?![0-9])',                       # AWS 계정 ID 모양
    r'\b(AKIA|ASIA)[0-9A-Z]{16}\b',                         # AWS 액세스 키
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    r'''(?i)(aws_secret_access_key|secretaccesskey)["']?\s*[:=]\s*["']?[A-Za-z0-9/+]{40}''',
    r'[a-z0-9]{20,}\.lambda-url\.[a-z0-9-]+\.on\.aws',      # Lambda Function URL
    r'\b[a-z0-9]{13,14}\.cloudfront\.net\b',                # CloudFront 기본 주소
    r'\bE[0-9A-Z]{12,13}\b',                                # CloudFront 배포·OAC ID
    r'\b[0-9a-f]{64}\b',                                    # 키 해시 등
]
leaks = []
for name in files:
    dst = mirror / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / name, dst)
    data = dst.read_bytes()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        text = None
    if text is not None:
        for real, mask in pairs:
            text = text.replace(real, mask)
        if text.encode('utf-8') != data:
            dst.write_text(text)
        data = text.encode('utf-8')
        for pat in generic:
            leaks += [f'{name}: {m.group(0)[:12]}…' for m in re.finditer(pat, text)]
    for real, _ in pairs:
        if real.encode('utf-8') in data:
            leaks.append(f'{name}: {real[:6]}… ({"바이너리" if text is None else "텍스트"})')
if leaks:
    print('중단: 공개 미러에 넣으면 안 되는 값이 남아 있음 (커밋·push 안 함)')
    print('\n'.join(sorted(set(leaks))))
    print('실제 값이면 data/mirror-redact.txt 에 추가하거나 파일을 EXCLUDE 에 넣을 것')
    sys.exit(1)
print(f'검사 통과: 파일 {len(files)}개, 가린 값 종류 {len(pairs)}개, 제외 파일 {len(EXCLUDE)}개')
PY

git -C "$MIRROR" add -A
echo "== 미러에서 바뀔 파일"
git -C "$MIRROR" diff --cached --name-status
if [ "$MODE" = --check ]; then
  restore; echo "미리보기만 함 — push 안 함. 사용자 확인 후 --push"; exit 0
fi
if git -C "$MIRROR" diff --cached --quiet; then echo "mirror: 변경 없음"; exit 0; fi
git -C "$MIRROR" commit -q -m "$(git -C "$SRC" log -1 --format=%s)"
git -C "$MIRROR" push -q origin main
echo "mirror push 완료: $(git -C "$MIRROR" log -1 --oneline)"
