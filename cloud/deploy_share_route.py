"""공유 링크(/s/토큰)를 CloudFront 기본 주소(xxxx.cloudfront.net)로 열 수 있게 한다.

- CloudFront에 api(Lambda Function URL) 원본과 `s/*` 동작을 추가한다. 이 동작에는 사이트 잠금 함수를 붙이지 않고(받는 사람은 접속 키가 없음),
  캐시하지 않는다(공유를 끄면 바로 막혀야 함). Host 헤더는 Function URL 것으로 바꿔 보낸다(AllViewerExceptHostHeader).
- S3의 config.js에 window.SHELF_SHARE_BASE(공유 링크 앞부분)를 넣는다. 화면은 이 값으로 공유 주소를 만든다.
- CloudFront 기본 주소는 도메인을 바꿔도 그대로라, 도메인 이관 전후로 보낸 공유 링크가 계속 열린다.
- 이미 반영돼 있으면 아무것도 바꾸지 않는다(여러 번 실행해도 됨).
사용: python3 cloud/deploy_share_route.py"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_config as cfg  # noqa: E402

ORIGIN_ID = 'api-origin'
PATH = 's/*'
CACHING_DISABLED = '4135ea2d-6df8-44a3-9df3-4b5a84be39ad'           # AWS 관리형 캐시 정책
ALL_VIEWER_EXCEPT_HOST = 'b689b0a8-53d0-40ab-baf2-68738e2966ac'     # AWS 관리형 원본 요청 정책


def aws(*args, text=False):
    r = subprocess.run(['aws', *args, *cfg.AWS_ARGS], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('AWS 오류: ' + (r.stderr.strip() or r.stdout.strip()))
    return r.stdout if text else (json.loads(r.stdout) if r.stdout.strip() else {})


def main():
    config_js = aws('s3', 'cp', f's3://{cfg.BUCKET}/config.js', '-', text=True)
    m = re.search(r'SHELF_API_BASE\s*=\s*"https://([^/"]+)/?"', config_js)
    if not m:
        raise SystemExit('config.js에서 api 주소를 찾지 못했습니다.')
    api_host = m.group(1)

    out = aws('cloudfront', 'get-distribution-config', '--id', cfg.DISTRIBUTION, '--output', 'json')
    etag, conf = out['ETag'], out['DistributionConfig']
    changed = False
    origins = conf['Origins']
    if not any(o['Id'] == ORIGIN_ID for o in origins['Items']):
        origins['Items'].append({
            'Id': ORIGIN_ID, 'DomainName': api_host, 'OriginPath': '', 'CustomHeaders': {'Quantity': 0},
            'CustomOriginConfig': {'HTTPPort': 80, 'HTTPSPort': 443, 'OriginProtocolPolicy': 'https-only',
                                   'OriginSslProtocols': {'Quantity': 1, 'Items': ['TLSv1.2']},
                                   'OriginReadTimeout': 30, 'OriginKeepaliveTimeout': 5},
            'ConnectionAttempts': 3, 'ConnectionTimeout': 10, 'OriginShield': {'Enabled': False}, 'OriginAccessControlId': ''})
        origins['Quantity'] = len(origins['Items'])
        changed = True
    behaviors = conf.setdefault('CacheBehaviors', {'Quantity': 0, 'Items': []})
    behaviors.setdefault('Items', [])
    if not any(b['PathPattern'] == PATH for b in behaviors['Items']):
        behaviors['Items'].insert(0, {
            'PathPattern': PATH, 'TargetOriginId': ORIGIN_ID,
            'TrustedSigners': {'Enabled': False, 'Quantity': 0}, 'TrustedKeyGroups': {'Enabled': False, 'Quantity': 0},
            'ViewerProtocolPolicy': 'redirect-to-https',
            'AllowedMethods': {'Quantity': 2, 'Items': ['HEAD', 'GET'], 'CachedMethods': {'Quantity': 2, 'Items': ['HEAD', 'GET']}},
            'SmoothStreaming': False, 'Compress': True,
            'LambdaFunctionAssociations': {'Quantity': 0}, 'FunctionAssociations': {'Quantity': 0},
            'FieldLevelEncryptionId': '', 'CachePolicyId': CACHING_DISABLED, 'OriginRequestPolicyId': ALL_VIEWER_EXCEPT_HOST})
        behaviors['Quantity'] = len(behaviors['Items'])
        changed = True
    if changed:
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(conf, f)
        try:
            aws('cloudfront', 'update-distribution', '--id', cfg.DISTRIBUTION, '--if-match', etag,
                '--distribution-config', f'file://{f.name}', '--output', 'json')
        finally:
            Path(f.name).unlink()
        print('CloudFront에 공유 링크 경로(s/*)를 추가했습니다. 전 세계에 퍼지는 데 몇 분 걸립니다.')
    else:
        print('CloudFront 공유 링크 경로는 이미 있습니다.')

    share_base = 'https://' + aws('cloudfront', 'get-distribution', '--id', cfg.DISTRIBUTION,
                                  '--query', 'Distribution.DomainName', '--output', 'text', text=True).strip()
    line = f'window.SHELF_SHARE_BASE = "{share_base}";'
    if line not in config_js:
        body = re.sub(r'\n?window\.SHELF_SHARE_BASE\s*=.*', '', config_js).rstrip('\n') + '\n' + line + '\n'
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
            f.write(body)
        try:
            aws('s3api', 'put-object', '--bucket', cfg.BUCKET, '--key', 'config.js', '--body', f.name,
                '--content-type', 'application/javascript; charset=utf-8', '--cache-control', 'no-cache')
        finally:
            Path(f.name).unlink()
        print('config.js에 공유 링크 주소를 넣었습니다:', share_base)
    else:
        print('config.js 공유 링크 주소 확인:', share_base)


if __name__ == '__main__':
    main()
