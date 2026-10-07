import sys,unittest,tempfile,json,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ai_runner as a
OUT={'title':'제목','summary':'요약','folder':'야구','tags':[],'sufficient':True}
class Fallback(unittest.TestCase):
 def test_quota_switch_and_cooldown(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','You have hit your usage limit.')),patch.object(a,'run_claude',return_value=OUT) as claude:
   self.assertEqual(a.run_summary('p',{},d),OUT)
   self.assertEqual(a.run_summary('p',{},d),OUT)
   self.assertEqual(a.subprocess.run.call_count,1);self.assertEqual(claude.call_count,2)
 def test_connection_error_does_not_switch(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','network unavailable')),patch.object(a,'run_claude') as claude:
   with self.assertRaises(a.SummaryUnavailable):a.run_summary('p',{},d)
   claude.assert_not_called()
 def test_codex_success(self):
  def run(cmd,**kw):Path(cmd[cmd.index('-o')+1]).write_text(json.dumps(OUT));return subprocess.CompletedProcess(cmd,0,'','')
  with tempfile.TemporaryDirectory() as d,patch.object(a.subprocess,'run',side_effect=run),patch.object(a,'run_claude') as claude:
   self.assertEqual(a.run_summary('p',{},d),OUT);claude.assert_not_called()
 def test_claude_image_and_error(self):
  with tempfile.TemporaryDirectory() as d:
   image=Path(d)/'image.jpg';image.write_bytes(b'jpeg')
   def run(cmd,**kw):
    message=json.loads(kw['input']);self.assertEqual(message['message']['content'][1]['type'],'image');self.assertEqual(cmd[cmd.index('--tools')+1],'')
    return subprocess.CompletedProcess(cmd,0,json.dumps({'type':'result','structured_output':OUT}),'')
   with patch.object(a.subprocess,'run',side_effect=run):self.assertEqual(a.run_claude('p',{},d,image),OUT)
   with patch.object(a.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps({'type':'result','is_error':True}),'')):
    with self.assertRaises(a.SummaryUnavailable):a.run_claude('p',{},d)
 def test_multiple_images(self):
  with tempfile.TemporaryDirectory() as d:
   images=[Path(d)/'a.jpg',Path(d)/'b.jpg'];[im.write_bytes(b'jpeg') for im in images]
   def claude_run(cmd,**kw):
    message=json.loads(kw['input']);self.assertEqual(len(message['message']['content']),3)
    self.assertTrue(all(c['type']=='image' for c in message['message']['content'][1:]))
    return subprocess.CompletedProcess(cmd,0,json.dumps({'type':'result','structured_output':OUT}),'')
   with patch.object(a.subprocess,'run',side_effect=claude_run):self.assertEqual(a.run_claude('p',{},d,images),OUT)
   def codex_run(cmd,**kw):
    self.assertEqual(cmd.count('-i'),2)
    Path(cmd[cmd.index('-o')+1]).write_text(json.dumps(OUT));return subprocess.CompletedProcess(cmd,0,'','')
   with tempfile.TemporaryDirectory() as d2,patch.object(a.subprocess,'run',side_effect=codex_run),patch.object(a,'run_claude') as claude:
    self.assertEqual(a.run_summary('p',{},d2,images),OUT);claude.assert_not_called()
if __name__=='__main__':unittest.main()
