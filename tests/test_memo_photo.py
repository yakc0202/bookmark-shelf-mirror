from test_sharing import api
import base64, hashlib, json, os, unittest

JPEG=b'\xff\xd8\xff\xe0'+b'x'*100+b'\xff\xd9'

class MemoPhoto(unittest.TestCase):
 def setUp(self):
  os.environ['CLIENT_TOKEN_HASH']=hashlib.sha256(b'k').hexdigest()
  self.puts=[];self.transacts=[]
  self.orig=(api.S3,api.transact)
  api.S3=type('S3',(),{'put_object':lambda s,**kw:self.puts.append(kw)})()
  api.transact=lambda fn:self.transacts.append(fn)
 def tearDown(self):api.S3,api.transact=self.orig
 def call(self,image):
  event={'rawPath':'/api/memos/photo','requestContext':{'http':{'method':'POST'}},'headers':{'authorization':'Bearer k'},'body':json.dumps({'image':base64.b64encode(image).decode()})}
  return api.handler(event,None)
 def test_stores_image_without_creating_bookmark(self):
  out=self.call(JPEG)
  self.assertEqual(out['statusCode'],200)
  url=json.loads(out['body'])['url']
  self.assertEqual(len(self.puts),1);key=self.puts[0]['Key']
  self.assertTrue(key.startswith('photos/') and key.endswith('.jpg'))
  self.assertEqual(url,'https://test/'+key)
  self.assertEqual(self.transacts,[])
 def test_rejects_non_jpeg(self):
  self.assertEqual(self.call(b'not a jpeg')['statusCode'],400)
  self.assertEqual(self.puts,[])
if __name__=='__main__':unittest.main()
