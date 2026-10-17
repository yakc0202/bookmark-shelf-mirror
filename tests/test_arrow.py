from test_sharing import api
import unittest

class Arrow(unittest.TestCase):
 def test_arrowize_nested_in_place(self):
  d={'items':[{'title':'A -> B','entries':[{'title':'x->y','url':'https://e.com/a-b'}]}],'memos':[{'content':'1->2->3'}],'n':3}
  api.arrowize(d)
  self.assertEqual(d['items'][0]['title'],'A → B');self.assertEqual(d['items'][0]['entries'][0]['title'],'x→y')
  self.assertEqual(d['items'][0]['entries'][0]['url'],'https://e.com/a-b');self.assertEqual(d['memos'][0]['content'],'1→2→3');self.assertEqual(d['n'],3)
 def test_saved_memo_comes_back_with_arrow(self):
  store={'data':{'items':[],'memos':[{'id':'m','content':'old ->'}]}}
  old_read,old_s3=api.read,api.S3
  self.addCleanup(lambda:(setattr(api,'read',old_read),setattr(api,'S3',old_s3)))
  api.read=lambda:(store['data'],'e')
  class S3:
   @staticmethod
   def put_object(**kw):
    import json;store['data']=json.loads(kw['Body'])
  api.S3=S3
  out=api.transact(lambda d:d['memos'][0].update(title='t')or d['memos'][0])
  self.assertEqual(out['content'],'old →');self.assertEqual(store['data']['memos'][0]['content'],'old →')
if __name__=='__main__':unittest.main()
