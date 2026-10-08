from test_sharing import api
import unittest

def save(data, kind, **kw):
 return api.change(data, '/api/schedule/save', {'kind': kind, **kw})

class Schedule(unittest.TestCase):
 def setUp(self): self.data = {'items': []}
 def test_todo_create_update_and_done_time(self):
  t = save(self.data, 'todos', title='보고서', minutes=60, due='2026-10-10')
  self.assertEqual((t['minutes'], t['due'], t['done']), (60, '2026-10-10', False))
  t2 = save(self.data, 'todos', id=t['id'], title='보고서', minutes=60, due='', done=True)
  self.assertTrue(t2['done']); self.assertGreater(t2['done_at'], 0); self.assertEqual(t2['created'], t['created'])
  self.assertEqual(len(self.data['schedule']['todos']), 1)
 def test_todo_defaults_and_validation(self):
  self.assertEqual(save(self.data, 'todos', title='짧은 일')['minutes'], 30)
  for bad in ({'title': ''}, {'title': 'x', 'minutes': 0}, {'title': 'x', 'due': '10월'}):
   with self.assertRaises(api.Problem): save(self.data, 'todos', **bad)
 def test_event_and_routine_times(self):
  e = save(self.data, 'events', title='치과', date='2026-10-09', start='14:00', end='15:00')
  self.assertEqual(e['start'], '14:00')
  with self.assertRaises(api.Problem): save(self.data, 'events', title='x', date='2026-10-09', start='15:00', end='14:00')
  r = save(self.data, 'routines', title='점심', start='12:00', end='13:00', days=[5, 1, 1], type='meal')
  self.assertEqual((r['days'], r['type']), ([1, 5], 'meal'))
  with self.assertRaises(api.Problem): save(self.data, 'routines', title='x', start='09:00', end='10:00', days=[])
 def test_gym_pass_and_bookings(self):
  p = save(self.data, 'passes', title='필라테스 10회', total=10, expires='2026-12-31')
  b = save(self.data, 'bookings', title='필라테스', date='2026-10-09', start='19:00', end='19:50', pass_id=p['id'])
  self.assertEqual(b['pass_id'], p['id'])
  with self.assertRaises(api.Problem): save(self.data, 'bookings', title='x', date='2026-10-09', start='19:00', end='19:50', pass_id='없음')
  api.change(self.data, '/api/schedule/delete', {'kind': 'passes', 'id': p['id']})
  self.assertEqual(self.data['schedule']['bookings'][0]['pass_id'], '')
 def test_settings_and_unknown_kind(self):
  self.assertEqual(save(self.data, 'settings', day_start='07:30', day_end='24:00'), {'day_start': '07:30', 'day_end': '24:00'})
  with self.assertRaises(api.Problem): save(self.data, 'settings', day_start='25:00', day_end='24:00')
  with self.assertRaises(api.Problem): save(self.data, 'memos', title='x')
 def test_delete_missing_is_404(self):
  with self.assertRaises(api.Problem): api.change(self.data, '/api/schedule/delete', {'kind': 'todos', 'id': 'nope'})
if __name__ == '__main__': unittest.main()
