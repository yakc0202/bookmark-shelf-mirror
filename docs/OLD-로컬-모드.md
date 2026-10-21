# OLD: 로컬 전용 모드 (초기 프로토타입, 더 이상 사용하지 않음)

아래는 S3/Lambda로 옮기기 전, 맥 로컬 서버 + Tailscale만으로 운영하던 초기 버전의 안내입니다.
`server.py`를 직접 실행하는 이 모드는 코드에 남아 있지만 현재 운영 방식이 아니므로 새로 시작한다면 위 "빠른 사용법"을 따르세요.

## 실행

`start.command`를 실행하고 http://localhost:8787 에 접속합니다.
접속 키는 `data/token` 파일에 있으며 브라우저에 한 번 입력합니다.
Codex CLI에 로그인되어 있어야 자동 분류가 작동합니다.
카드와 대기열은 `data/shelf.db`에 저장됩니다.

## 외부 공유 연결 (Tailscale)

1. https://tailscale.com/download 에서 맥·아이폰용 Tailscale을 설치합니다.
2. 양쪽에서 같은 계정으로 로그인하고 연결합니다.
3. 맥의 Tailscale IP로 `http://100.x.x.x:8787`를 아이폰 Safari에서 엽니다.
4. 접속 키로 연결한 뒤 웹 화면 상단의 '연결 안내'대로 단축어를 만듭니다.
5. 아이폰 Wi-Fi를 끄고 셀룰러에서 링크를 공유해 실제 외부 연결을 확인합니다.

수신 주소: `http://맥의-Tailscale-IP:8787/api/items`
메서드: POST / JSON 본문: `{"text":"단축어 입력의 텍스트"}`
헤더: `Authorization: Bearer 접속키`

이 HTTP 주소는 개인 Tailscale 연결용입니다. 공유기 포트 개방이나 공개 터널로 노출하지 마세요.
서버 실행 중 caffeinate가 유휴 잠자기를 막습니다. 덮개 닫기·종료·네트워크 단절 때는 이용할 수 없습니다.
