"""화면 파일(index.html 등, CloudFront 기본 동작)을 압축해서 보내게 바꾼다.

지금 기본 동작은 관리형 CachingDisabled 정책이라 압축까지 꺼져 있다(207KB가 그대로 감).
압축을 켠 전용 캐시 정책(최소·기본 TTL 0, 쿠키·헤더·쿼리 없이 Accept-Encoding만)을 만들어 기본 동작에 붙인다.
- index.html은 S3에 Cache-Control: no-cache로 올리므로 배포는 지금처럼 바로 반영된다.
- 사이트 잠금 함수(viewer-request)는 캐시보다 먼저 돌아 잠금은 그대로다.
- photos/*, s/* 동작은 건드리지 않는다.

    python3 cloud/enable_page_compression.py          # 미리보기(바꿀 내용만 출력)
    python3 cloud/enable_page_compression.py --apply  # 실제 반영
    python3 cloud/enable_page_compression.py --undo   # 원래 CachingDisabled로 되돌리기

필요 권한·순서는 cloud/INFRA.md "화면 파일 압축" 참고.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import site_config as cfg  # noqa: E402

DIST = cfg.DISTRIBUTION
POLICY_NAME = 'bookmark-shelf-page-compress'
CACHING_DISABLED = '4135ea2d-6df8-44a3-9df3-4b5a84be39ad'  # AWS 관리형 CachingDisabled


def aws(*args):
    r = subprocess.run(['aws', 'cloudfront', *args, *cfg.AWS_ARGS, '--output', 'json'], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('aws cloudfront ' + args[0] + ' 실패: ' + r.stderr.strip()[:300])
    return json.loads(r.stdout or '{}')


def find_policy():
    for p in aws('list-cache-policies', '--type', 'custom').get('CachePolicyList', {}).get('Items', []):
        if p['CachePolicy']['CachePolicyConfig']['Name'] == POLICY_NAME:
            return p['CachePolicy']['Id']
    return None


def create_policy():
    config = {
        'Name': POLICY_NAME, 'Comment': '서랍 화면: 매번 원본 확인 + gzip/br 압축',
        'MinTTL': 0, 'DefaultTTL': 0, 'MaxTTL': 31536000,
        'ParametersInCacheKeyAndForwardedToOrigin': {
            'EnableAcceptEncodingGzip': True, 'EnableAcceptEncodingBrotli': True,
            'HeadersConfig': {'HeaderBehavior': 'none'}, 'CookiesConfig': {'CookieBehavior': 'none'},
            'QueryStringsConfig': {'QueryStringBehavior': 'none'}}}
    return aws('create-cache-policy', '--cache-policy-config', json.dumps(config))['CachePolicy']['Id']


def main():
    apply, undo = '--apply' in sys.argv, '--undo' in sys.argv
    got = aws('get-distribution-config', '--id', DIST)
    config, etag = got['DistributionConfig'], got['ETag']
    current = config['DefaultCacheBehavior'].get('CachePolicyId')
    if undo:
        target = CACHING_DISABLED
    else:
        target = find_policy()
        if not target:
            print('새 캐시 정책 만들 것:', POLICY_NAME)
            if not apply:
                print('미리보기만 함 — --apply로 반영')
                return
            target = create_policy()
            print('캐시 정책 만듦:', target)
    print('기본 동작 캐시 정책:', current, '→', target, '(압축:', config['DefaultCacheBehavior'].get('Compress'), ')')
    if current == target:
        print('이미 적용됨')
        return
    if not (apply or undo):
        print('미리보기만 함 — --apply로 반영')
        return
    config['DefaultCacheBehavior']['CachePolicyId'] = target
    config['DefaultCacheBehavior']['Compress'] = True
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(config, f)
    try:
        aws('update-distribution', '--id', DIST, '--if-match', etag, '--distribution-config', f'file://{f.name}')
    finally:
        Path(f.name).unlink()
    print('반영함. 전 세계 엣지에 퍼지는 데 몇 분 걸림 — 확인 방법은 cloud/INFRA.md')


main()
