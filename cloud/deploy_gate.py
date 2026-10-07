"""cloud/site-gate.js 를 CloudFront Function으로 배포하고 기본 동작(viewer-request)에 연결한다.
가짜 키로 CloudFront에서 동작을 시험한 뒤, 통과하면 API Lambda의 CLIENT_TOKEN_HASH로 바꿔 발행한다.
사용: python3 cloud/deploy_gate.py [--test-only]"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = '<GATE_FUNCTION_NAME>'
DIST = '<CLOUDFRONT_DISTRIBUTION_ID>'
API_FUNCTION = '<API_LAMBDA_NAME>'
HOST = '<SITE_DOMAIN>'
AWS = ['--profile', '<AWS_PROFILE>', '--output', 'json']


def aws(*args, region='us-east-1'):
    r = subprocess.run(['aws', *args, *AWS, '--region', region], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return json.loads(r.stdout) if r.stdout.strip() else {}


def build(key_hash):
    code = (ROOT / 'cloud/site-gate.js').read_text()
    assert '__CLIENT_TOKEN_HASH__' in code
    out = ROOT / 'data/cloud-build/site-gate.js'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(code.replace('__CLIENT_TOKEN_HASH__', key_hash))
    return out


def upsert(path):
    config = json.dumps({'Comment': 'bookmark-shelf site gate', 'Runtime': 'cloudfront-js-2.0'})
    try:
        etag = aws('cloudfront', 'describe-function', '--name', NAME, '--stage', 'DEVELOPMENT')['ETag']
    except RuntimeError as e:
        if 'NoSuchFunctionExists' not in str(e):
            raise
        return aws('cloudfront', 'create-function', '--name', NAME, '--function-config', config,
                   '--function-code', f'fileb://{path}')['ETag']
    return aws('cloudfront', 'update-function', '--name', NAME, '--if-match', etag, '--function-config', config,
               '--function-code', f'fileb://{path}')['ETag']


def run_test(etag, uri, host=HOST, cookie=None):
    event = {'version': '1.0', 'context': {'eventType': 'viewer-request'}, 'viewer': {'ip': '198.51.100.1'},
             'request': {'method': 'GET', 'uri': uri, 'querystring': {}, 'headers': {'host': {'value': host}},
                         'cookies': {'shelf_key': {'value': cookie}} if cookie else {}}}
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(event, f)
    result = aws('cloudfront', 'test-function', '--name', NAME, '--if-match', etag, '--stage', 'DEVELOPMENT',
                 '--event-object', f'fileb://{f.name}')['TestResult']
    if result.get('FunctionErrorMessage'):
        raise SystemExit('함수 오류: ' + result['FunctionErrorMessage'])
    return json.loads(result['FunctionOutput'])


def self_test():
    fake = 'gate-selftest-key'
    etag = upsert(build(hashlib.sha256(fake.encode()).hexdigest()))
    checks = [
        ('cloudfront.net 주소는 301로 넘김', run_test(etag, '/', host='<CLOUDFRONT_DEFAULT_DOMAIN>'),
         lambda o: o['response']['statusCode'] == 301 and o['response']['headers']['location']['value'] == f'https://{HOST}/'),
        ('키 없으면 입력 화면', run_test(etag, '/'),
         lambda o: o['response']['statusCode'] == 200 and 'const bad=false' in o['response']['body']['data']),
        ('틀린 키면 오류 안내', run_test(etag, '/', cookie='wrong'),
         lambda o: 'const bad=true' in o['response']['body']['data']),
        ('맞는 키면 통과', run_test(etag, '/', cookie=fake),
         lambda o: 'request' in o and 'response' not in o),
        ('config.js도 키 필요', run_test(etag, '/config.js'),
         lambda o: o['response']['statusCode'] == 200 and '접속 키' in o['response']['body']['data']),
        ('아이콘은 키 없이 통과', run_test(etag, '/apple-touch-icon.png'),
         lambda o: 'request' in o and 'response' not in o),
        ('단축어 파일은 키 없이 통과', run_test(etag, '/shortcuts/Save-to-Shelf.shortcut'),
         lambda o: 'request' in o and 'response' not in o),
    ]
    failed = False
    for label, output, ok in checks:
        passed = ok(output)
        failed |= not passed
        print(('통과' if passed else '실패'), label)
    if failed:
        raise SystemExit('시험 실패 — 발행하지 않음')


def publish():
    key_hash = aws('lambda', 'get-function-configuration', '--function-name', API_FUNCTION,
                   '--query', 'Environment.Variables.CLIENT_TOKEN_HASH', region='<AWS_REGION>')
    if not isinstance(key_hash, str) or len(key_hash) != 64:
        raise SystemExit('CLIENT_TOKEN_HASH를 읽지 못함')
    etag = upsert(build(key_hash))
    arn = aws('cloudfront', 'publish-function', '--name', NAME, '--if-match', etag)['FunctionSummary']['FunctionMetadata']['FunctionARN']
    print('발행 완료:', arn)
    current = aws('cloudfront', 'get-distribution-config', '--id', DIST)
    config, dist_etag = current['DistributionConfig'], current['ETag']
    assoc = config['DefaultCacheBehavior'].setdefault('FunctionAssociations', {'Quantity': 0})
    items = assoc.get('Items', [])
    if any(i['FunctionARN'] == arn and i['EventType'] == 'viewer-request' for i in items):
        print('이미 기본 동작에 연결돼 있음 (발행 내용 즉시 반영)')
        return
    items = [i for i in items if i['EventType'] != 'viewer-request'] + [{'FunctionARN': arn, 'EventType': 'viewer-request'}]
    config['DefaultCacheBehavior']['FunctionAssociations'] = {'Quantity': len(items), 'Items': items}
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(config, f)
    aws('cloudfront', 'update-distribution', '--id', DIST, '--if-match', dist_etag, '--distribution-config', f'file://{f.name}')
    print('기본 동작에 연결함 — 전파까지 몇 분 걸림')


if __name__ == '__main__':
    self_test()
    if '--test-only' not in sys.argv:
        publish()
