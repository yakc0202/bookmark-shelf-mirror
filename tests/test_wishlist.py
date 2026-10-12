from test_sharing import api
import unittest

def save(data, **body):
 return api.change(data, '/api/wishlist/save', body)

class Wishlist(unittest.TestCase):
 def setUp(self): self.data = {'items': []}
 def test_add_edit_buy_delete(self):
  w = save(self.data, title=' 에어팟 ', price=259000, url='https://shop.test/a')
  self.assertEqual((w['title'], w['price'], w['bought'], w['bought_at']), ('에어팟', 259000, False, 0))
  b = save(self.data, id=w['id'], title='에어팟', price=259000, bought=True)
  self.assertTrue(b['bought']); self.assertGreater(b['bought_at'], 0)
  again = save(self.data, id=w['id'], title='에어팟 프로', price=259000, bought=True)
  self.assertEqual(again['bought_at'], b['bought_at'])  # 이름만 고쳐도 산 날은 그대로
  self.assertEqual(len(self.data['wishlist']), 1)
  api.change(self.data, '/api/wishlist/delete', {'id': w['id']})
  self.assertEqual(self.data['wishlist'], [])
 def test_from_shelf_card(self):
  w = save(self.data, title='러닝화', url='https://shop.test/r', item_id='abc', thumbnail='https://img.test/r.jpg')
  self.assertEqual((w['item_id'], w['thumbnail']), ('abc', 'https://img.test/r.jpg'))
  w = save(self.data, id=w['id'], title='러닝화', price=129000)
  self.assertEqual(w['item_id'], 'abc')  # 수정해도 연결 유지
 def test_validation(self):
  for bad in ({'title': ''}, {'title': 'x', 'price': -1}, {'title': 'x', 'price': '1000'}, {'title': 'x', 'url': 'javascript:alert(1)'}):
   with self.assertRaises(api.Problem): save(self.data, **bad)
  with self.assertRaises(api.Problem): save(self.data, id='없음', title='x')

class PassUsed(unittest.TestCase):
 def test_used_count_saved(self):
  data = {'items': []}
  p = api.change(data, '/api/schedule/save', {'kind': 'passes', 'title': '주 2회', 'total': 8, 'used': 1, 'expires': ''})
  self.assertEqual(p['used'], 1)
  p = api.change(data, '/api/schedule/save', {'kind': 'passes', 'id': p['id'], 'title': '주 2회', 'total': 8, 'expires': ''})
  self.assertEqual(p['used'], 1)  # 화면에서 수정해도(used 없이 보내도) 임의 차감은 유지
  q = api.change(data, '/api/schedule/save', {'kind': 'passes', 'title': '새 이용권', 'total': 8, 'expires': ''})
  self.assertEqual(q['used'], 0)
  with self.assertRaises(api.Problem):
   api.change(data, '/api/schedule/save', {'kind': 'passes', 'title': 'x', 'total': 8, 'used': -1})



class AddByLinkOrPhoto(unittest.TestCase):
 def test_link_uses_preview(self):
  data = {'items': []}
  w = api.change(data, '/api/wishlist/add', {'_url': 'https://shop.test/p/1', '_thumbnail': 'https://img.test/a.jpg', '_preview_title': '맘앤온 애엽즙'})
  self.assertEqual((w['title'], w['url'], w['thumbnail'], w['price']), ('맘앤온 애엽즙', 'https://shop.test/p/1', 'https://img.test/a.jpg', 0))
  again = api.change(data, '/api/wishlist/add', {'_url': 'https://shop.test/p/1', '_thumbnail': '', '_preview_title': ''})
  self.assertEqual((again['id'], len(data['wishlist'])), (w['id'], 1))  # 같은 링크는 한 번만

 def test_link_without_preview_uses_host(self):
  w = api.change({'items': []}, '/api/wishlist/add', {'_url': 'https://shop.test/p/2', '_thumbnail': 'javascript:x', '_preview_title': ''})
  self.assertEqual((w['title'], w['thumbnail']), ('shop.test', ''))


 def test_nothing(self):
  with self.assertRaises(api.Problem): api.change({'items': []}, '/api/wishlist/add', {})

class PhotoImport(unittest.TestCase):
 def run_job(self, data, result):
  job = api.change(data, '/worker/claim', {})['item']
  self.assertEqual(job['kind'], 'wish-import')
  api.change(data, '/worker/complete', {'kind': 'wish-import', 'id': job['id'], 'lease': job['lease'], 'revision': job['revision'], 'result': result})
  return data['wish_jobs'][-1]

 def test_items_from_photo(self):
  data = {'items': [], 'wishlist': [{'id': 'x', 'created': 1, 'title': '맘앤온 애엽즙', 'price': 0, 'url': '', 'note': '', 'bought': False, 'bought_at': 0}]}
  out = api.change(data, '/api/wishlist/import', {'_photo_key': 'photos/cart.jpg'})
  self.assertIn('위시리스트', out['message'])
  job = self.run_job(data, {'status': 'ready', 'items': [
   {'title': '러닝화 젤카야노', 'price': 129000, 'note': '260'}, {'title': ' 맘앤온  애엽즙', 'price': 0, 'note': ''},
   {'title': '니트', 'price': '9000', 'note': ''}, {'title': '', 'price': 0, 'note': ''}]})
  added = data['wishlist'][1:]
  self.assertEqual([(w['title'], w['price'], w['note']) for w in added], [('러닝화 젤카야노', 129000, '260'), ('니트', 0, '')])
  self.assertTrue(all(w['thumbnail'].endswith('/photos/cart.jpg') for w in added))
  self.assertEqual((job['status'], job['added']), ('ready', 2))  # 이미 있는 이름은 빼고, 빈 이름은 무시

 def test_nothing_found_and_busy(self):
  data = {'items': []}
  api.change(data, '/api/wishlist/import', {'_photo_key': 'photos/a.jpg'})
  job = self.run_job(data, {'status': 'ready', 'items': []})
  self.assertEqual((job['added'], bool(job['error'])), (0, True))
  api.change(data, '/api/wishlist/import', {'_photo_key': 'photos/b.jpg'})
  job = self.run_job(data, {'status': 'ai_waiting', 'error': '바쁨'})
  self.assertEqual(job['status'], 'ai_waiting')

if __name__ == '__main__':
 unittest.main()
