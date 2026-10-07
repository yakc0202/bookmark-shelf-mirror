from test_sharing import api
import json,unittest
from unittest.mock import patch,MagicMock

class ItemMerge(unittest.TestCase):
 def setUp(self):self.data={'items':[]}
 def post(self,url,note=''):return api.change(self.data,'/api/items',{'url':url,'note':note})
 def test_first_link_creates_plain_item(self):
  out=self.post('https://a.test/one')
  item=self.data['items'][0]
  self.assertEqual(out['id'],item['id']);self.assertNotIn('entries',item)
 def test_second_link_within_window_merges_as_entry(self):
  self.post('https://a.test/thread/one')
  out=self.post('https://a.test/thread/two')
  self.assertEqual(len(self.data['items']),1)
  item=self.data['items'][0]
  self.assertEqual(out['id'],item['id'])
  self.assertEqual(item['entries'],[{'kind':'link','url':'https://a.test/thread/two','title':'a.test'}])
 def test_merge_into_card_being_processed_requeues_it(self):
  self.post('https://a.test/thread/one')
  first=api.change(self.data,'/worker/claim',{})['item']
  self.assertEqual(self.data['items'][0]['status'],'processing')
  self.post('https://a.test/thread/two')
  item=self.data['items'][0]
  self.assertEqual(item['status'],'queued')
  done={'id':first['id'],'lease':first['lease'],'revision':first['revision'],'result':{'status':'ready','title':'t'}}
  with self.assertRaises(api.Problem):api.change(self.data,'/worker/complete',done)
  again=api.change(self.data,'/worker/claim',{})['item']
  self.assertEqual(again['id'],first['id']);self.assertEqual(len(again['entries']),1)
  api.change(self.data,'/worker/complete',{**done,'lease':again['lease'],'revision':again['revision']})
  self.assertEqual(self.data['items'][0]['status'],'ready')
 def test_link_outside_window_starts_new_item(self):
  self.post('https://a.test/thread/one')
  self.data['items'][0]['created']-=30
  self.post('https://a.test/thread/two')
  self.assertEqual(len(self.data['items']),2)
 def test_different_host_does_not_merge(self):
  self.post('https://a.test/one')
  self.post('https://b.test/two')
  self.assertEqual(len(self.data['items']),2)
 def test_same_host_different_section_does_not_merge(self):
  self.post('https://a.test/userA/status/1')
  self.post('https://a.test/userB/status/2')
  self.assertEqual(len(self.data['items']),2)
 def test_resharing_url_already_inside_a_collection_is_recognized_as_duplicate(self):
  self.post('https://a.test/one')
  api.change(self.data,'/api/items/to-collection',{'id':self.data['items'][0]['id']})
  self.assertEqual(self.data['items'][0]['url'],'')
  out=self.post('https://a.test/one')
  self.assertEqual(len(self.data['items']),1)
  self.assertEqual(out['id'],self.data['items'][0]['id'])
 def test_resharing_url_from_a_deleted_collection_restores_it(self):
  self.post('https://a.test/one')
  item_id=self.data['items'][0]['id']
  api.change(self.data,'/api/items/to-collection',{'id':item_id})
  api.change(self.data,'/api/delete',{'id':item_id})
  self.post('https://a.test/one')
  self.assertEqual(len(self.data['items']),1)
  self.assertFalse(self.data['items'][0]['deleted'])
 def test_does_not_merge_into_photo_item(self):
  self.data['items'].append({'id':'p','url':'','title':'사진','folder':'f','status':'ready','created':__import__('time').time(),
   'revision':1,'deleted':False,'kind':'photo','image_key':'photos/a.jpg'})
  self.post('https://a.test/one')
  self.assertEqual(len(self.data['items']),2)
 def test_does_not_merge_into_collection_item(self):
  self.data['items'].append({'id':'c','url':'','title':'모음','folder':'f','status':'ready','created':__import__('time').time(),
   'revision':1,'deleted':False,'kind':'collection','entries':[]})
  self.post('https://a.test/one')
  self.assertEqual(len(self.data['items']),2)
 def test_does_not_merge_into_deleted_item(self):
  self.post('https://a.test/one')
  self.data['items'][0]['deleted']=True
  self.post('https://b.test/two')
  self.assertEqual(len(self.data['items']),2)
 def test_tweet_entry_title_uses_oembed_not_repeated_account_name(self):
  oembed_body=json.dumps({'html':'<blockquote class="twitter-tweet"><p>실제 트윗 본문</p>&mdash; 솔이 (@soly) <a href="x">date</a></blockquote>'}).encode()
  og_body=b'<html><head><meta property="og:title" content="\xec\x86\x94\xec\x9d\xb4 (@soly) / X"></head></html>'
  responses=[MagicMock(**{'read.return_value':og_body}),MagicMock(**{'read.return_value':oembed_body})]
  for r in responses:r.__enter__=lambda s:s;r.__exit__=lambda s,*a:False
  with patch('urllib.request.urlopen',side_effect=responses):
   self.post('https://twitter.com/soly/status/1')
   self.post('https://twitter.com/soly/status/2')
  item=self.data['items'][0]
  self.assertEqual(item['entries'][0]['title'],'실제 트윗 본문')
 def test_tweet_entry_title_strips_trailing_media_link(self):
  oembed_body=json.dumps({'html':'<blockquote class="twitter-tweet"><p>맛집 추천 pic.twitter.com/abc123</p>&mdash; 솔이 (@soly) <a href="x">date</a></blockquote>'}).encode()
  og_body=b'<html></html>'
  responses=[MagicMock(**{'read.return_value':og_body}),MagicMock(**{'read.return_value':oembed_body})]
  for r in responses:r.__enter__=lambda s:s;r.__exit__=lambda s,*a:False
  with patch('urllib.request.urlopen',side_effect=responses):
   self.post('https://twitter.com/soly/status/1')
   self.post('https://twitter.com/soly/status/2')
  item=self.data['items'][0]
  self.assertEqual(item['entries'][0]['title'],'맛집 추천')
 def test_youtube_links_skip_classification_and_go_to_watch_later(self):
  for url in ['https://www.youtube.com/watch?v=abc','https://youtu.be/abc','https://m.youtube.com/watch?v=abc','https://www.youtube.com/shorts/abc']:
   data={'items':[]}
   api.change(data,'/api/items',{'url':url})
   item=data['items'][0]
   self.assertEqual(item['status'],'ready')
   self.assertEqual(item['folder'],'나중에 다시 보기')
if __name__=='__main__':unittest.main()
