"""worker Lambda가 AI 로그인 정보를 SSM(기본) 또는 예전 Secrets Manager에서 읽는지."""
import importlib
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'cloud'))

CODEX = {'auth_mode': 'chatgpt', 'tokens': {'id_token': 'x'}}


class FakeClient:
    def __init__(self, service, missing=False):
        self.service, self.missing = service, missing

    def get_parameters(self, Names, WithDecryption):
        assert WithDecryption
        if self.missing:
            return {'Parameters': [], 'InvalidParameters': Names}
        values = {'/p/codex-auth': json.dumps(CODEX), '/p/claude-token': 'tok'}
        return {'Parameters': [{'Name': n, 'Value': values[n]} for n in reversed(Names)], 'InvalidParameters': []}

    def get_secret_value(self, SecretId):
        return {'SecretString': json.dumps({'codex_auth': CODEX, 'claude_token': 'old'})}


def load(env, missing=False):
    calls = []
    boto3 = types.SimpleNamespace(client=lambda svc: calls.append(svc) or FakeClient(svc, missing))
    base = {'API_URL': 'https://x', 'WORKER_TOKEN': 't'}
    with mock.patch.dict(os.environ, {**base, **env}, clear=True), mock.patch.dict(sys.modules, {'boto3': boto3}):
        mod = importlib.reload(importlib.import_module('worker_handler'))
        try:
            return mod.load_auth(), calls
        except RuntimeError as e:
            return e, calls


class WorkerAuthTest(unittest.TestCase):
    def test_reads_ssm_when_prefix_set(self):
        (codex, claude), calls = load({'AUTH_PARAM_PREFIX': '/p/', 'AUTH_SECRET_ARN': 'arn'})
        self.assertEqual(calls, ['ssm'])
        self.assertEqual(codex, CODEX)
        self.assertEqual(claude, 'tok')

    def test_falls_back_to_secrets_manager(self):
        (codex, claude), calls = load({'AUTH_SECRET_ARN': 'arn'})
        self.assertEqual(calls, ['secretsmanager'])
        self.assertEqual(claude, 'old')

    def test_missing_parameter_is_an_error(self):
        err, _ = load({'AUTH_PARAM_PREFIX': '/p/'}, missing=True)
        self.assertIsInstance(err, RuntimeError)
        self.assertIn('/p/codex-auth', str(err))

    def test_upload_names_match_handler_prefix(self):
        import worker_auth
        self.assertEqual(worker_auth.NAMES['codex'], worker_auth.PREFIX + 'codex-auth')
        self.assertEqual(worker_auth.NAMES['claude'], worker_auth.PREFIX + 'claude-token')


    def test_refreshed_codex_login_is_saved_back(self):
        puts = []
        client = types.SimpleNamespace(put_parameter=lambda **kw: puts.append(kw))
        boto3 = types.SimpleNamespace(client=lambda svc: client)
        base = {'API_URL': 'https://x', 'WORKER_TOKEN': 't', 'AUTH_PARAM_PREFIX': '/p/'}
        with mock.patch.dict(os.environ, base, clear=True), mock.patch.dict(sys.modules, {'boto3': boto3}):
            mod = importlib.reload(importlib.import_module('worker_handler'))
            import tempfile
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / 'auth.json'
                mod.CODEX_SLOTS[1] = ('codex-auth', path)
                path.write_text(json.dumps(CODEX))
                mod.save_refreshed_codex_auth({1: CODEX})          # 안 바뀌면 저장 안 함
                self.assertEqual(puts, [])
                new = {**CODEX, 'tokens': {'id_token': 'y'}}
                path.write_text(json.dumps(new))
                mod.save_refreshed_codex_auth({1: CODEX})
                self.assertEqual(len(puts), 1)
                self.assertEqual((puts[0]['Name'], json.loads(puts[0]['Value']), puts[0]['Overwrite']), ('/p/codex-auth', new, True))
                path.write_text('{broken')
                mod.save_refreshed_codex_auth({1: CODEX})          # 깨진 파일은 저장 안 함
                self.assertEqual(len(puts), 1)


if __name__ == '__main__':
    unittest.main()
