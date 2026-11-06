"""서랍 웹 로그인 비밀번호를 설정한다. 원문은 어디에도 저장하지 않고 해시만 API Lambda 환경변수에 넣는다.
사용: python3 cloud/set_password.py [--logout-all]
--logout-all: 입장권 서명 비밀값도 새로 만들어 잠금 함수까지 다시 발행한다(모든 기기 로그아웃, CloudFront Function 권한 필요)."""
import getpass
import hashlib
import json
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_config as cfg  # noqa: E402

ROUNDS = 600_000
MIN_LENGTH = 8


def make_hash(password, salt=None, rounds=ROUNDS):
    salt = salt or secrets.token_bytes(16)
    return f'pbkdf2_sha256${rounds}${salt.hex()}${hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds).hex()}'


def aws(*args, query=None):
    cmd = ['aws', 'lambda', *args, '--function-name', cfg.API_FUNCTION, *cfg.AWS_ARGS, '--output', 'json']
    if query:
        cmd += ['--query', query]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('실패: ' + (r.stderr or r.stdout))
    return json.loads(r.stdout) if r.stdout.strip() else None


def main():
    logout_all = '--logout-all' in sys.argv
    password = getpass.getpass('새 비밀번호: ')
    if len(password) < MIN_LENGTH:
        raise SystemExit(f'{MIN_LENGTH}자 이상으로 정해 주세요.')
    if password != getpass.getpass('한 번 더: '):
        raise SystemExit('두 번 입력한 값이 다릅니다.')
    env = aws('get-function-configuration', query='Environment.Variables') or {}
    env['PASSWORD_HASH'] = make_hash(password)
    if logout_all or not env.get('SESSION_SECRET'):
        env['SESSION_SECRET'] = secrets.token_urlsafe(32)
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump({'Variables': env}, f)
    try:
        aws('update-function-configuration', '--environment', f'file://{f.name}', query='LastUpdateStatus')
    finally:
        Path(f.name).unlink()
    subprocess.run(['aws', 'lambda', 'wait', 'function-updated', '--function-name', cfg.API_FUNCTION, *cfg.AWS_ARGS], check=True)
    print('비밀번호를 저장했습니다.')
    if logout_all:
        subprocess.run([sys.executable, str(Path(__file__).with_name('deploy_gate.py'))], check=True)
        print('모든 기기를 로그아웃했습니다.')


if __name__ == '__main__':
    main()
