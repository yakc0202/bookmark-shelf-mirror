"""worker Lambda(컨테이너 이미지)에 server.py·ai_runner.py·cloud/worker_handler.py 변경을 Docker 없이 배포한다.
지금 Lambda가 실행 중인 이미지 위에 이 세 파일만 담은 층(layer)을 하나 얹은 새 이미지를 ECR에 올리고
(`aws ecr` API만 사용), worker Lambda를 그 이미지로 바꾼다. 패키지·Node·CLI를 바꿀 때는
cloud/Dockerfile.worker로 전체 재빌드가 필요하다(이 스크립트는 파이썬 파일만 교체).
사용: python3 cloud/deploy_worker.py
되돌리기: 출력되는 이전 이미지 주소로 `aws lambda update-function-code --function-name <함수> --image-uri <이전 주소>`"""
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = '<WORKER_LAMBDA_NAME>'
AWS = ['--profile', '<AWS_PROFILE>', '--region', '<AWS_REGION>', '--output', 'json']
FILES = {'server.py': 'var/task/server.py', 'ai_runner.py': 'var/task/ai_runner.py',
         'cloud/worker_handler.py': 'var/task/worker_handler.py'}
SINGLE = ('application/vnd.docker.distribution.manifest.v2+json', 'application/vnd.oci.image.manifest.v1+json')
INDEX = ('application/vnd.docker.distribution.manifest.list.v2+json', 'application/vnd.oci.image.index.v1+json')


def aws(*args):
    r = subprocess.run(['aws', *args, *AWS], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('AWS 오류: ' + (r.stderr.strip() or r.stdout.strip()))
    return json.loads(r.stdout) if r.stdout.strip() else {}


def get_manifest(repo, digest):
    out = aws('ecr', 'batch-get-image', '--repository-name', repo, '--image-ids', f'imageDigest={digest}',
              '--accepted-media-types', *SINGLE, *INDEX)
    if not out.get('images'):
        raise SystemExit('이미지 정보를 못 읽음: ' + json.dumps(out.get('failures')))
    return json.loads(out['images'][0]['imageManifest'])


def download_blob(repo, digest):
    url = aws('ecr', 'get-download-url-for-layer', '--repository-name', repo, '--layer-digest', digest)['downloadUrl']
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    if 'sha256:' + hashlib.sha256(data).hexdigest() != digest:
        raise SystemExit('내려받은 설정 파일 해시 불일치')
    return data


def upload_blob(repo, data, tmp):
    digest = 'sha256:' + hashlib.sha256(data).hexdigest()
    have = aws('ecr', 'batch-check-layer-availability', '--repository-name', repo, '--layer-digests', digest)
    if have.get('layers') and have['layers'][0].get('layerAvailability') == 'AVAILABLE':
        return digest
    upload_id = aws('ecr', 'initiate-layer-upload', '--repository-name', repo)['uploadId']
    part = Path(tmp) / ('part-' + digest[7:19])
    part.write_bytes(data)
    aws('ecr', 'upload-layer-part', '--repository-name', repo, '--upload-id', upload_id,
        '--part-first-byte', '0', '--part-last-byte', str(len(data) - 1), '--layer-part-blob', f'fileb://{part}')
    aws('ecr', 'complete-layer-upload', '--repository-name', repo, '--upload-id', upload_id, '--layer-digests', digest)
    return digest


def build_layer():
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.PAX_FORMAT) as tar:
        for src, dst in FILES.items():
            data = (ROOT / src).read_bytes()
            info = tarfile.TarInfo(dst)
            info.size, info.mode, info.mtime, info.uid, info.gid = len(data), 0o644, int(time.time()), 0, 0
            tar.addfile(info, io.BytesIO(data))
    raw = raw.getvalue()
    return raw, gzip.compress(raw, mtime=0)


def main():
    fn = aws('lambda', 'get-function', '--function-name', FUNCTION)
    image_uri, resolved = fn['Code']['ImageUri'], fn['Code']['ResolvedImageUri']
    repo_uri, base_digest = resolved.split('@')
    repo = repo_uri.split('/', 1)[1]
    print('현재(되돌릴 때 쓸) 이미지:', resolved)
    manifest = get_manifest(repo, base_digest)
    if manifest.get('mediaType') in INDEX or 'manifests' in manifest:
        pick = next(m for m in manifest['manifests']
                    if m.get('platform', {}).get('architecture') == 'arm64' and m.get('platform', {}).get('os') == 'linux')
        manifest = get_manifest(repo, pick['digest'])
    media = manifest.get('mediaType') or SINGLE[1]
    if media not in SINGLE:
        raise SystemExit('알 수 없는 이미지 형식: ' + media)
    config = json.loads(download_blob(repo, manifest['config']['digest']))
    raw, gz = build_layer()
    with tempfile.TemporaryDirectory() as tmp:
        layer_digest = upload_blob(repo, gz, tmp)
        config['rootfs']['diff_ids'].append('sha256:' + hashlib.sha256(raw).hexdigest())
        config.setdefault('history', []).append({'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                                 'created_by': 'cloud/deploy_worker.py: ' + ', '.join(FILES)})
        config_bytes = json.dumps(config, separators=(',', ':')).encode()
        config_digest = upload_blob(repo, config_bytes, tmp)
    oci = media == SINGLE[1]
    manifest['config'] = {**manifest['config'], 'digest': config_digest, 'size': len(config_bytes)}
    manifest['layers'].append({'mediaType': 'application/vnd.oci.image.layer.v1.tar+gzip' if oci else
                               'application/vnd.docker.image.rootfs.diff.tar.gzip', 'size': len(gz), 'digest': layer_digest})
    body = json.dumps(manifest, separators=(',', ':'))
    tag = time.strftime('patch-%Y%m%d-%H%M%S')
    for t in (tag, 'latest'):
        aws('ecr', 'put-image', '--repository-name', repo, '--image-tag', t,
            '--image-manifest', body, '--image-manifest-media-type', media)
    print('새 이미지 태그:', tag)
    aws('lambda', 'update-function-code', '--function-name', FUNCTION, '--image-uri', f'{repo_uri}:{tag}')
    subprocess.run(['aws', 'lambda', 'wait', 'function-updated', '--function-name', FUNCTION, *AWS[:4]], check=True)
    print('worker 반영 완료:', aws('lambda', 'get-function', '--function-name', FUNCTION)['Code']['ResolvedImageUri'].split('@')[1])


if __name__ == '__main__':
    main()
