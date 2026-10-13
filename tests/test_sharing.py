import importlib.util, sys, types, unittest, copy, os
from pathlib import Path
sys.modules['boto3']=types.SimpleNamespace(client=lambda *a,**kw:None)
sys.modules['botocore']=types.ModuleType('botocore')
sys.modules['botocore.config']=types.SimpleNamespace(Config=lambda **kw:None)
sys.modules['botocore.exceptions']=types.SimpleNamespace(ClientError=type('ClientError',(Exception,),{}))
os.environ['DATA_BUCKET']='test'
spec=importlib.util.spec_from_file_location('api',Path(__file__).resolve().parents[1]/'cloud/api.py')
api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
class Sharing(unittest.TestCase):
 def setUp(self):
  self.data={'items':[{'id':'one','url':'https://example.com','title':'<script>bad</script>','folder':'야구','summary':'safe summary','note':'PRIVATE NOTE','status':'ready','created':1},{'id':'two','url':'https://example.org','title':'OTHER PRIVATE TITLE'}]}
 def share(self):return api.change(self.data,'/api/share',{'id':'one'})['token']
 def test_only_selected_safe_fields_in_public_page(self):
  token=self.share();page=api.shared_page(self.data,token)['body']
  self.assertEqual(len(token),43);self.assertNotIn(token,page);self.assertIn('&lt;script&gt;',page)
  for secret in ('PRIVATE NOTE','OTHER PRIVATE TITLE','<script>'):self.assertNotIn(secret,page)
 def test_reuse_revoke_and_delete_restore(self):
  first=self.share();second=self.share()
  self.assertEqual(first,second)
  api.shared_page(self.data,first)
  api.change(self.data,'/api/unshare',{'id':'one'})
  with self.assertRaises(api.Problem):api.shared_page(self.data,first)
  third=self.share()
  self.assertNotEqual(first,third)
  api.change(self.data,'/api/delete',{'id':'one'});api.change(self.data,'/api/restore',{'id':'one'})
  with self.assertRaises(api.Problem):api.shared_page(self.data,third)
 def test_unknown_token(self):
  for token in ('','../data/cards.json','a'*43):
   with self.assertRaises(api.Problem):api.shared_page(self.data,token)
 def test_collection_shares_all_entries(self):
  self.data['items'].append({'id':'col','kind':'collection','url':'','title':'여행 모음','topic':'오사카 여행','folder':'여행','summary':'가볼 곳','note':'PRIVATE NOTE','status':'ready','created':2,
   'entries':[{'kind':'link','url':'https://a.example/x','title':'<b>맛집</b>','thumbnail':'https://img.example/a.jpg'},{'kind':'link','url':'javascript:alert(1)','title':'나쁜 링크'},{'image_key':'photos/p.jpg'}]})
  out=api.change(self.data,'/api/share',{'id':'col'});self.assertIn('모음을',out['message'])
  page=api.shared_page(self.data,out['token'])['body']
  for want in ('오사카 여행','공유받은 모음 · 항목 2개','https://a.example/x','&lt;b&gt;맛집&lt;/b&gt;','a.example','/photos/p.jpg','가볼 곳'):self.assertIn(want,page)
  for bad in ('javascript:','나쁜 링크','PRIVATE NOTE','원본 보기'):self.assertNotIn(bad,page)
if __name__=='__main__':unittest.main()
