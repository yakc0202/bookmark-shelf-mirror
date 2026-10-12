from test_sharing import api
import unittest
from unittest.mock import patch

def link(id, url, **extra):
 x = dict(id=id, url=url, title='t-' + id, summary='s', folder='f', tags='[]', thumbnail='', status='ready', source='', note='',
          created=1, error='', revision=1, deleted=False)
 x.update(extra); return x

class Split(unittest.TestCase):
 def test_linked_entries_become_own_cards(self):
  data = {'items': [link('a', 'https://www.threads.com/share/A/', topic='AI', entries=[
   {'kind': 'link', 'url': 'https://www.threads.com/share/B/', 'title': '4. lagging', 'thumbnail': 'https://img/b.jpg'},
   {'image_key': 'photos/p.jpg'}])]}
  out = api.change(data, '/api/items/split', {'id': 'a'})
  self.assertEqual(out['count'], 2)
  a, b = data['items']
  self.assertEqual((a['url'], a['status'], a['entries']), ('https://www.threads.com/share/A/', 'queued', [{'image_key': 'photos/p.jpg'}]))
  self.assertEqual((b['url'], b['title'], b['thumbnail'], b['status']), ('https://www.threads.com/share/B/', '4. lagging', 'https://img/b.jpg', 'queued'))

 def test_collection_becomes_links_and_restores_deleted(self):
  data = {'items': [
   dict(link('c', '', kind='collection', topic='맛집'), entries=[
    {'kind': 'link', 'url': 'https://x.test/1', 'title': '하나'}, {'kind': 'link', 'url': 'https://x.test/2', 'title': '둘'}]),
   link('old', 'https://x.test/2', deleted=True)]}
  out = api.change(data, '/api/items/split', {'id': 'c'})
  c = data['items'][0]
  self.assertNotIn('kind', c); self.assertNotIn('entries', c)
  self.assertEqual((c['url'], c['title'], c['topic']), ('https://x.test/1', '하나', ''))
  self.assertFalse(data['items'][1]['deleted'])  # 이미 있던(지운) 카드는 새로 만들지 않고 되살림
  self.assertEqual((len(data['items']), out['count']), (2, 2))

 def test_nothing_to_split(self):
  data = {'items': [link('a', 'https://x.test/a'), link('p', '', kind='photo', image_key='photos/p.jpg')]}
  for i in ('a', 'p'):
   with self.assertRaises(api.Problem): api.change(data, '/api/items/split', {'id': i})

if __name__ == '__main__':
 unittest.main()
