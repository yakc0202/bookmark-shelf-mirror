# 인프라 참고 (CloudFormation 밖에서 관리)

2026-10-02부터 Lambda/IAM Role/Function URL은 CloudFormation으로 관리하지
않습니다. `cloud/api.py`를 고칠 때마다 전체 스택을 재배포하는 게 번거롭고,
실제로 거의 안 바뀌는 리소스(권한, URL 설정)까지 매번 재평가할 이유가
없어서 `DeletionPolicy: Retain`으로 스택에서만 떼어냈습니다 (리소스 자체는
삭제되지 않고 그대로 살아있음).

## HTTPS (CloudFront)
- ACM 인증서(us-east-1): `arn:aws:acm:us-east-1:<account-id>:certificate/39c1879e-0312-4562-a33a-c5faf3c18380`
- CloudFront 배포 ID: `<CLOUDFRONT_DISTRIBUTION_ID>`, 도메인: `<CLOUDFRONT_DEFAULT_DOMAIN>`
- DNS: `<SITE_DOMAIN>` CNAME → `<CLOUDFRONT_DEFAULT_DOMAIN>` (<DNS_REGISTRAR>에서 관리. S3 엔드포인트로 직접 연결하면 안 됨 — 아래 origin 설명 참고)
- Origin: S3 **website** 엔드포인트(`<SITE_DOMAIN>.s3-website.<AWS_REGION>.amazonaws.com`), Origin Protocol Policy `http-only`, 캐시 정책 CachingDisabled(배포 즉시 반영되게 일부러 캐시 끔)
  - ⚠️ S3 **REST** 엔드포인트(`....s3.<AWS_REGION>.amazonaws.com`)를 HTTPS-only origin으로 쓰면 안 됨: 버킷명에 점이 2개(`<SITE_DOMAIN>`) 들어 있어서 AWS 와일드카드 인증서(`*.s3.<AWS_REGION>.amazonaws.com`, 레이블 1개만 매칭)와 호스트네임이 안 맞아 TLS 핸드셰이크가 실패하고 CloudFront가 502를 반환함(2026-10-03 발생·수정). website 엔드포인트는 HTTPS 자체를 지원 안 하므로 origin 구간은 http-only로 두고, 뷰어 쪽 HTTPS는 ACM 인증서가 그대로 처리.
- `index.html` 배포 후 반영이 늦어 보이면: 캐시를 꺼놨으니 보통 즉시 반영됨. 그래도 이상하면
  `aws cloudfront create-invalidation --distribution-id <CLOUDFRONT_DISTRIBUTION_ID> --paths "/*" --profile <AWS_PROFILE> --region us-east-1`

## 사진(`photos/*`) 전용 CDN 캐싱 (2026-10-04 추가)

사진 북마크가 S3 presigned URL(만료 시간 있음)을 쓰다 보니 "오래 열어두면 사진이 깨짐",
"매 요청마다 수백 장을 다시 서명하느라 느림" 문제가 있었음. 사진은 한 번 올라가면
내용이 절대 안 바뀌는 불변 데이터(키가 무작위 32자 hex)라서, presigned URL 대신
CloudFront로 영구 캐싱하는 쪽으로 바꿈.

- 같은 CloudFront 배포(`<CLOUDFRONT_DISTRIBUTION_ID>`)에 `photos/*` 경로 전용 오리진·캐시 동작을 추가:
  - 오리진: S3 **REST** 엔드포인트(`<SITE_DOMAIN>.s3.<AWS_REGION>.amazonaws.com`)를
    **네이티브 S3 오리진 타입**(`S3OriginConfig` + Origin Access Control)으로 연결.
    ⚠️ 위에서 경고한 "버킷명에 점 2개라 REST 엔드포인트를 HTTPS origin으로 못 씀" 문제는
    **커스텀 오리진(`CustomOriginConfig`)으로 쓸 때만** 해당하는 얘기였음. 네이티브 S3
    오리진 타입(OAC 사용)은 CloudFront가 내부적으로 다르게 처리해서 점 2개짜리 버킷명도
    문제없이 동작함(2026-10-04 실제로 확인).
  - Origin Access Control: `<PHOTOS_OAC_NAME>` (ID `<CLOUDFRONT_OAC_ID>`) — 버킷을 공개
    전환하지 않고 CloudFront만 `photos/*`를 읽을 수 있게 버킷 정책에 조건부(`AWS:SourceArn`
    이 배포로 한정) 허용 추가.
  - 캐시 정책: AWS 관리형 `Managed-CachingOptimized`(`658327ea-f89d-4fab-a63d-7e88639e58f6`).
  - S3 오브젝트 자체의 `Cache-Control` 헤더를 `public, max-age=31536000, immutable`로 설정
    (`/api/photos`, `/api/attach-photo` 업로드 시점). 기존에 이미 올라가 있던 사진 209장은
    `aws s3api copy-object --metadata-directive REPLACE`로 한 번에 메타데이터만 갱신해서
    소급 적용함(내용은 그대로, 헤더만 바뀜).
- `cloud/api.py`의 `photo_url(key)`는 이제 presigned URL이 아니라 그냥
  `https://<SITE_DOMAIN>/{key}` 고정 주소를 반환함 — 서명도, 만료도, 재서명 캐시도
  필요 없어짐(이전에 추가했던 서명 URL 메모리 캐시는 삭제).
- **보안 트레이드오프(의도된 설계)**: 사진 주소는 이제 영구적이고, 주소를 아는 사람은
  누구나 볼 수 있음(=무작위 키 추측 불가능성에만 의존). 기존 공유 링크(`/s/토큰`) 기능과
  정확히 같은 신뢰 모델이라 이 개인용 앱에서는 받아들이기로 함. 더 엄격하게 하려면
  CloudFront 서명 URL(전용 키쌍/키그룹 + Lambda에 RSA 서명 코드/의존성 추가 필요)로
  바꿀 수 있지만, 설정·유지보수 부담이 커서 이번엔 안 함.
- 이 작업에 필요했던 임시 IAM 권한(`cloudfront:CreateOriginAccessControl` 등 2개 액션 +
  이 버킷 한정 `s3:GetBucketPolicy`/`PutBucketPolicy`)은 콘솔 인라인 정책(`<TEMP_IAM_POLICY_NAME>`)
  으로 붙였던 것 — 작업이 끝났으니 최소 권한 유지를 위해 콘솔에서 제거 권장(더 이상 쓸 일 없음,
  OAC/버킷 정책은 한 번 만들고 나면 재수정할 필요가 없음).

## 현재 살아있는 리소스
- Lambda 함수: `<API_LAMBDA_NAME>` (<AWS_REGION>, python3.13, handler `index.handler`)
- Function URL: `https://<API_FUNCTION_URL_ID>.lambda-url.<AWS_REGION>.on.aws`
- IAM Role: `<API_STACK_NAME>-ApiRole-*` (정확한 이름은 `aws lambda get-function --function-name <API_LAMBDA_NAME> --query Configuration.Role`로 확인)
- 환경변수: `DATA_BUCKET=<SITE_DOMAIN>`, `CLIENT_TOKEN_HASH`, `WORKER_TOKEN_HASH` (평소엔 안 바뀜)

## 서버리스 worker (2026-10-03 추가, 맥 로컬 워커 대체)

Codex/Claude Code CLI로 AI 분류를 돌리던 로컬 맥 워커(`cloud/worker.py`)를
Lambda 컨테이너로도 옮겼습니다. 맥을 안 켜놔도 자동 정리되게 하는 게 목적.

- Lambda 함수: `<WORKER_LAMBDA_NAME>` (컨테이너 이미지, arm64, 메모리 1024MB, 타임아웃 600초)
- 이미지: ECR `<WORKER_LAMBDA_NAME>`, `cloud/Dockerfile.worker`로 빌드
  (Python 3.13 베이스 + Node 22 직접 설치 + `@openai/codex`/`@anthropic-ai/claude-code` npm 설치)
- 핸들러: `cloud/worker_handler.py` — `cloud/worker.py`와 같은 claim→organize/extract→complete
  로직이지만 무한 루프 대신 호출당 최대 20건 처리 후 종료(Lambda는 호출 단위로 과금/제한됨)
- IAM Role: `<WORKER_ROLE_NAME>` — `secretsmanager:GetSecretValue`(아래 시크릿만) +
  `AWSLambdaBasicExecutionRole`만 가짐. S3 권한은 없음(HTTP API를 통해서만 데이터에 접근)
- 자격증명: Secrets Manager `<WORKER_SECRET_NAME>`에 `{codex_auth, claude_token}` JSON으로
  저장. Lambda 콜드스타트 시 `/tmp/.codex/auth.json`에 쓰고 `CLAUDE_CODE_OAUTH_TOKEN` 환경변수로
  주입(Lambda는 `/tmp` 외 쓰기 불가이므로 `SHELF_DATA_DIR=/tmp/data`로 `server.py`의 데이터 경로도 바꿈).
  Codex는 전용 두 번째 ChatGPT 계정(`~/.codex2`) 세션을 복사한 것, Claude는 개인 계정의
  `claude setup-token` 헤드리스 토큰.
- 트리거: `cloud/api.py`가 `/api/items`, `/api/photos`, `/api/memos/extract` 처리 직후
  `LAMBDA_CLIENT.invoke(FunctionName='<WORKER_LAMBDA_NAME>', InvocationType='Event', ...)`로
  비동기 호출(실패해도 본 요청에는 영향 없음, try/except로 무시). api Lambda 역할에
  `lambda:InvokeFunction`을 worker 함수로 한정해서 추가해둠.
- 안전망: EventBridge 규칙 `<WORKER_SCHEDULE_NAME>` (`rate(1 hour)`)이 1시간마다
  워커를 깨움 — `ai_waiting`(1시간 재시도) 항목이 새 글 공유 없이도 처리되게, 그리고 invoke
  실패나 워커 크래시로 못 간 작업을 주워가게 하는 용도. 메인 트리거는 위 invoke이고
  이건 어디까지나 보험(비용은 거의 $0 — 프리티어 안에서 다 소화됨).
- 자격증명 재발급 시: 새 토큰/auth.json 준비 후
  `aws secretsmanager put-secret-value --secret-id <WORKER_SECRET_NAME> --secret-string file://...`
  로 교체. Lambda 재배포는 필요 없음(다음 콜드스타트부터 자동 반영).
- 로컬 맥 워커(`cloud/worker.py`)는 당장은 그대로 같이 둠(둘 다 같은 claim/lease를 쓰니
  동시에 돌아도 안전, 중복 처리는 안 됨). 완전히 끌지는 사용자 판단에 맡김.

## `bookmark` IAM 사용자 권한 (2026-10-03 최소 권한으로 정리)

처음엔 설정 과정에서 하나씩 막힐 때마다 AWS 관리형 FullAccess 정책을 10개까지
붙였었는데(Lambda/S3/CloudFront/ACM/IAM/ECR×2/CloudFormation/EventBridge/
SecretsManager), 전부 떼고 위 9개 리소스(2 Lambda, 1 S3 버킷, 1 CloudFront
배포, 1 ECR 리포, 1 Secret, 1 EventBridge 규칙, 2 로그 그룹)에만 정확히 맞춘
고객관리형 정책 하나(`<IAM_POLICY_NAME>`, IAM 콘솔에서 ARN
`arn:aws:iam::<account-id>:policy/<IAM_POLICY_NAME>`로 확인 가능)로
교체했습니다. 인라인 정책 용량 한도(2048바이트)를 넘어서 managed policy로 만듦.

**포함된 것**: 이 2개 Lambda 함수의 조회/코드·설정 업데이트/invoke, 이 S3
버킷의 object 읽기·쓰기·목록, 이 CloudFront 배포 조회·업데이트·무효화, 이
Secret 읽기·쓰기, 이 ECR 리포 push/pull(+ 계정 전체에 걸리는
`ecr:GetAuthorizationToken`은 ECR 설계상 리소스 범위 지정이 안 돼서 예외),
이 EventBridge 규칙 조회·업데이트, 이 2개 로그 그룹 보존기간 설정.

**뺀 것(= 앞으로 안 되는 것)**: `iam:*` 전부(자기 자신에게 권한을 추가하는
것조차 안 됨 — 의도된 것), `cloudformation:*`(이 프로젝트는 안 씀),
`acm:*`(인증서 이미 발급됨, DNS 검증 방식이라 자동 갱신되고 평소 건드릴 일
없음), 리소스 생성/삭제 계열(`lambda:CreateFunction`, `ecr:CreateRepository`,
`s3:CreateBucket` 등 — 전부 최초 1회성 설정 작업).

**앞으로 새 권한이 필요하면**: `bookmark` 프로필 자체로는 더 이상 자기
권한을 못 늘립니다. AWS 콘솔에 계정 소유자로 로그인해서 IAM에서
`<IAM_POLICY_NAME>` 정책을 수정하거나 임시로 다른 정책을 붙여야 합니다.
작업 끝나면 다시 빼는 걸 권장(최소 권한 유지).

## 평소 코드 배포 (`cloud/api.py` 수정 시)
```
python3 cloud/deploy.py
```
`cloud/api.py`를 zip으로 묶어 `aws lambda update-function-code`로 바로 올립니다.
CloudFormation을 거치지 않습니다.

## 만약 Lambda/Role/URL이 통째로 사라졌다면 (재해 복구)
이 리소스들을 처음부터 다시 만들어야 하는 경우, 과거
`cloud/build.py`(현재는 삭제됨, git log에서 `084dc3e` 이전 커밋 참고)에
있던 CloudFormation 정의를 참고하세요:

- IAM Role: Lambda가 assume, 정책은 `s3:GetObject`/`s3:PutObject`를
  `<SITE_DOMAIN>/data/cards.json`, `<SITE_DOMAIN>/photos/*`에만,
  `s3:ListBucket`을 `data/cards.json` prefix 조건으로만 허용
- Lambda 함수: Runtime `python3.13`, Handler `index.handler`, Memory 256MB,
  Timeout 25초, 코드는 `cloud/api.py` 내용 그대로
- Function URL: `AuthType: NONE` (토큰은 애플리케이션 레벨에서 자체 검증),
  CORS는 `http://<SITE_DOMAIN>`, S3 웹사이트 엔드포인트, `localhost:8787` 허용
- Lambda Permission 2개: Function URL 호출 허용 + 함수 직접 호출 허용(둘 다 Principal `*`,
  Function URL 경유로 제한)

새로 만든 뒤에는 `cloud/deploy.py`의 함수 이름/Function URL을 갱신해야 합니다.

## 사이트 잠금 (CloudFront Function, 2026-10-07)

- 함수 `<GATE_FUNCTION_NAME>`(cloudfront-js-2.0), 기본 동작(`photos/*` 제외) viewer-request에 연결. 코드 `cloud/site-gate.js`.
- `shelf_key` 쿠키의 SHA-256이 API Lambda의 `CLIENT_TOKEN_HASH`와 같을 때만 통과. 아니면 접속 키 입력 화면(200)을 직접 응답.
- 공개 경로: `/apple-touch-icon.png`, `/apple-touch-icon-precomposed.png`, `/favicon.ico`, `/shortcuts/*`. `photos/*`는 별도 동작이라 함수 영향 없음.
- `<SITE_DOMAIN>`가 아닌 호스트(cloudfront.net 기본 주소 등)는 301로 이동.
- 배포: `python3 cloud/deploy_gate.py` — 가짜 키로 TestFunction 시험 후 실제 해시로 발행·연결. 해시는 저장소에 넣지 않음.
- **접속 키를 바꾸면** API Lambda의 `CLIENT_TOKEN_HASH`를 바꾼 뒤 이 스크립트를 다시 실행해야 함(안 하면 새 키로 사이트가 안 열림).
- 되돌리기: CloudFront 콘솔 → 배포 → 동작 → 기본값 → 함수 연결 viewer-request를 "연결 없음"으로.
- 쿠키 `shelf_key`: 1년 유지(Secure, SameSite=Lax). 앱(`static/index.html`의 `syncKeyCookie`)이 시작·로그인 때 갱신하고, 입력 화면은 기기에 저장된 키(localStorage `shelf-key`)로 자동 재진입.
- 함수 관리 권한은 상시 권한이 아님. 키를 바꿀 때 `bookmark` 사용자에 CloudFront Function 권한(Create/Update/Publish/Describe/Get/TestFunction)을 잠깐 붙이고 스크립트 실행.

## 버킷 공개 파일과 아이콘 (2026-10-07 기준)

- 버킷 정책상 누구나 읽을 수 있는 파일: `index.html`, `config.js`, `shortcuts/Save-to-Shelf.shortcut`, `apple-touch-icon.png`, `apple-touch-icon-precomposed.png`, `favicon.ico`. 그 외 루트 경로는 403(`data/` 포함). 새 파일을 공개하려면 버킷 정책 수정 필요(`bookmark` 사용자에는 상시 권한 없음).
- 사이트 잠금 이후 `index.html`, `config.js`는 키 쿠키가 있어야 열림. 위 공개 파일 중 아이콘 3종·단축어만 키 없이 열림.
- `photos/*`는 버킷 정책이 아니라 CloudFront OAC로만 공개 → 새 공개 이미지가 필요하면 `photos/` 아래에 올리면 권한 없이 됨.
- 탭 파비콘: `photos/site-favicon-v1.png`(투명 배경 128px). `photos/`는 1년 불변 캐시라 아이콘을 바꿀 땐 같은 이름에 덮어쓰지 말고 `v2`처럼 새 이름으로 올린 뒤 `index.html`과 `cloud/site-gate.js`의 링크를 함께 바꿀 것.
- 홈 화면·즐겨찾기 아이콘: `apple-touch-icon.png`(180px, 미색 배경 — iOS가 투명 배경을 검게 칠하므로 배경 유지).

## worker 코드 배포 (Docker 없이, 2026-10-07)

- `server.py`·`ai_runner.py`·`cloud/worker_handler.py`만 바뀐 경우: `python3 cloud/deploy_worker.py`. 지금 worker Lambda가 쓰는 이미지 위에 이 세 파일만 담은 층을 얹은 새 이미지를 `aws ecr` API(batch-get-image, 레이어 업로드, put-image)로 올리고 Lambda를 그 이미지로 바꾼다. 태그 `patch-YYYYMMDD-HHMMSS`와 `latest`를 함께 붙임.
- 스크립트가 처음에 출력하는 "현재(되돌릴 때 쓸) 이미지" 주소로 `aws lambda update-function-code --image-uri <주소>`를 하면 되돌릴 수 있음.
- Python 패키지·Node·Codex/Claude CLI 버전을 바꾸는 등 `cloud/Dockerfile.worker` 자체가 바뀌면 Docker로 전체 재빌드가 필요(이 맥에는 2026-10-07 기준 Docker 없음).
- 배포 뒤 확인: `aws lambda invoke --function-name <worker> --invocation-type RequestResponse`로 한 번 실행해 오류 없이 `{"processed": N}`이 나오는지 본다.
- 첫 사용(2026-10-07): 모음 주제 추론 반영. 이전 이미지 `sha256:6289f55a…`, 새 이미지 `sha256:9e19700b…`(태그 `patch-20261007-145550`).
