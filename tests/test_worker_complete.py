from test_sharing import api
import hashlib, json, os, unittest

class WorkerCompleteResponse(unittest.TestCase):
 def setUp(self):
  os.environ['WORKER_TOKEN_HASH']=hashlib.sha256(b'w').hexdigest()
  self.orig=api.transact
 def tearDown(self):api.transact=self.orig
 def call(self):
  event={'rawPath':'/worker/complete','requestContext':{'http':{'method':'POST'}},'headers':{'authorization':'Bearer w'},
         'body':json.dumps({'id':'x','lease':'old','revision':1,'result':{'status':'ready'}})}
  return api.handler(event,None)
 def test_stale_result_is_not_applied_but_answers_ok_so_worker_moves_on(self):
  def stale(fn):raise api.Problem(409,'삭제 또는 수정된 카드라 이전 처리 결과를 적용하지 않았습니다.')
  api.transact=stale
  out=self.call()
  self.assertEqual(out['statusCode'],200)
  self.assertEqual(json.loads(out['body'])['applied'],False)
 def test_other_errors_still_fail(self):
  def broken(fn):raise api.Problem(400,'잘못된 처리 상태입니다.')
  api.transact=broken
  self.assertEqual(self.call()['statusCode'],400)
if __name__=='__main__':unittest.main()
