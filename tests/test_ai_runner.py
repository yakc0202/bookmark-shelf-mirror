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
 def test_login_or_connection_error_switches_to_claude(self):
  for err in ('network unavailable','Failed to refresh token: refresh token was already used'):
   with tempfile.TemporaryDirectory() as d,patch.object(a.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'',err)),patch.object(a,'run_claude',return_value=OUT) as claude:
    self.assertEqual(a.run_summary('p',{},d),OUT);self.assertEqual(claude.call_count,1)
    self.assertEqual(a.run_summary('p',{},d),OUT);self.assertEqual(a.subprocess.run.call_count,1)  # 1시간 동안 Codex 건너뜀
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
 def test_second_claude_account(self):
  import os
  a._claude_skip.clear()
  seen=[]
  def run(cmd,**kw):
   tok=(kw.get('env') or {}).get('CLAUDE_CODE_OAUTH_TOKEN');seen.append(tok)
   if tok=='A':return subprocess.CompletedProcess(cmd,1,json.dumps({'type':'result','is_error':True,'result':'limit'}),'')
   return subprocess.CompletedProcess(cmd,0,json.dumps({'type':'result','structured_output':OUT}),'')
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'CLAUDE_CODE_OAUTH_TOKEN':'A','CLAUDE_CODE_OAUTH_TOKEN_2':'B'}),patch.object(a.shutil,'which',return_value='claude'),patch.object(a.subprocess,'run',side_effect=run):
   self.assertEqual(a.run_claude('p',{},d),OUT);self.assertEqual(seen,['A','B'])
   self.assertEqual(a.run_claude('p',{},d),OUT);self.assertEqual(seen,['A','B','B'])  # 실패한 계정 1은 1시간 건너뜀
  a._claude_skip.clear()
  with patch.dict(os.environ,{'CLAUDE_CODE_OAUTH_TOKEN':'A'},clear=False):
   os.environ.pop('CLAUDE_CODE_OAUTH_TOKEN_2',None);self.assertEqual(a.claude_accounts(),[(1,'A')])
 def test_codex_account_order_and_skip_missing_second(self):
  import os
  homes=[]
  def run(cmd,**kw):
   home=(kw.get('env') or {}).get('CODEX_HOME');homes.append(home)
   if home is None:return subprocess.CompletedProcess(cmd,1,'','refresh token was already used')
   Path(cmd[cmd.index('-o')+1]).write_text(json.dumps(OUT));return subprocess.CompletedProcess(cmd,0,'','')
  with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as h2,patch.object(a.subprocess,'run',side_effect=run),patch.object(a,'run_claude') as claude:
   (Path(h2)/'auth.json').write_text('{}')
   with patch.dict(os.environ,{'CODEX_HOME_2':h2}):
    self.assertEqual(a.run_summary('p',{},d),OUT);self.assertEqual(homes,[None,h2])
    self.assertEqual(a.run_summary('p',{},d),OUT);self.assertEqual(homes,[None,h2,h2])  # 계정 1은 1시간 건너뜀
   claude.assert_not_called()
  with patch.dict(os.environ,{},clear=False):
   os.environ.pop('CODEX_HOME_2',None);self.assertEqual(a.codex_accounts(),[(1,None)])  # 계정 2 정보가 없으면 건너뜀
 def test_login_failure_rests_a_day_until_login_changes(self):
  import os,time
  calls=[]
  def run(cmd,**kw):
   calls.append(1);return subprocess.CompletedProcess(cmd,1,'','Failed to refresh token: refresh token was already used. Please log out and sign in again.')
  with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as home,patch.object(a.subprocess,'run',side_effect=run),patch.object(a,'run_claude',return_value=OUT):
   (Path(home)/'auth.json').write_text('old')
   with patch.dict(os.environ,{'CODEX_HOME':home}):
    os.environ.pop('CODEX_HOME_2',None)
    a.run_summary('p',{},d)
    rest=json.loads((Path(d)/'codex-cooldown.json').read_text())
    self.assertTrue(rest['login']);self.assertGreater(rest['until']-time.time(),23*3600)
    a.run_summary('p',{},d);self.assertEqual(len(calls),1)      # 하루 동안 건너뜀
    (Path(home)/'auth.json').write_text('new')                 # 다시 로그인하면
    a.run_summary('p',{},d);self.assertEqual(len(calls),2)      # 바로 다시 시도
 def test_claude_login_failure_rests_a_day(self):
  import os,time
  a._claude_skip.clear()
  def run(cmd,**kw):
   tok=kw['env']['CLAUDE_CODE_OAUTH_TOKEN']
   if tok=='A':return subprocess.CompletedProcess(cmd,1,json.dumps({'type':'result','is_error':True,'result':'OAuth token has expired. Please run /login'}),'')
   return subprocess.CompletedProcess(cmd,0,json.dumps({'type':'result','structured_output':OUT}),'')
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'CLAUDE_CODE_OAUTH_TOKEN':'A','CLAUDE_CODE_OAUTH_TOKEN_2':'B'}),patch.object(a.shutil,'which',return_value='claude'),patch.object(a.subprocess,'run',side_effect=run):
   self.assertEqual(a.run_claude('p',{},d),OUT)
   self.assertGreater(a._claude_skip[1][0]-time.time(),23*3600)
  a._claude_skip.clear()
 def test_login_vs_quota_detection(self):
  self.assertTrue(a.login_failed('refresh token was already used'))
  self.assertTrue(a.login_failed('workspace routing discovery unauthorized (401)'))
  self.assertFalse(a.login_failed('You have hit your usage limit.'))
  self.assertFalse(a.login_failed('network unavailable'))
if __name__=='__main__':unittest.main()
