from test_sharing import api
import unittest

class Extract(unittest.TestCase):
 def setUp(self):
  self.data={'items':[],'memos':[{'id':'m1','title':'원본','content':'## 가게1\n내용','folder':'차','bookmark_ids':[],'created':1,'updated':1,'revision':1}]}
 def test_missing_memo(self):
  with self.assertRaises(api.Problem) as e:api.change(self.data,'/api/memos/extract',{'id':'missing','instruction':'추천 매장만'})
  self.assertEqual(e.exception.status,404)
 def test_blank_and_too_long_instruction_rejected(self):
  with self.assertRaises(api.Problem):api.change(self.data,'/api/memos/extract',{'id':'m1','instruction':'  '})
  with self.assertRaises(api.Problem):api.change(self.data,'/api/memos/extract',{'id':'m1','instruction':'x'*201})
 def test_queues_job_inheriting_folder_and_snapshot(self):
  job=api.change(self.data,'/api/memos/extract',{'id':'m1','instruction':'추천 매장만'})
  self.assertEqual(job['status'],'queued');self.assertEqual(job['kind'],'memo-extract')
  self.assertEqual(job['folder'],'차');self.assertEqual(job['source_snapshot'],'## 가게1\n내용')
  self.assertEqual(job['source_memo_id'],'m1');self.assertIn(job,self.data['memos'])
 def test_worker_claims_memo_extract_jobs_fifo_with_items(self):
  self.data['items'].append({'id':'i1','url':'https://example.com','title':'t','status':'queued','created':5,'deleted':False,'folder':'x'})
  job=api.change(self.data,'/api/memos/extract',{'id':'m1','instruction':'추천 매장만'})
  job['created']=1
  claimed=api.change(self.data,'/worker/claim',{})
  self.assertEqual(claimed['item']['id'],job['id']);self.assertEqual(claimed['item']['kind'],'memo-extract')
  self.assertEqual(job['status'],'processing');self.assertIn('lease',job)
  claimed2=api.change(self.data,'/worker/claim',{})
  self.assertEqual(claimed2['item']['id'],'i1')
 def test_worker_complete_ready_updates_memo_and_bumps_revision(self):
  job=api.change(self.data,'/api/memos/extract',{'id':'m1','instruction':'추천 매장만'})
  claimed=api.change(self.data,'/worker/claim',{})['item']
  api.change(self.data,'/worker/complete',{'id':job['id'],'lease':claimed['lease'],'revision':1,'kind':'memo-extract',
             'result':{'status':'ready','title':'추천 매장','content':'## 가게1\n발췌'}})
  self.assertEqual(job['title'],'추천 매장');self.assertEqual(job['content'],'## 가게1\n발췌')
  self.assertEqual(job['status'],'ready');self.assertEqual(job['revision'],2);self.assertNotIn('lease',job)
 def test_worker_complete_rejects_stale_lease_or_revision(self):
  job=api.change(self.data,'/api/memos/extract',{'id':'m1','instruction':'추천 매장만'})
  claimed=api.change(self.data,'/worker/claim',{})['item']
  with self.assertRaises(api.Problem) as e:
   api.change(self.data,'/worker/complete',{'id':job['id'],'lease':'wrong','revision':1,'kind':'memo-extract','result':{'status':'ready'}})
  self.assertEqual(e.exception.status,409)
  with self.assertRaises(api.Problem):
   api.change(self.data,'/worker/complete',{'id':job['id'],'lease':claimed['lease'],'revision':99,'kind':'memo-extract','result':{'status':'ready'}})
 def test_worker_complete_needs_content_leaves_content_untouched(self):
  job=api.change(self.data,'/api/memos/extract',{'id':'m1','instruction':'추천 매장만'})
  claimed=api.change(self.data,'/worker/claim',{})['item']
  api.change(self.data,'/worker/complete',{'id':job['id'],'lease':claimed['lease'],'revision':1,'kind':'memo-extract',
             'result':{'status':'needs_content','error':'못 찾음'}})
  self.assertEqual(job['status'],'needs_content');self.assertEqual(job['content'],'');self.assertEqual(job['error'],'못 찾음')
if __name__=='__main__':unittest.main()
