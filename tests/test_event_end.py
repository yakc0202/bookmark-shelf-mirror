from test_sharing import api
import time, unittest

def card(i, **kw):
 return {'id': i, 'url': 'https://e.test/' + i, 'title': i, 'folder': '서울(빵집)', 'status': 'ready', 'created': 1, 'revision': 1, 'deleted': False, **kw}

class EventEnd(unittest.TestCase):
 def test_complete_stores_valid_end_date_only(self):
  data = {'items': [card('a', status='queued')]}
  job = api.change(data, '/worker/claim', {})['item']
  api.change(data, '/worker/complete', {'id': 'a', 'lease': job['lease'], 'revision': job['revision'], 'result': {'status': 'ready', 'ends_on': '2026-10-15'}})
  self.assertEqual(data['items'][0]['ends_on'], '2026-10-15')
  data['items'][0]['status'] = 'queued'
  job = api.change(data, '/worker/claim', {})['item']
  api.change(data, '/worker/complete', {'id': 'a', 'lease': job['lease'], 'revision': job['revision'], 'result': {'status': 'ready', 'ends_on': '다음 주'}})
  self.assertNotIn('ends_on', data['items'][0])
 def test_claim_moves_ended_events_once_and_hides_folder_from_ai(self):
  today = time.strftime('%Y-%m-%d', time.gmtime(time.time() + 9 * 3600))
  data = {'items': [card('old', ends_on='2000-01-01'), card('now', ends_on=today), card('none'), card('q', status='queued')]}
  out = api.change(data, '/worker/claim', {})
  old = data['items'][0]
  self.assertEqual((old['folder'], old['folder_before_end'], old['event_ended']), ('지난 행사', '서울(빵집)', True))
  self.assertEqual(data['items'][1]['folder'], '서울(빵집)')
  self.assertNotIn('지난 행사', out['folders'])
  old['folder'] = '서울(빵집)'
  api.change(data, '/worker/claim', {})
  self.assertEqual(old['folder'], '서울(빵집)')
 def test_public_view_includes_end_date(self):
  self.assertEqual(api.visible(card('a', ends_on='2026-10-15'))['ends_on'], '2026-10-15')
if __name__ == '__main__': unittest.main()
