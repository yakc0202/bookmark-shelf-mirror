"""worker Lambda의 AI 로그인 정보(Codex auth.json, Claude 토큰)를 SSM Parameter Store에 넣는다.
값은 화면에 출력하지 않고, 명령줄 인자 대신 권한 600 임시 파일로 AWS CLI에 넘긴다.

두 값을 따로 넣는 이유: SSM 무료(Standard) 파라미터는 4KB까지라 둘을 합치면 넘는다.
등급은 Intelligent-Tiering — 4KB 안이면 무료, 넘으면 그 파라미터만 Advanced(월 $0.05)로 자동 전환.

사용:
  python3 cloud/worker_auth.py login-codex   # 이 맥의 Codex와 섞이지 않는 따로 된 로그인을 새로 만들어 Codex 값만 교체(브라우저 로그인)
  python3 cloud/worker_auth.py set --codex ~/.codex2/auth.json --claude-token-file <토큰 파일>
  python3 cloud/worker_auth.py migrate     # 예전 Secrets Manager 값을 그대로 복사(1회용)
  python3 cloud/worker_auth.py status      # 이름·버전·바뀐 시각만 표시(값은 안 읽음)
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_config as cfg  # noqa: E402

PREFIX = '/<WORKER_SECRET_NAME>/'
NAMES = {'codex': PREFIX + 'codex-auth', 'claude': PREFIX + 'claude-token'}
OLD_SECRET = '<WORKER_SECRET_NAME>'


def aws(*args):
    r = subprocess.run(['aws', *args, *cfg.AWS_ARGS, '--output', 'json'], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('AWS 오류: ' + (r.stderr.strip() or r.stdout.strip()))
    return json.loads(r.stdout) if r.stdout.strip() else {}


def put(name, value):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'in.json'
        path.touch(mode=0o600)
        path.write_text(json.dumps({'Name': name, 'Value': value, 'Type': 'SecureString',
                                    'Tier': 'Intelligent-Tiering', 'Overwrite': True}))
        out = aws('ssm', 'put-parameter', '--cli-input-json', f'file://{path}')
    print(f'{name}: 버전 {out.get("Version")}, 등급 {out.get("Tier")} ({len(value.encode())}바이트)')


def put_both(codex_auth, claude_token):
    if not isinstance(codex_auth, dict) or 'tokens' not in codex_auth:
        raise SystemExit('Codex auth.json 형식이 아님(tokens 없음)')
    if not claude_token.strip():
        raise SystemExit('Claude 토큰이 비어 있음')
    put(NAMES['codex'], json.dumps(codex_auth, separators=(',', ':')))
    put(NAMES['claude'], claude_token.strip())


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('set')
    s.add_argument('--codex', required=True)
    s.add_argument('--claude-token-file', required=True)
    sub.add_parser('login-codex')
    sub.add_parser('migrate')
    sub.add_parser('status')
    a = ap.parse_args()
    if a.cmd == 'set':
        put_both(json.loads(Path(os.path.expanduser(a.codex)).read_text()),
                 Path(os.path.expanduser(a.claude_token_file)).read_text())
    elif a.cmd == 'login-codex':
        # 맥의 ~/.codex 로그인을 그대로 쓰면 맥 Codex가 토큰을 갱신할 때 worker 쪽이 깨진다 → 임시 폴더에 따로 로그인.
        with tempfile.TemporaryDirectory(prefix='codex-worker-') as home:
            env = {**os.environ, 'CODEX_HOME': home}
            # 키체인 말고 auth.json 파일로 저장하게
            if subprocess.run(['codex', 'login', '-c', 'cli_auth_credentials_store="file"'], env=env).returncode != 0:
                raise SystemExit('codex login 실패')
            auth = json.loads((Path(home) / 'auth.json').read_text())
            if not isinstance(auth, dict) or 'tokens' not in auth:
                raise SystemExit('Codex auth.json 형식이 아님(tokens 없음)')
            put(NAMES['codex'], json.dumps(auth, separators=(',', ':')))
        print('임시 로그인 폴더는 지웠습니다. worker는 다음 실행부터 새 로그인을 씁니다.')
    elif a.cmd == 'migrate':
        secret = json.loads(aws('secretsmanager', 'get-secret-value', '--secret-id', OLD_SECRET)['SecretString'])
        put_both(secret['codex_auth'], secret['claude_token'])
    else:
        out = aws('ssm', 'get-parameters', '--names', *NAMES.values(), '--no-with-decryption',
                  '--query', '{ok:Parameters[].[Name,Version,LastModifiedDate],missing:InvalidParameters}')
        for name, version, changed in out['ok']:
            print(name, '버전', version, changed)
        for name in out['missing']:
            print(name, '없음')


if __name__ == '__main__':
    main()
