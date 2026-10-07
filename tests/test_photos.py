from test_sharing import api
import unittest
from unittest.mock import patch

class Photos(unittest.TestCase):
 def setUp(self):self.data={'items':[]}
 def post(self,key,note=''):return api.change(self.data,'/api/photos',{'_photo_key':key,'_note':note})
 def test_first_photo_creates_plain_item(self):
  out=self.post('photos/a.jpg')
  item=self.data['items'][0]
  self.assertEqual(out['id'],item['id']);self.assertEqual(item['image_key'],'photos/a.jpg')
  self.assertNotIn('entries',item);self.assertEqual(item['kind'],'photo');self.assertEqual(item['status'],'queued')
 def test_second_photo_within_window_merges_into_entries(self):
  self.post('photos/a.jpg')
  self.post('photos/b.jpg')
  self.assertEqual(len(self.data['items']),1)
  item=self.data['items'][0]
  self.assertEqual(item['entries'],[{'image_key':'photos/a.jpg'},{'image_key':'photos/b.jpg'}])
  self.assertEqual(item['image_key'],'photos/a.jpg')
 def test_three_photos_merge_into_one_item_in_order(self):
  self.post('photos/a.jpg');self.post('photos/b.jpg');self.post('photos/c.jpg')
  self.assertEqual(len(self.data['items']),1)
  keys=[e['image_key'] for e in self.data['items'][0]['entries']]
  self.assertEqual(keys,['photos/a.jpg','photos/b.jpg','photos/c.jpg'])
 def test_photo_outside_window_starts_new_item(self):
  self.post('photos/a.jpg')
  self.data['items'][0]['created']-=30
  self.post('photos/b.jpg')
  self.assertEqual(len(self.data['items']),2)
 def test_merge_requeues_and_bumps_revision(self):
  self.post('photos/a.jpg')
  item=self.data['items'][0]
  item['status']='ready';item['revision']=5;item['error']='old'
  self.post('photos/b.jpg')
  self.assertEqual(item['status'],'queued');self.assertEqual(item['error'],'');self.assertEqual(item['revision'],6)
 def test_deleted_recent_photo_not_merged_into(self):
  self.post('photos/a.jpg')
  self.data['items'][0]['deleted']=True
  self.post('photos/b.jpg')
  self.assertEqual(len(self.data['items']),2)
 def test_entry_cap_at_ten_starts_new_item(self):
  self.post('photos/0.jpg')
  for i in range(1,10):self.post(f'photos/{i}.jpg')
  self.assertEqual(len(self.data['items'][0]['entries']),10)
  self.post('photos/overflow.jpg')
  self.assertEqual(len(self.data['items']),2)
 def test_visible_resolves_entries_with_signed_urls(self):
  self.post('photos/a.jpg');self.post('photos/b.jpg')
  with patch.object(api,'photo_url',side_effect=lambda key:'https://signed/'+key):
   vis=api.visible(self.data['items'][0])
  self.assertEqual(vis['kind'],'photo')
  self.assertEqual(vis['entries'],[{'thumbnail':'https://signed/photos/a.jpg'},{'thumbnail':'https://signed/photos/b.jpg'}])
if __name__=='__main__':unittest.main()
