"""배포·운영 스크립트가 함께 쓰는 사이트 설정(cloud/site.json)을 읽는다.

도메인을 바꿀 때는 cloud/site.json의 site_domain만 고치고 docs/DOMAIN_MIGRATION.md 순서대로 배포한다.
S3 버킷 이름(bucket)은 도메인과 별개라 바꾸지 않는다."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / 'cloud/site.json').read_text())

SITE_DOMAIN = SITE['site_domain']
SITE_URL = 'https://' + SITE_DOMAIN
BUCKET = SITE['bucket']
PROFILE = SITE['aws_profile']
REGION = SITE['region']
DISTRIBUTION = SITE['cloudfront_distribution']
API_FUNCTION = SITE['api_function']
WORKER_FUNCTION = SITE['worker_function']
GATE_FUNCTION = SITE['gate_function']
AWS_ARGS = ['--profile', PROFILE, '--region', REGION]
