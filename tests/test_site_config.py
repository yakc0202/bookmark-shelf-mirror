import importlib.util, re, subprocess, sys, types, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cloud'))
import site_config as cfg

class SiteConfig(unittest.TestCase):
 def test_domain_only_lives_in_site_json(self):
  # 도메인은 cloud/site.json 한 곳에만 둔다(문서·운영 데이터·미러용 가릴 값 목록 제외). 커밋되는 파일만 본다(맥마다 다른 로컬 설정 제외)
  hits=[]
  tracked=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True).stdout.decode().split('\0')
  for p in (ROOT/f for f in tracked if f):
   if not p.is_file() or {'.git','data','docs','tests'}&set(p.relative_to(ROOT).parts) or p.suffix in ('.md','.shortcut'):continue
   if p.name in ('site.json','mirror-redact.txt'):continue
   try:text=p.read_text()
   except (UnicodeDecodeError,OSError):continue
   if cfg.SITE_DOMAIN in text:hits.append(str(p.relative_to(ROOT)))
  self.assertEqual(hits,[])
 def test_gate_template_has_placeholders(self):
  code=(ROOT/'cloud/site-gate.js').read_text()
  self.assertIn("const HOST = '__SITE_DOMAIN__';",code)
  self.assertIn('__CLIENT_TOKEN_HASH__',code)

class RelinkMemoPhotos(unittest.TestCase):
 def test_absolute_photo_links_become_relative(self):
  sys.modules.setdefault('boto3',types.SimpleNamespace(client=lambda *a,**kw:None))
  spec=importlib.util.spec_from_file_location('relink',ROOT/'cloud/relink_memo_photos.py')
  relink=importlib.util.module_from_spec(spec);spec.loader.exec_module(relink)
  key='a'*32
  data={'memos':[{'title':'t','revision':1,'content':f'글\n![사진](https://old.example.com/photos/{key}.jpg)\n![밖](https://other.com/x.jpg)'}]}
  self.assertEqual(len(relink.fix(data)),1)
  self.assertEqual(data['memos'][0]['content'],f'글\n![사진](/photos/{key}.jpg)\n![밖](https://other.com/x.jpg)')
  self.assertEqual(data['memos'][0]['revision'],2)
  self.assertEqual(relink.fix(data),[])
if __name__=='__main__':unittest.main()
