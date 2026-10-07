from test_sharing import api
import copy
import unittest

class Memos(unittest.TestCase):
 def setUp(self):self.data={'items':[{'id':'b','url':'https://example.com','title':'북마크','status':'ready','folder':'f'}]}
 def save(self,**kw):return api.change(self.data,'/api/memos/save',dict(title='여행',content='계획',folder='여행',bookmark_ids=['b'],**kw))
 def test_create_edit_conflict_delete_preserves_bookmarks(self):
  before=copy.deepcopy(self.data['items']);m=self.save();self.assertEqual(m['revision'],1);self.assertEqual(m['content_revision'],1)
  updated=self.save(id=m['id'],content_revision=1);self.assertEqual(updated['revision'],2);self.assertEqual(updated['content_revision'],2)
  with self.assertRaises(api.Problem) as e:self.save(id=m['id'],content_revision=1)
  self.assertEqual(e.exception.status,409)
  with self.assertRaises(api.Problem):api.change(self.data,'/api/memos/delete',{'id':m['id'],'content_revision':1})
  api.change(self.data,'/api/memos/delete',{'id':m['id'],'content_revision':2})
  self.assertEqual(self.data['items'],before);self.assertEqual(self.data['memos'],[])
 def test_invalid_ref_and_deleted_existing_reference(self):
  with self.assertRaises(api.Problem):api.change(self.data,'/api/memos/save',{'bookmark_ids':['missing']})
  m=self.save();self.data['items'][0]['deleted']=True
  self.save(id=m['id'],content_revision=1)
  with self.assertRaises(api.Problem):self.save()
 def test_background_summary_completion_does_not_block_next_save(self):
  m=self.save()
  api.change(self.data,'/api/memos/summarize',{'id':m['id']})
  job=api.change(self.data,'/worker/claim',{})['item']
  api.change(self.data,'/worker/complete',{'id':job['id'],'lease':job['lease'],'revision':job['revision'],
   'kind':'memo-summary','result':{'status':'ready','summary':'요약'}})
  memo=self.data['memos'][0]
  self.assertEqual(memo['summary'],'요약');self.assertNotIn('kind',memo);self.assertGreater(memo['revision'],job['revision'])
  self.assertEqual(memo['content_revision'],1)
  updated=self.save(id=m['id'],content_revision=memo['content_revision'])
  self.assertEqual(updated['content_revision'],2)
 def test_save_does_not_auto_queue_summary(self):
  m=self.save()
  self.assertNotIn('kind',m);self.assertNotIn('status',m)
  updated=api.change(self.data,'/api/memos/save',{'id':m['id'],'title':'여행','content':'새 내용','folder':'여행','bookmark_ids':['b'],'content_revision':m['content_revision']})
  self.assertNotIn('kind',updated);self.assertNotIn('status',updated)
 def test_summarize_requires_existing_memo_and_content(self):
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/memos/summarize',{'id':'missing'})
  m=api.change(self.data,'/api/memos/save',{'title':'여행','content':'   ','folder':'여행','bookmark_ids':['b']})
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/memos/summarize',{'id':m['id']})
 def test_summarize_queues_without_bumping_content_revision(self):
  m=self.save()
  original_revision,original_content_revision=m['revision'],m['content_revision']
  out=api.change(self.data,'/api/memos/summarize',{'id':m['id']})
  self.assertEqual(out['kind'],'memo-summary');self.assertEqual(out['status'],'queued')
  self.assertGreater(out['revision'],original_revision)
  self.assertEqual(out['content_revision'],original_content_revision)
 def test_auth_and_private_memos(self):
  import os,json
  os.environ['CLIENT_TOKEN_HASH']='not-a-token'
  event={'rawPath':'/api/memos','requestContext':{'http':{'method':'GET'}},'headers':{}}
  self.assertEqual(api.handler(event,None)['statusCode'],401)
 def test_utf8_body_limit(self):
  text='한'*100000
  m=api.change(self.data,'/api/memos/save',{'content':text})
  self.assertEqual(m['content'],text)
  with self.assertRaises(api.Problem):api.change(self.data,'/api/memos/save',{'content':text+'한'})
if __name__=='__main__':unittest.main()
