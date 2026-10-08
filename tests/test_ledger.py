from test_sharing import api
import unittest

class Ledger(unittest.TestCase):
 def setUp(self):self.data={}
 def save(self,**kw):
  body={'date':'2026-10-06','kind':'expense','amount':12000,'category':'식비','memo':'점심'}
  body.update(kw);return api.change(self.data,'/api/ledger/save',body)
 def test_create(self):
  e=self.save()
  self.assertEqual(self.data['ledger'],[e])
  self.assertEqual((e['kind'],e['amount'],e['category']),('expense',12000,'식비'))
 def test_rejects_bad_input(self):
  for bad in ({'date':'2026/10/06'},{'kind':'refund'},{'amount':0},{'amount':-5},{'amount':'1000'},{'amount':True},{'amount':1.5}):
   with self.subTest(bad=bad),self.assertRaises(api.Problem):self.save(**bad)
 def test_empty_category_defaults(self):
  self.assertEqual(self.save(category='  ')['category'],'기타')
 def test_update_keeps_created(self):
  e=self.save()
  u=self.save(id=e['id'],amount=5000,kind='income')
  self.assertEqual(len(self.data['ledger']),1)
  self.assertEqual((u['amount'],u['kind'],u['created']),(5000,'income',e['created']))
 def test_kind_defaults_to_expense(self):
  body={'date':'2026-10-06','amount':3000,'category':'카페'}
  self.assertEqual(api.change(self.data,'/api/ledger/save',body)['kind'],'expense')
 def test_update_unknown_id(self):
  with self.assertRaises(api.Problem):self.save(id='nope')
 def test_delete(self):
  e=self.save()
  api.change(self.data,'/api/ledger/delete',{'id':e['id']})
  self.assertEqual(self.data['ledger'],[])
  with self.assertRaises(api.Problem):api.change(self.data,'/api/ledger/delete',{'id':e['id']})

class LedgerPlans(unittest.TestCase):
 def setUp(self):self.data={}
 def plan(self,**kw):
  body={'cycle':'2026-10','title':'관리비','amount':150000,'category':'주거'};body.update(kw)
  return api.change(self.data,'/api/ledger/plans/save',body)
 def check(self,p,checked,date='2026-10-07'):
  return api.change(self.data,'/api/ledger/plans/check',{'id':p['id'],'checked':checked,'date':date})
 def test_create_and_validate(self):
  p=self.plan()
  self.assertEqual((p['done'],p['amount'],p['category']),(False,150000,'주거'))
  for bad in ({'title':' '},{'amount':0},{'cycle':'2026-1'}):
   with self.subTest(bad=bad),self.assertRaises(api.Problem):self.plan(**bad)
 def test_check_creates_expense_today_and_uncheck_removes_it(self):
  p=self.plan()
  out=self.check(p,True)
  e=self.data['ledger'][0]
  self.assertEqual((e['date'],e['amount'],e['category'],e['memo'],e['kind']),('2026-10-07',150000,'주거','관리비','expense'))
  self.assertTrue(out['plan']['done']);self.assertEqual(out['plan']['entry_id'],e['id'])
  self.check(p,True)
  self.assertEqual(len(self.data['ledger']),1)
  self.check(p,False)
  self.assertEqual(self.data['ledger'],[]);self.assertFalse(self.data['ledger_plans'][0]['done'])
 def test_deleting_linked_expense_unchecks_plan(self):
  p=self.plan();self.check(p,True)
  api.change(self.data,'/api/ledger/delete',{'id':self.data['ledger'][0]['id']})
  self.assertFalse(self.data['ledger_plans'][0]['done']);self.assertEqual(self.data['ledger_plans'][0]['entry_id'],'')
 def test_edit_keeps_done_state(self):
  p=self.plan();self.check(p,True)
  u=self.plan(id=p['id'],amount=160000)
  self.assertTrue(u['done']);self.assertEqual(u['amount'],160000)
 def test_edit_updates_linked_expense(self):
  p=self.plan();self.check(p,True)
  self.plan(id=p['id'],title='관리비 10월',amount=170000,category='생활')
  e=self.data['ledger'][0]
  self.assertEqual((e['amount'],e['category'],e['memo'],e['date']),(170000,'생활','관리비 10월','2026-10-07'))
 def test_custom_memo_kept_and_link_survives_entry_edit(self):
  p=self.plan();self.check(p,True)
  e=self.data['ledger'][0]
  api.change(self.data,'/api/ledger/save',{'id':e['id'],'date':e['date'],'kind':'expense','amount':e['amount'],'category':e['category'],'memo':'카드 결제'})
  self.assertEqual(self.data['ledger'][0]['plan_id'],p['id'])
  self.plan(id=p['id'],amount=99000)
  self.assertEqual((self.data['ledger'][0]['amount'],self.data['ledger'][0]['memo']),(99000,'카드 결제'))
 def test_delete_plan(self):
  p=self.plan()
  api.change(self.data,'/api/ledger/plans/delete',{'id':p['id']})
  self.assertEqual(self.data['ledger_plans'],[])
if __name__=='__main__':unittest.main()
