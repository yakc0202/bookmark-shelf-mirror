from test_sharing import api
import unittest

def card(i, url, **kw):
 return {'id': i, 'url': url, 'title': '제목 ' + i, 'folder': 'f', 'status': 'ready', 'created': 1, 'revision': 1, 'deleted': False, **kw}

class CollectionMove(unittest.TestCase):
 def setUp(self):
  self.col = {'id': 'c', 'url': '', 'title': '모음', 'kind': 'collection', 'entries': [{'kind': 'link', 'url': 'https://old.test/1', 'title': '기존'}],
              'folder': '모음', 'status': 'ready', 'created': 1, 'revision': 1, 'deleted': False}
  self.data = {'items': [self.col], 'shares': {}}
 def test_move_adds_link_and_thread_posts_and_hides_card_from_home(self):
  self.data['items'].append(card('a', 'https://a.test/1', thumbnail='https://img.test/a.jpg',
                                 entries=[{'kind': 'link', 'url': 'https://a.test/2', 'title': '둘째'}, {'image_key': 'photos/x.jpg'}]))
  self.data['shares']['s'] = {'item_id': 'a'}
  out = api.change(self.data, '/api/collections/move', {'id': 'c', 'item_id': 'a'})
  self.assertEqual((out['start'], out['count']), (1, 2))
  self.assertEqual([e['url'] for e in self.col['entries']], ['https://old.test/1', 'https://a.test/1', 'https://a.test/2'])
  self.assertEqual(self.col['entries'][1]['thumbnail'], 'https://img.test/a.jpg')
  moved = self.data['items'][1]
  self.assertTrue(moved['deleted']); self.assertEqual(self.data['shares'], {})
 def test_link_already_in_collection_is_not_duplicated(self):
  self.data['items'].append(card('a', 'https://old.test/1'))
  out = api.change(self.data, '/api/collections/move', {'id': 'c', 'item_id': 'a'})
  self.assertEqual(out['count'], 0); self.assertEqual(len(self.col['entries']), 1)
 def test_unmove_restores_card_and_removes_entries(self):
  self.data['items'].append(card('a', 'https://a.test/1'))
  out = api.change(self.data, '/api/collections/move', {'id': 'c', 'item_id': 'a'})
  api.change(self.data, '/api/collections/unmove', {'id': 'c', 'item_id': 'a', 'start': out['start'], 'count': out['count']})
  self.assertFalse(self.data['items'][1]['deleted'])
  self.assertEqual([e['url'] for e in self.col['entries']], ['https://old.test/1'])
 def test_unmove_refuses_when_collection_changed(self):
  self.data['items'].append(card('a', 'https://a.test/1'))
  out = api.change(self.data, '/api/collections/move', {'id': 'c', 'item_id': 'a'})
  self.col['entries'].pop()
  with self.assertRaises(api.Problem):
   api.change(self.data, '/api/collections/unmove', {'id': 'c', 'item_id': 'a', 'start': out['start'], 'count': out['count']})
 def test_cannot_move_into_non_collection_or_move_photo(self):
  self.data['items'] += [card('a', 'https://a.test/1'), card('b', 'https://b.test/1'), card('p', '', kind='photo')]
  with self.assertRaises(api.Problem): api.change(self.data, '/api/collections/move', {'id': 'b', 'item_id': 'a'})
  with self.assertRaises(api.Problem): api.change(self.data, '/api/collections/move', {'id': 'c', 'item_id': 'p'})
if __name__ == '__main__': unittest.main()
