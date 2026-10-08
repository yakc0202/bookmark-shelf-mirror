from test_sharing import api
import unittest

def claim(data):
 return api.change(data, '/worker/claim', {})['item']

def complete(data, job, result):
 return api.change(data, '/worker/complete', {'kind': 'schedule-import', 'id': job['id'], 'lease': job['lease'], 'revision': job['revision'], 'result': result})

def booking(title, date='2026-10-09', start='19:00', end='19:50', status='booked'):
 return {'title': title, 'date': date, 'start': start, 'end': end, 'status': status}

class ScheduleImport(unittest.TestCase):
 def setUp(self):
  self.data = {'items': []}
  self.ballet = api.change(self.data, '/api/schedule/save', {'kind': 'passes', 'title': '발레 10회', 'total': 10, 'expires': ''})
 def upload(self):
  api.change(self.data, '/api/schedule/import', {'_photo_key': 'photos/a.jpg'})
  return claim(self.data)
 def test_capture_job_is_claimed_and_merged(self):
  job = self.upload()
  self.assertEqual((job['kind'], job['image_key']), ('schedule-import', 'photos/a.jpg'))
  complete(self.data, job, {'status': 'ready', 'bookings': [booking('발레'), booking('발레', start='20:00', end='21:00', status='waiting'), booking('요가', start='25:00')]})
  b = self.data['schedule']['bookings']
  self.assertEqual([(x['start'], x['status'], x['pass_id']) for x in b], [('19:00', 'booked', self.ballet['id']), ('20:00', 'waiting', '')])
  j = self.data['schedule']['jobs'][0]
  self.assertEqual((j['status'], j['added'], j['updated']), ('ready', 2, 0))
 def test_same_class_from_second_capture_updates_status(self):
  complete(self.data, self.upload(), {'status': 'ready', 'bookings': [booking('발레', status='waiting')]})
  complete(self.data, self.upload(), {'status': 'ready', 'bookings': [booking(' 발 레', status='booked')]})
  b = self.data['schedule']['bookings']
  self.assertEqual(len(b), 1); self.assertEqual(b[0]['status'], 'booked')
  self.assertEqual(self.data['schedule']['jobs'][1]['updated'], 1)
 def test_stale_or_busy(self):
  job = self.upload()
  with self.assertRaises(api.Problem): complete(self.data, {**job, 'lease': 'x'}, {'status': 'ready', 'bookings': []})
  complete(self.data, job, {'status': 'ai_waiting', 'error': '바쁨'})
  self.assertEqual(self.data['schedule']['jobs'][0]['status'], 'ai_waiting')
  self.assertIsNone(claim(self.data))
 def test_manual_booking_status(self):
  b = api.change(self.data, '/api/schedule/save', {'kind': 'bookings', **booking('발레', status='waiting')})
  self.assertEqual(b['status'], 'waiting')
  plain = {'kind': 'bookings', 'title': '발레', 'date': '2026-10-09', 'start': '19:00', 'end': '20:00'}
  self.assertEqual(api.change(self.data, '/api/schedule/save', plain)['status'], 'booked')
  with self.assertRaises(api.Problem): api.change(self.data, '/api/schedule/save', {'kind': 'bookings', **booking('발레', status='done')})
if __name__ == '__main__': unittest.main()
