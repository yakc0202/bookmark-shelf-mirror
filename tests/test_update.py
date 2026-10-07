from test_sharing import api
import unittest

class Update(unittest.TestCase):
 def setUp(self):
  self.data={'items':[{'id':'a','url':'https://x.test','title':'old','summary':'s','folder':'f','tags':'[]',
   'thumbnail':'','status':'ready','source':'','note':'','created':1,'error':'','revision':1,'deleted':False,
   'attachment_url':'','reason':''}]}
 def item(self):return self.data['items'][0]
 def test_combined_fields_apply_together(self):
  api.change(self.data,'/api/update',{'id':'a','title':'새 제목','folder':'새 폴더','reason':'이유','attachment_url':'https://file.test'})
  x=self.item()
  self.assertEqual(x['title'],'새 제목');self.assertEqual(x['folder'],'새 폴더')
  self.assertEqual(x['reason'],'이유');self.assertEqual(x['attachment_url'],'https://file.test')
 def test_title_only_keeps_existing_folder(self):
  api.change(self.data,'/api/update',{'id':'a','title':'새 제목'})
  self.assertEqual(self.item()['folder'],'f')
 def test_note_still_requeues_and_sets_error_empty(self):
  self.item()['status']='needs_content';self.item()['error']='부족'
  api.change(self.data,'/api/update',{'id':'a','note':'추가 본문'})
  x=self.item()
  self.assertEqual(x['note'],'추가 본문');self.assertEqual(x['status'],'queued');self.assertEqual(x['error'],'')
 def test_reason_alone_does_not_requeue(self):
  self.item()['status']='ready'
  api.change(self.data,'/api/update',{'id':'a','reason':'왜 저장했는지'})
  self.assertEqual(self.item()['status'],'ready')
 def test_no_fields_is_a_noop(self):
  before=dict(self.item())
  api.change(self.data,'/api/update',{'id':'a'})
  after=self.item()
  for k in before:
   if k=='revision':continue
   self.assertEqual(after[k],before[k])
if __name__=='__main__':unittest.main()
