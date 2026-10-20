from test_sharing import api
import unittest, hashlib, json, os, gzip, base64

class StarAndAll(unittest.TestCase):
 def setUp(self):
  self.data={'items':[{'id':'one','url':'https://example.com','title':'t','folder':'f','status':'processing','revision':3,'created':1}]}
 def test_star_keeps_revision(self):
  api.change(self.data,'/api/update',{'id':'one','starred':True})
  x=self.data['items'][0];self.assertTrue(x['starred']);self.assertEqual(x['revision'],3)
  self.assertTrue(api.visible(x)['starred'])
  api.change(self.data,'/api/update',{'id':'one','starred':False})
  self.assertFalse(self.data['items'][0]['starred'])
 def test_all_returns_everything_in_one_read(self):
  reads=[]
  old=api.read;self.addCleanup(setattr,api,'read',old)
  api.read=lambda:(reads.append(1),(self.data,'e'))[1]
  os.environ['CLIENT_TOKEN_HASH']=hashlib.sha256(b'k').hexdigest()
  event={'rawPath':'/api/all','requestContext':{'http':{'method':'GET'}},'headers':{'authorization':'Bearer k'}}
  r=api.handler(event,None);self.assertEqual(r['statusCode'],200)
  body=r['body']
  if r.get('isBase64Encoded'):body=gzip.decompress(base64.b64decode(body)).decode()
  out=json.loads(body)
  self.assertEqual(set(out),{'items','memos','habits','ledger','plans','schedule','wishlist'})
  self.assertEqual(out['items'][0]['id'],'one');self.assertEqual(len(reads),1)
if __name__=='__main__':unittest.main()
