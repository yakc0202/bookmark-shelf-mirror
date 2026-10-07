from test_sharing import api
import unittest

class Habits(unittest.TestCase):
 def setUp(self):self.data={}
 def test_create_requires_title_and_duration(self):
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/habits/save',{'title':'','duration_days':30})
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/habits/save',{'title':'A','duration_days':0})
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/habits/save',{'title':'A','duration_days':3651})
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/habits/save',{'title':'A','duration_days':'30'})
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/habits/save',{'title':'A','duration_days':True})
 def test_create_sets_defaults(self):
  h=api.change(self.data,'/api/habits/save',{'title':'A','description':'설명','duration_days':30})
  self.assertEqual(h['duration_days'],30)
  self.assertEqual(h['stamps'],{})
  self.assertIn(h,self.data['habits'])
 def test_edit_preserves_stamps_and_created(self):
  h=api.change(self.data,'/api/habits/save',{'title':'A','duration_days':30})
  api.change(self.data,'/api/habits/stamp',{'id':h['id'],'date':'2026-10-06','stamped':True})
  updated=api.change(self.data,'/api/habits/save',{'id':h['id'],'title':'A2','duration_days':60})
  self.assertEqual(updated['title'],'A2')
  self.assertEqual(updated['duration_days'],60)
  self.assertEqual(updated['created'],h['created'])
  self.assertEqual(updated['stamps'],{'2026-10-06':True})
 def test_stamp_toggle_on_and_off(self):
  h=api.change(self.data,'/api/habits/save',{'title':'A','duration_days':30})
  out=api.change(self.data,'/api/habits/stamp',{'id':h['id'],'date':'2026-10-06','stamped':True})
  self.assertEqual(out['stamps'],{'2026-10-06':True})
  out=api.change(self.data,'/api/habits/stamp',{'id':h['id'],'date':'2026-10-06','stamped':False})
  self.assertEqual(out['stamps'],{})
 def test_stamp_rejects_bad_date_format(self):
  h=api.change(self.data,'/api/habits/save',{'title':'A','duration_days':30})
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/habits/stamp',{'id':h['id'],'date':'not-a-date','stamped':True})
 def test_delete_removes_habit(self):
  h=api.change(self.data,'/api/habits/save',{'title':'A','duration_days':30})
  api.change(self.data,'/api/habits/delete',{'id':h['id']})
  self.assertEqual(self.data['habits'],[])
 def test_delete_missing_raises(self):
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/habits/delete',{'id':'missing'})
 def test_stamp_missing_habit_raises(self):
  with self.assertRaises(api.Problem):
   api.change(self.data,'/api/habits/stamp',{'id':'missing','date':'2026-10-06','stamped':True})
if __name__=='__main__':unittest.main()
