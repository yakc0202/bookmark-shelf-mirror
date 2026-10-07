from test_sharing import api
import unittest

class MergePhotos(unittest.TestCase):
 def setUp(self):self.data={'items':[]}
 def photo_item(self,id,**extra):
  item=dict(id=id,url='',title='사진 '+id,summary='',folder='f',tags='[]',thumbnail='',
   status='ready',source='사진',note='',created=1,error='',revision=1,deleted=False,
   kind='photo',image_key='photos/'+id+'.jpg')
  item.update(extra)
  self.data['items'].append(item)
  return item
 def test_merge_combines_single_images_into_entries(self):
  self.photo_item('a');self.photo_item('b')
  out=api.change(self.data,'/api/items/merge-photos',{'id':'a','with':'b'})
  self.assertEqual(out['entries'],[{'image_key':'photos/a.jpg'},{'image_key':'photos/b.jpg'}])
  a=next(x for x in self.data['items'] if x['id']=='a')
  b=next(x for x in self.data['items'] if x['id']=='b')
  self.assertEqual(a['entries'],[{'image_key':'photos/a.jpg'},{'image_key':'photos/b.jpg'}])
  self.assertTrue(b['deleted'])
 def test_merge_preserves_existing_entries_on_both_sides(self):
  self.photo_item('a',entries=[{'image_key':'photos/a.jpg'},{'image_key':'photos/a2.jpg'}])
  self.photo_item('b',entries=[{'image_key':'photos/b.jpg'},{'image_key':'photos/b2.jpg'}])
  out=api.change(self.data,'/api/items/merge-photos',{'id':'a','with':'b'})
  self.assertEqual(len(out['entries']),4)
 def test_rejects_non_photo_kind(self):
  self.photo_item('a')
  self.data['items'].append(dict(id='c',url='https://x.test',title='t',summary='',folder='f',tags='[]',
   thumbnail='',status='ready',source='',note='',created=1,error='',revision=1,deleted=False))
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/items/merge-photos',{'id':'a','with':'c'})
 def test_rejects_same_item(self):
  self.photo_item('a')
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/items/merge-photos',{'id':'a','with':'a'})
 def test_rejects_deleted_item(self):
  self.photo_item('a');self.photo_item('b',deleted=True)
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/items/merge-photos',{'id':'a','with':'b'})
 def test_rejects_over_ten_entries(self):
  self.photo_item('a',entries=[{'image_key':f'photos/{i}.jpg'} for i in range(6)])
  self.photo_item('b',entries=[{'image_key':f'photos/{i}.jpg'} for i in range(6)])
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/items/merge-photos',{'id':'a','with':'b'})
if __name__=='__main__':unittest.main()
