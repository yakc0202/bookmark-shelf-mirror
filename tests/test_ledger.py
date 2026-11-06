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

class LedgerInstallment(unittest.TestCase):
 def setUp(self):self.data={}
 def add(self,**kw):
  body={'date':'2026-11-30','amount':100000,'months':3,'category':'가전','memo':'청소기'};body.update(kw)
  return api.change(self.data,'/api/ledger/installment',body)
 def test_splits_by_month(self):
  out=self.add()
  self.assertEqual([e['amount'] for e in out],[33334,33333,33333])
  self.assertEqual([e['date'] for e in out],['2026-11-30','2026-12-30','2027-01-30'])
  self.assertEqual([(e['inst_no'],e['inst_total']) for e in out],[(1,3),(2,3),(3,3)])
  self.assertEqual(self.data['ledger'],out)
 def test_clamps_to_month_end(self):
  self.assertEqual(self.add(date='2027-01-31')[1]['date'],'2027-02-28')
 def test_rejects_bad_input(self):
  for bad in ({'months':1},{'months':61},{'months':'3'},{'months':True},{'amount':2},{'date':'2026-13-01'},{'date':'2026-02-30'},{'book':'x'}):
   with self.subTest(bad=bad),self.assertRaises(api.Problem):self.add(**bad)
 def test_edit_changes_one_and_keeps_link(self):
  out=self.add();e=out[1]
  u=api.change(self.data,'/api/ledger/save',{'id':e['id'],'date':e['date'],'amount':5000,'category':'가전'})
  self.assertEqual((u['amount'],u['inst_id'],u['inst_no'],u['inst_total']),(5000,e['inst_id'],2,3))
  self.assertEqual(self.data['ledger'][0]['amount'],33334)
 def test_delete_removes_whole_installment_only(self):
  other=api.change(self.data,'/api/ledger/save',{'date':'2026-11-30','amount':1000,'category':'식비'})
  out=self.add()
  api.change(self.data,'/api/ledger/delete',{'id':out[1]['id']})
  self.assertEqual(self.data['ledger'],[other])
 def test_shared_book_is_separate(self):
  self.add(book='shared')
  self.assertEqual(len(self.data['shared_ledger']),3);self.assertNotIn('ledger',self.data)

class LedgerPlanInstallment(unittest.TestCase):
 def setUp(self):self.data={}
 def add(self,**kw):
  body={'cycle':'2026-11','title':'노트북','amount':100000,'months':3,'category':'가전'};body.update(kw)
  return api.change(self.data,'/api/ledger/plans/installment',body)
 def test_one_plan_per_cycle(self):
  out=self.add()
  self.assertEqual([p['cycle'] for p in out],['2026-11','2026-12','2027-01'])
  self.assertEqual([p['amount'] for p in out],[33334,33333,33333])
  self.assertEqual([(p['inst_no'],p['inst_total'],p['done']) for p in out],[(1,3,False),(2,3,False),(3,3,False)])
 def test_rejects_bad_input(self):
  for bad in ({'months':1},{'months':61},{'amount':2},{'cycle':'2026-13'},{'title':' '},{'book':'x'}):
   with self.subTest(bad=bad),self.assertRaises(api.Problem):self.add(**bad)
 def test_edit_changes_one_and_keeps_link(self):
  p=self.add()[1]
  u=api.change(self.data,'/api/ledger/plans/save',{'id':p['id'],'cycle':p['cycle'],'title':'노트북','amount':5000})
  self.assertEqual((u['amount'],u['inst_id'],u['inst_no']),(5000,p['inst_id'],2))
  self.assertEqual(self.data['ledger_plans'][0]['amount'],33334)
 def test_converts_existing_plan(self):
  p=api.change(self.data,'/api/ledger/plans/save',{'cycle':'2026-11','title':'노트북','amount':100000})
  out=self.add(id=p['id'])
  self.assertEqual(self.data['ledger_plans'],out)
  api.change(self.data,'/api/ledger/plans/check',{'id':out[0]['id'],'checked':True,'date':'2026-11-07'})
  with self.assertRaises(api.Problem):self.add(id=out[0]['id'])
  with self.assertRaises(api.Problem):self.add(id='nope')
 def test_check_records_only_that_month(self):
  p=self.add()[0]
  api.change(self.data,'/api/ledger/plans/check',{'id':p['id'],'checked':True,'date':'2026-11-07'})
  self.assertEqual([e['amount'] for e in self.data['ledger']],[33334])
 def test_delete_removes_plans_keeps_recorded_expense(self):
  p=self.add()[0]
  api.change(self.data,'/api/ledger/plans/check',{'id':p['id'],'checked':True,'date':'2026-11-07'})
  api.change(self.data,'/api/ledger/plans/delete',{'id':p['id']})
  self.assertEqual(self.data['ledger_plans'],[]);self.assertEqual(len(self.data['ledger']),1)

class LedgerBudget(unittest.TestCase):
 def setUp(self):self.data={}
 def test_saves_per_cycle_and_book(self):
  api.change(self.data,'/api/ledger/budget',{'cycle':'2026-10','amount':1500000})
  out=api.change(self.data,'/api/ledger/budget',{'cycle':'2026-11','amount':0})
  self.assertEqual(out,{'2026-10':1500000,'2026-11':0})
  api.change(self.data,'/api/ledger/budget',{'cycle':'2026-10','amount':300000,'book':'shared'})
  self.assertEqual(self.data['shared_ledger_budgets'],{'2026-10':300000})
  self.assertEqual(self.data['ledger_budgets']['2026-10'],1500000)
 def test_rejects_bad_input(self):
  for bad in ({'cycle':'2026-10-05','amount':1},{'cycle':'2026-10','amount':-1},{'cycle':'2026-10','amount':'1'},{'cycle':'2026-10','amount':True},{'cycle':'2026-10','amount':1,'book':'x'}):
   with self.subTest(bad=bad),self.assertRaises(api.Problem):api.change(self.data,'/api/ledger/budget',bad)

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
 def test_editing_linked_expense_updates_plan(self):
  p=self.plan();self.check(p,True)
  e=self.data['ledger'][0]
  out=api.change(self.data,'/api/ledger/save',{'id':e['id'],'date':'2026-10-09','kind':'expense','amount':123000,'category':'생활','memo':e['memo']})
  plan=self.data['ledger_plans'][0]
  self.assertEqual((plan['amount'],plan['category'],plan['done_date'],plan['done']),(123000,'생활','2026-10-09',True))
  self.assertEqual(out['plan']['amount'],123000);self.assertNotIn('plan',self.data['ledger'][0])
 def test_delete_plan(self):
  p=self.plan()
  api.change(self.data,'/api/ledger/plans/delete',{'id':p['id']})
  self.assertEqual(self.data['ledger_plans'],[])
if __name__=='__main__':unittest.main()

class SharedBook(unittest.TestCase):
 def setUp(self):self.data={}
 def test_shared_entries_and_plans_stay_separate(self):
  mine=api.change(self.data,'/api/ledger/save',{'date':'2026-10-06','amount':1000,'category':'식비'})
  shared=api.change(self.data,'/api/ledger/save',{'date':'2026-10-06','amount':50000,'category':'관리비','book':'shared'})
  self.assertEqual(self.data['ledger'],[mine]);self.assertEqual(self.data['shared_ledger'],[shared])
  p=api.change(self.data,'/api/ledger/plans/save',{'cycle':'2026-10','title':'월세','amount':500000,'book':'shared'})
  out=api.change(self.data,'/api/ledger/plans/check',{'id':p['id'],'checked':True,'date':'2026-10-07','book':'shared'})
  self.assertEqual(len(self.data['shared_ledger']),2);self.assertEqual(len(self.data['ledger']),1)
  self.assertEqual(len(out['ledger']),2);self.assertNotIn('ledger_plans',self.data)
 def test_cannot_touch_other_book(self):
  e=api.change(self.data,'/api/ledger/save',{'date':'2026-10-06','amount':1000})
  with self.assertRaises(api.Problem):api.change(self.data,'/api/ledger/delete',{'id':e['id'],'book':'shared'})
 def test_unknown_book_rejected(self):
  with self.assertRaises(api.Problem):api.change(self.data,'/api/ledger/save',{'date':'2026-10-06','amount':1000,'book':'other'})
