# 서랍(bookmark-shelf) 작업 규칙

Claude Code, Codex 등 이 저장소에서 일하는 모든 에이전트에 적용한다. 규칙은 한 줄로 쓰고, 날짜·사건 경위는 `REQUESTS.md`에만 적는다.

## 세션 시작·끝

- 세션을 시작하면 [`SYNC.md`](SYNC.md)(지금 상태 요약)를 먼저 읽고, 작업을 마치면 바뀐 상태(진행 중·사용자 몫·최근 결정·맥별 설정)를 갱신해 같은 커밋에 넣는다.

## 요청 기록

- 사용자의 모든 요청(질문·버그·기능)과 처리 상태를 [`REQUESTS.md`](REQUESTS.md)에 적는다. 형식은 그 파일 상단 규칙을 따른다.
- 다른 세션이 기록만 보고 이어서 일할 수 있게 다음을 빠짐없이 적는다: 바뀐 것(파일·함수·API 경로·설정·새 리소스), 사용자에게 말한 주의·다음 할 일, 사용자가 직접 할 일, 임시 권한(범위·만료·지워도 되는지), 막힌 단계와 이유, 진단 근거.
- 막힌 것은 "완료"로 적지 않는다. 상태가 바뀌면 앞 항목도 고쳐 낡은 상태를 남기지 않는다.
- 인프라 변경·운영 방법은 `cloud/INFRA.md`, 작업 규칙은 이 파일에 적는다.
- 기록은 변경과 같은 커밋에 넣고, 응답을 끝내기 전에 대화 내용과 맞는지 확인한다.
- 기능 개선이 아닌 운영 기록(재처리·복구, 동작 확인, 배포·푸시 확인, 권한, 로컬 정리, 질의응답·진단, 규칙)에는 `<!-- mirror:skip -->`를 붙인다. 항목 전체면 `###` 제목 줄 끝, 일부면 그 줄 끝.

## 데이터 보정

- 분류 규칙·폴더 로직을 바꾸면 기존 `data/cards.json`에서 새 규칙에 안 맞는 항목을 찾아 묻지 않고 고친다. 가능하면 `normalize_folder()` 같은 코드 규칙으로 기계적으로 고친다(AI 재호출 없이).

## 컨테이너 빌드(Colima)

- Colima는 `cloud/Dockerfile.worker` 전체 재빌드(패키지·Node·Codex/Claude CLI 변경)할 때만 켜고, 평소에는 꺼 둔다. 전체 빌드는 Colima가 있는 MacBook Air에서만 한다.
- `server.py`·`ai_runner.py`·`cloud/worker_handler.py`만 바뀌면 `python3 cloud/deploy_worker.py`로 배포한다(Docker 불필요).
- VM이 없으면 `colima start --cpu 2 --memory 4 --arch aarch64 --vm-type vz --runtime docker`로 만든다. 긴 다운로드 출력은 `docker build -q`로 줄인다.
- 순서: `colima start` → 빌드·ECR 푸시·Lambda 교체 → `aws lambda invoke`로 확인 → `colima stop`. 실패해도 끝낼 때 `colima stop`, 끝나기 전 `colima status`로 확인한다.
- 이미지 정리는 켜진 상태에서 `docker image prune -a`. 맥 디스크까지 비우려면 `colima delete -f --data`.

## 변경 후 배포·푸시

코드를 바꾸면 묻지 않고 아래까지 마친다. 하나라도 못 했으면 "완료"라고 하지 말고 남은 것을 기록·보고한다.

1. 배포: 화면(`static/index.html`)은 S3 업로드, `cloud/api.py`는 `python3 cloud/deploy.py`, 정리 작업 코드는 `python3 cloud/deploy_worker.py`(명령은 `SETUP.md` "배포").
2. `git push origin main`. force-push 금지.
3. 공개 미러는 `./mirror-push.sh`로만 올린다(대상 `bookmark-shelf-mirror`, 작업 폴더 `~/Documents/Codex/bookmark-shelf-mirror`).
   - 먼저 `./mirror-push.sh`로 미리보기를 보여 주고, 사용자가 승인하면 `./mirror-push.sh --push`.
   - 공개 미러에는 보안 관련 값을 하나도 넣지 않는다: 계정·리소스 ID, 엔드포인트, 키, 해시, 도메인, 리전, AWS 리소스 이름, IAM 사용자·프로필, GitHub 아이디, DNS 업체 이름. 실제 값 목록은 저장소 맨 위 `mirror-redact.txt`(비공개 저장소에만 커밋, `mirror-push.sh`가 미러에서 제외)에 `실제값 => <표시>`로 적는다(긴 값 먼저). 다른 맥에서도 `git pull`만 하면 같은 규칙으로 미러 push 가능.
   - 가릴 수 없는 파일은 스크립트의 `EXCLUDE`로 미러에서 뺀다(API 주소가 든 단축어, `docs/서랍-구성-안내.md`).
   - 자동 모드에서는 허용 규칙 `Bash(./mirror-push.sh)`, `Bash(./mirror-push.sh *)`가 있어야 실행된다. 막히면 막혔다고 기록·보고한다.
