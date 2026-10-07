from test_sharing import api
import unittest
from unittest.mock import patch

class AttachPhoto(unittest.TestCase):
 def setUp(self):self.data={'items':[]}
 def link_item(self,**extra):
  item=dict(id='a',url='https://x.test',title='t',summary='',folder='f',tags='[]',thumbnail='',
   status='ready',source='',note='',created=1,error='',revision=1,deleted=False)
  item.update(extra)
  self.data['items'].append(item)
  return item
 def test_attach_to_plain_link_creates_entries(self):
  self.link_item()
  out=api.change(self.data,'/api/attach-photo',{'id':'a','_photo_key':'photos/x.jpg'})
  self.assertEqual(out['entries'],[{'image_key':'photos/x.jpg'}])
  self.assertEqual(self.data['items'][0]['entries'],[{'image_key':'photos/x.jpg'}])
 def test_attach_to_photo_item_preserves_original_image(self):
  self.link_item(kind='photo',image_key='photos/orig.jpg')
  out=api.change(self.data,'/api/attach-photo',{'id':'a','_photo_key':'photos/new.jpg'})
  self.assertEqual(out['entries'],[{'image_key':'photos/orig.jpg'},{'image_key':'photos/new.jpg'}])
 def test_rejects_deleted_item(self):
  self.link_item(deleted=True)
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/attach-photo',{'id':'a','_photo_key':'photos/x.jpg'})
 def test_rejects_at_ten_entries(self):
  self.link_item(entries=[{'image_key':f'photos/{i}.jpg'} for i in range(10)])
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/attach-photo',{'id':'a','_photo_key':'photos/x.jpg'})
 def test_visible_resolves_attached_photo_on_link_item(self):
  self.link_item(entries=[{'image_key':'photos/a.jpg'}])
  with patch.object(api,'photo_url',side_effect=lambda key:'https://signed/'+key):
   vis=api.visible(self.data['items'][0])
  self.assertNotEqual(vis.get('kind'),'photo')
  self.assertEqual(vis['entries'],[{'thumbnail':'https://signed/photos/a.jpg'}])
if __name__=='__main__':unittest.main()
