"""Fast path for shipping cloud/api.py changes: zips it as index.py and
pushes straight to the Lambda function via update-function-code. No
CloudFormation involved (see cloud/INFRA.md for why)."""
import io
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTION_NAME = '<API_LAMBDA_NAME>'

buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('index.py', (ROOT / 'cloud/api.py').read_text())
zip_path = ROOT / 'data/cloud-build/api.zip'
zip_path.parent.mkdir(parents=True, exist_ok=True)
zip_path.write_bytes(buf.getvalue())

result = subprocess.run(
    ['aws', 'lambda', 'update-function-code', '--function-name', FUNCTION_NAME,
     '--zip-file', f'fileb://{zip_path}', '--profile', '<AWS_PROFILE>', '--region', '<AWS_REGION>',
     '--query', 'LastUpdateStatus', '--output', 'text'],
    capture_output=True, text=True)
if result.returncode != 0:
    raise SystemExit('배포 실패: ' + (result.stderr or result.stdout))
print('배포 완료:', result.stdout.strip())
