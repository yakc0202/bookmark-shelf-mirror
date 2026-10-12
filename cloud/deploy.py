"""Fast path for shipping cloud/api.py changes: zips it as index.py and
pushes straight to the Lambda function via update-function-code. No
CloudFormation involved (see cloud/INFRA.md for why).

함수 이름·프로필·리전과 사이트 주소는 cloud/site.json에서 읽는다. 코드를 올린 뒤
Lambda 환경변수 SITE_URL(사진 공개 주소의 기준)이 site.json의 도메인과 다르면 그 값만 고친다
(다른 환경변수는 그대로 두고, 값은 화면에 출력하지 않는다)."""
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_config as cfg  # noqa: E402

ROOT = cfg.ROOT
FUNCTION_NAME = cfg.API_FUNCTION


def aws(*args, query=None):
    cmd = ['aws', 'lambda', *args, '--function-name', FUNCTION_NAME, *cfg.AWS_ARGS, '--output', 'json']
    if query:
        cmd += ['--query', query]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('배포 실패: ' + (r.stderr or r.stdout))
    return json.loads(r.stdout) if r.stdout.strip() else None


buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', (ROOT / 'cloud/api.py').read_text())
zip_path = ROOT / 'data/cloud-build/api.zip'
zip_path.parent.mkdir(parents=True, exist_ok=True)
zip_path.write_bytes(buf.getvalue())



def wait_updated():
    subprocess.run(['aws', 'lambda', 'wait', 'function-updated', '--function-name', FUNCTION_NAME, *cfg.AWS_ARGS], check=True)


print('배포 완료:', aws('update-function-code', '--zip-file', f'fileb://{zip_path}', query='LastUpdateStatus'))
wait_updated()

env = aws('get-function-configuration', query='Environment.Variables') or {}
if env.get('SITE_URL') != cfg.SITE_URL:
    env['SITE_URL'] = cfg.SITE_URL
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump({'Variables': env}, f)
    try:
        aws('update-function-configuration', '--environment', f'file://{f.name}', query='LastUpdateStatus')
    finally:
        Path(f.name).unlink()
    wait_updated()
    print('SITE_URL 환경변수를', cfg.SITE_URL, '로 맞춤')
else:
    print('SITE_URL 환경변수 확인:', cfg.SITE_URL)
