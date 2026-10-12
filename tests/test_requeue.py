"""사진·링크가 덧붙으면 카드를 다시 정리 대기로 돌리고, 워커가 링크 카드에 붙은 사진도 받는지."""
from test_sharing import api
import hashlib, json, os, unittest
from unittest.mock import patch

def link(id, **extra):
 x = dict(id=id, url='https://blog.test/' + id, title='t', summary='s', folder='f', tags='[]', thumbnail='', status='ready',
          source='', note='', created=1, error='', revision=1, deleted=False)
 x.update(extra); return x

def photo(id, **extra):
 return link(id, url='', kind='photo', image_key='photos/' + id + '.jpg', **extra)

class Requeue(unittest.TestCase):
 def test_attach_photo_requeues(self):
  data = {'items': [link('a')]}
  out = api.change(data, '/api/attach-photo', {'id': 'a', '_photo_key': 'photos/n.jpg'})
  a = data['items'][0]
  self.assertEqual((a['status'], a['revision']), ('queued', 2)); self.assertIn('다시 정리', out['message'])

 def test_merge_into_link_or_photo_requeues(self):
  data = {'items': [link('a'), photo('p'), photo('q')]}
  api.change(data, '/api/items/merge-photos', {'id': 'a', 'with': 'p'})
  self.assertEqual(data['items'][0]['status'], 'queued')

 @patch.object(api, 'fetch_link_preview', return_value=('', '다음 글'))
 def test_thread_entry_requeues_ready_card(self, _):
  data = {'items': []}
  api.change(data, '/api/items', {'url': 'https://x.com/me/status/1'})
  data['items'][0]['status'] = 'ready'
  api.change(data, '/api/items', {'url': 'https://x.com/me/status/2'})
  self.assertEqual(data['items'][0]['status'], 'queued')

 def test_collection_is_not_requeued(self):
  data = {'items': [link('c', url='', kind='collection', entries=[])]}
  api.requeue(data['items'][0])
  self.assertEqual(data['items'][0]['status'], 'ready')

class ClaimPhotos(unittest.TestCase):
 def claim(self, data):
  os.environ['WORKER_TOKEN_HASH'] = hashlib.sha256(b'w').hexdigest()
  with patch.object(api, 'transact', lambda fn: fn(data)):
   r = api.handler({'rawPath': '/worker/claim', 'requestContext': {'http': {'method': 'POST'}},
                    'headers': {'authorization': 'Bearer w'}, 'body': '{}'}, None)
  return json.loads(r['body'])['item']

 def test_link_card_with_attached_photos_sends_them(self):
  item = self.claim({'items': [link('a', status='queued', entries=[{'kind': 'link', 'url': 'https://blog.test/b'}, {'image_key': 'photos/x.jpg'}])]})
  self.assertTrue(item['image_download'].endswith('/photos/x.jpg'))
  self.assertEqual(len(item['entries_download']), 1)

 def test_plain_link_has_no_photos(self):
  item = self.claim({'items': [link('a', status='queued')]})
  self.assertNotIn('image_download', item)

 def test_photo_card_sends_all_photos(self):
  item = self.claim({'items': [photo('p', status='queued', entries=[{'image_key': 'photos/p.jpg'}, {'image_key': 'photos/p2.jpg'}])]})
  self.assertEqual(len(item['entries_download']), 2)

if __name__ == '__main__':
 unittest.main()
