from test_sharing import api
import unittest

class Collections(unittest.TestCase):
 def setUp(self):self.data={'items':[]}
 def test_create_defaults(self):
  out=api.change(self.data,'/api/collections',{})
  item=self.data['items'][0]
  self.assertEqual(item['kind'],'collection');self.assertEqual(item['title'],'새 모음')
  self.assertEqual(item['folder'],'모음');self.assertEqual(item['entries'],[]);self.assertEqual(item['status'],'ready')
  self.assertEqual(out['id'],item['id'])
 def test_create_with_title_and_folder(self):
  api.change(self.data,'/api/collections',{'title':'다이어리','folder':'기록'})
  item=self.data['items'][0]
  self.assertEqual(item['title'],'다이어리');self.assertEqual(item['folder'],'기록')
 def test_create_with_topic(self):
  api.change(self.data,'/api/collections',{'topic':'제주 여행'})
  self.assertEqual(self.data['items'][0]['topic'],'제주 여행')
 def test_to_collection_stores_topic(self):
  self.data['items'].append({'id':'x','url':'https://a.com','title':'t','folder':'f','status':'ready','created':1,'revision':1,'deleted':False})
  api.change(self.data,'/api/items/to-collection',{'id':'x','topic':'주말 나들이'})
  item=next(i for i in self.data['items'] if i['id']=='x')
  self.assertEqual(item['topic'],'주말 나들이')
 def test_update_topic(self):
  cid=api.change(self.data,'/api/collections',{'topic':'원래 주제'})['id']
  api.change(self.data,'/api/update',{'id':cid,'topic':'새 주제'})
  item=next(i for i in self.data['items'] if i['id']==cid)
  self.assertEqual(item['topic'],'새 주제')
 def test_add_entry_derives_title_from_host(self):
  cid=api.change(self.data,'/api/collections',{})['id']
  out=api.change(self.data,'/api/collections/entries',{'id':cid,'url':'https://example.com/post/1'})
  self.assertEqual(out['entries'][0],{'kind':'link','url':'https://example.com/post/1','title':'example.com'})
 def test_add_entry_custom_title_and_revision_bump(self):
  cid=api.change(self.data,'/api/collections',{})['id']
  api.change(self.data,'/api/collections/entries',{'id':cid,'url':'https://a.com','title':'A글'})
  item=next(x for x in self.data['items'] if x['id']==cid)
  self.assertEqual(item['entries'][0]['title'],'A글');self.assertEqual(item['revision'],2)
 def test_reject_non_http_url(self):
  cid=api.change(self.data,'/api/collections',{})['id']
  with self.assertRaises(api.Problem) as e:
   api.change(self.data,'/api/collections/entries',{'id':cid,'url':'javascript:alert(1)'})
  self.assertEqual(e.exception.status,400)
 def test_remove_entry_by_index(self):
  cid=api.change(self.data,'/api/collections',{})['id']
  api.change(self.data,'/api/collections/entries',{'id':cid,'url':'https://a.com'})
  api.change(self.data,'/api/collections/entries',{'id':cid,'url':'https://b.com'})
  api.change(self.data,'/api/collections/entries/remove',{'id':cid,'index':0})
  item=next(x for x in self.data['items'] if x['id']==cid)
  self.assertEqual(len(item['entries']),1);self.assertEqual(item['entries'][0]['url'],'https://b.com')
 def test_remove_invalid_index_rejected(self):
  cid=api.change(self.data,'/api/collections',{})['id']
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/collections/entries/remove',{'id':cid,'index':5})
 def test_entries_allowed_on_photo_item(self):
  self.data['items'].append({'id':'x','url':'https://a.com','title':'t','folder':'f','status':'ready','created':1,'revision':1,'deleted':False,'kind':'photo','image_key':'photos/a.jpg'})
  out=api.change(self.data,'/api/collections/entries',{'id':'x','url':'https://instagram.com/someone'})
  self.assertEqual(out['entries'],[{'kind':'link','url':'https://instagram.com/someone','title':'instagram.com'}])
 def test_entries_allowed_on_plain_link_item(self):
  self.data['items'].append({'id':'x','url':'https://a.com','title':'t','folder':'f','status':'ready','created':1,'revision':1,'deleted':False})
  out=api.change(self.data,'/api/collections/entries',{'id':'x','url':'https://b.com'})
  self.assertEqual(out['entries'],[{'kind':'link','url':'https://b.com','title':'b.com'}])
 def test_entry_limit(self):
  cid=api.change(self.data,'/api/collections',{})['id']
  item=next(x for x in self.data['items'] if x['id']==cid)
  item['entries']=[{'kind':'link','url':f'https://a.com/{i}','title':'t'} for i in range(50)]
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/collections/entries',{'id':cid,'url':'https://over.com'})
 def test_visible_resolves_link_entries(self):
  cid=api.change(self.data,'/api/collections',{})['id']
  api.change(self.data,'/api/collections/entries',{'id':cid,'url':'https://a.com','title':'A'})
  item=next(x for x in self.data['items'] if x['id']==cid)
  vis=api.visible(item)
  self.assertEqual(vis['kind'],'collection')
  self.assertEqual(vis['entries'],[{'kind':'link','url':'https://a.com','title':'A'}])
if __name__=='__main__':unittest.main()
