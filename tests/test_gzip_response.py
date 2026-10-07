from test_sharing import api
import gzip, base64, json, unittest

class GzipResponse(unittest.TestCase):
 def test_small_body_not_compressed_even_with_gzip_support(self):
  out=api.response(200,{'a':1},'gzip, deflate, br')
  self.assertNotIn('content-encoding',out['headers'])
  self.assertEqual(json.loads(out['body']),{'a':1})
 def test_large_body_compressed_when_client_supports_gzip(self):
  body={'items':[{'id':i,'title':'x'*50} for i in range(200)]}
  out=api.response(200,body,'gzip, deflate, br')
  self.assertEqual(out['headers']['content-encoding'],'gzip')
  self.assertTrue(out['isBase64Encoded'])
  decoded=gzip.decompress(base64.b64decode(out['body']))
  self.assertEqual(json.loads(decoded),body)
 def test_large_body_not_compressed_without_accept_encoding(self):
  body={'items':[{'id':i,'title':'x'*50} for i in range(200)]}
  out=api.response(200,body)
  self.assertNotIn('content-encoding',out['headers'])
  self.assertEqual(json.loads(out['body']),body)
if __name__=='__main__':unittest.main()
