"""cloud/site-gate.js 를 CloudFront Function으로 배포하고 기본 동작(viewer-request)에 연결한다.
가짜 비밀값으로 CloudFront에서 동작을 시험한 뒤, 통과하면 API Lambda의 SESSION_SECRET으로 바꿔 발행한다.
비밀번호가 아직 설정되지 않았으면 발행하지 않는다(사이트에 못 들어가게 되므로).
사용: python3 cloud/deploy_gate.py [--test-only]"""
import hashlib
import hmac
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_config as cfg  # noqa: E402

ROOT = cfg.ROOT
NAME = cfg.GATE_FUNCTION
DIST = cfg.DISTRIBUTION
API_FUNCTION = cfg.API_FUNCTION
HOST = cfg.SITE_DOMAIN
AWS = ['--profile', cfg.PROFILE, '--output', 'json']


def aws(*args, region='us-east-1'):
    r = subprocess.run(['aws', *args, *AWS, '--region', region], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return json.loads(r.stdout) if r.stdout.strip() else {}


def api_base():
    r = subprocess.run(['aws', 's3', 'cp', f's3://{cfg.BUCKET}/config.js', '-', *AWS, '--region', cfg.REGION], capture_output=True, text=True)
    m = re.search(r'SHELF_API_BASE\s*=\s*"(https://[^"]+?)/?"', r.stdout)
    if not m:
        raise SystemExit('config.js에서 API 주소를 읽지 못함: ' + r.stderr.strip())
    return m[1]


def build(secret):
    code = (ROOT / 'cloud/site-gate.js').read_text()
    assert '__SESSION_SECRET__' in code and '__SITE_DOMAIN__' in code and '__API_BASE__' in code
    code = code.replace('__SITE_DOMAIN__', HOST).replace('__API_BASE__', api_base())
    out = ROOT / 'data/cloud-build/site-gate.js'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(code.replace('__SESSION_SECRET__', secret))
    return out


def session(secret, exp):
    return f's1.{exp}.' + hmac.new(secret.encode(), f's1.{exp}'.encode(), hashlib.sha256).hexdigest()


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
    fake = 'gate-selftest-secret'
    etag = upsert(build(fake))
    checks = [
        ('다른 주소(cloudfront.net 기본 주소 등)는 301로 넘김', run_test(etag, '/', host='d111111abcdef8.cloudfront.net'),
         lambda o: o['response']['statusCode'] == 301 and o['response']['headers']['location']['value'] == f'https://{HOST}/'),
        ('입장권 없으면 비밀번호 화면', run_test(etag, '/'),
         lambda o: o['response']['statusCode'] == 200 and 'const bad=false' in o['response']['body']['data']),
        ('틀린 입장권이면 저장값을 지우는 화면', run_test(etag, '/', cookie='wrong'),
         lambda o: 'const bad=true' in o['response']['body']['data']),
        ('기간 지난 입장권은 막음', run_test(etag, '/', cookie=session(fake, 1)),
         lambda o: 'const bad=true' in o['response']['body']['data']),
        ('맞는 입장권이면 통과', run_test(etag, '/', cookie=session(fake, 4102444800)),
         lambda o: 'request' in o and 'response' not in o),
        ('config.js도 입장권 필요', run_test(etag, '/config.js'),
         lambda o: o['response']['statusCode'] == 200 and '비밀번호' in o['response']['body']['data']),
        ('아이콘은 입장권 없이 통과', run_test(etag, '/apple-touch-icon.png'),
         lambda o: 'request' in o and 'response' not in o),
        ('단축어 파일은 입장권 없이 통과', run_test(etag, '/shortcuts/Save-to-Shelf.shortcut'),
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
    env = aws('lambda', 'get-function-configuration', '--function-name', API_FUNCTION,
              '--query', 'Environment.Variables', region=cfg.REGION)
    if not env.get('PASSWORD_HASH') or not env.get('SESSION_SECRET'):
        raise SystemExit('비밀번호가 아직 없음 — 먼저 python3 cloud/set_password.py')
    etag = upsert(build(env['SESSION_SECRET']))
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
