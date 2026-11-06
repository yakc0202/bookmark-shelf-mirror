from test_sharing import api
import hashlib, json, os, sys, time, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud'))
from set_password import make_hash

class Login(unittest.TestCase):
 def setUp(self):
  self.data={'items':[]}
  for name,value in (('read',lambda:(self.data,'e')),('transact',self.apply)):
   self.addCleanup(setattr,api,name,getattr(api,name));setattr(api,name,value)
  env={'PASSWORD_HASH':make_hash('맞는 비밀번호',rounds=1000),'SESSION_SECRET':'secret','CLIENT_TOKEN_HASH':hashlib.sha256(b'key').hexdigest(),'WORKER_TOKEN_HASH':hashlib.sha256(b'worker').hexdigest()}
  for k,v in env.items():
   self.addCleanup(os.environ.__setitem__,k,os.environ[k]) if k in os.environ else self.addCleanup(os.environ.pop,k,None)
   os.environ[k]=v
 def apply(self,change):return change(self.data)
 def login(self,password):
  r=api.handler({'rawPath':'/api/login','requestContext':{'http':{'method':'POST'}},'headers':{},'body':json.dumps({'password':password})},None)
  return r['statusCode'],json.loads(r['body'])
 def call(self,path,token):
  return api.handler({'rawPath':path,'requestContext':{'http':{'method':'GET' if path=='/api/all' else 'POST'}},'headers':{'authorization':'Bearer '+token},'body':'{}'},None)['statusCode']
 def test_right_password_gives_working_token(self):
  status,out=self.login('맞는 비밀번호')
  self.assertEqual(status,200);self.assertEqual(self.call('/api/all',out['token']),200)
 def test_wrong_password_rejected(self):
  self.assertEqual(self.login('틀림')[0],401);self.assertEqual(self.data['login_guard']['fails'],1)
 def test_key_still_works_for_shortcut(self):
  self.assertEqual(self.call('/api/all','key'),200);self.assertEqual(self.call('/api/all','nope'),401)
 def test_token_cannot_call_worker(self):
  self.assertEqual(self.call('/worker/claim',self.login('맞는 비밀번호')[1]['token']),401)
 def test_forged_or_expired_token_rejected(self):
  self.assertEqual(self.call('/api/all','s1.4102444800.'+'0'*64),401)
  self.assertEqual(self.call('/api/all',f"s1.1.{api.session_sign('1')}"),401)
 def test_changing_secret_logs_out(self):
  token=self.login('맞는 비밀번호')[1]['token'];os.environ['SESSION_SECRET']='new'
  self.assertEqual(self.call('/api/all',token),401)
 def test_five_failures_make_you_wait_even_with_right_password(self):
  for _ in range(5):self.assertEqual(self.login('틀림')[0],401)
  status,out=self.login('맞는 비밀번호')
  self.assertEqual(status,429);self.assertIn('1분',out['error'])
 def test_wait_grows_and_stops_at_15_minutes(self):
  for fails,seconds in ((5,60),(6,120),(9,900),(12,900)):
   self.data['login_guard']={'fails':fails-1};before=time.time();self.login('틀림')
   self.assertAlmostEqual(self.data['login_guard']['until']-before,seconds,delta=5)
 def test_success_clears_failures(self):
  self.login('틀림');self.assertEqual(self.login('맞는 비밀번호')[0],200);self.assertNotIn('login_guard',self.data)
 def test_guard_not_sent_to_browser(self):
  self.login('틀림');token=self.login('틀림') and 'key'
  r=api.handler({'rawPath':'/api/all','requestContext':{'http':{'method':'GET'}},'headers':{'authorization':'Bearer '+token}},None)
  self.assertNotIn('login_guard',r['body'])
 def test_no_password_set_gives_clear_error(self):
  del os.environ['PASSWORD_HASH']
  self.assertEqual(self.login('아무거나')[0],503)
if __name__=='__main__':unittest.main()
