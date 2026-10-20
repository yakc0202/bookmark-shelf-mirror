import ast,io,json,re,unittest,urllib.parse,urllib.request
from pathlib import Path
from unittest import mock
from test_sharing import api
source=ast.parse((Path(__file__).resolve().parents[1]/'server.py').read_text())
nodes=[n for n in source.body if (isinstance(n,ast.FunctionDef) and n.name in ('read_x_post','youtube_oembed')) or (isinstance(n,ast.Assign) and getattr(n.targets[0],'id','') in ('X_STATUS','YOUTUBE_HOSTS'))]
ns={'re':re,'json':json,'urllib':urllib};exec(compile(ast.Module(body=nodes,type_ignores=[]),'x','exec'),ns)

def reply(payload):
 return mock.patch.object(urllib.request,'urlopen',return_value=mock.MagicMock(__enter__=lambda s:io.BytesIO(json.dumps(payload).encode()),__exit__=lambda *a:False))

class XPost(unittest.TestCase):
 def test_reads_text_media_quote_and_sends_only_post_number(self):
  tweet={'text':'쫄보가 어둠을 대하는 방법','author':{'name':'celeste'},'media':{'videos':[{}],'photos':[{'url':'https://pbs.twimg.com/a.jpg','altText':'강아지'}]},'quote':{'text':'원글','author':{'name':'b'}}}
  with reply({'tweet':tweet}) as op:
   title,content,thumb=ns['read_x_post']('https://x.com/someone/status/123?s=12')
  self.assertEqual(op.call_args[0][0].full_url,'https://api.fxtwitter.com/status/123')
  self.assertEqual((title,thumb),('쫄보가 어둠을 대하는 방법','https://pbs.twimg.com/a.jpg'))
  for part in ('작성자: celeste','첨부: 사진, 영상','사진 설명: 강아지','인용한 글:','원글'):self.assertIn(part,content)
 def test_article_uses_title_and_blocks(self):
  tweet={'text':'https://x.com/i/article/9','author':{},'article':{'title':'긴 글','content':{'blocks':[{'text':'첫 문단'},{'text':'둘째'}]}}}
  with reply({'tweet':tweet}):title,content,_=ns['read_x_post']('https://twitter.com/a/status/9')
  self.assertEqual(title,'긴 글');self.assertIn('첫 문단\n둘째',content)
 def test_failures_return_none(self):
  self.assertIsNone(ns['read_x_post']('https://x.com/someone'))
  with reply({'code':404}):self.assertIsNone(ns['read_x_post']('https://x.com/a/status/1'))
  with mock.patch.object(urllib.request,'urlopen',side_effect=OSError):self.assertIsNone(ns['read_x_post']('https://x.com/a/status/1'))

class YoutubeTitle(unittest.TestCase):
 def test_official_title_and_channel(self):
  with reply({'title':'팔뚝 운동','author_name':'채널','thumbnail_url':'https://i.ytimg.com/a.jpg'}) as op:
   title,content,thumb=ns['youtube_oembed']('https://youtube.com/watch?v=abc')
  self.assertTrue(op.call_args[0][0].full_url.startswith('https://www.youtube.com/oembed?format=json&url='))
  self.assertEqual((title,thumb),('팔뚝 운동','https://i.ytimg.com/a.jpg'));self.assertIn('채널: 채널',content)
 def test_other_hosts_and_failures(self):
  self.assertIsNone(ns['youtube_oembed']('https://example.com/watch?v=abc'))
  with mock.patch.object(urllib.request,'urlopen',side_effect=OSError):self.assertIsNone(ns['youtube_oembed']('https://youtu.be/abc'))

class NeedsContentDropsTags(unittest.TestCase):
 def test_tags_removed_only_when_content_is_insufficient(self):
  data={'items':[{'id':'a','url':'https://x.com/a/status/1','title':'a','folder':'받은 편지함','status':'queued','created':1,'revision':1,'deleted':False,'tags':'["추측"]'}]}
  job=api.change(data,'/worker/claim',{})['item']
  api.change(data,'/worker/complete',{'id':'a','lease':job['lease'],'revision':job['revision'],'result':{'status':'needs_content','error':'본문 부족'}})
  self.assertEqual(data['items'][0]['tags'],'[]')
  data['items'][0]['status']='queued'
  job=api.change(data,'/worker/claim',{})['item']
  api.change(data,'/worker/complete',{'id':'a','lease':job['lease'],'revision':job['revision'],'result':{'status':'ready','tags':'["강아지"]','summary':'요약'}})
  self.assertEqual(data['items'][0]['tags'],'["강아지"]')

if __name__=='__main__':unittest.main()
