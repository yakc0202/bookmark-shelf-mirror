from test_sharing import api
import unittest
from unittest.mock import patch

THREADS = ('<html><head><meta property="og:title" content="딸깍 (@ddal_kkak_) on Threads">'
           '<meta property="og:description" content="word-break는 줄바꿈 후보를 지정합니다.\n\n한국어 예시">'
           '<meta property="og:image" content="https://cdn.test/p.jpg?a=1&amp;b=2"></head></html>')
PLAIN = '<html><head><meta property="og:title" content="보통 글 제목"><meta property="og:description" content="설명"></head></html>'

class FakeResponse:
 def __init__(self, body): self.body = body.encode()
 def read(self, n=-1): return self.body
 def __enter__(self): return self
 def __exit__(self, *a): return False

def serve(body):
 return patch.object(api.urllib.request, 'urlopen', lambda req, timeout=0: FakeResponse(body))

class LinkPreview(unittest.TestCase):
 def test_threads_uses_post_text_and_author(self):
  with serve(THREADS):
   thumb, title, author = api.link_meta('https://www.threads.com/share/abc/')
  self.assertEqual(title, 'word-break는 줄바꿈 후보를 지정합니다.')
  self.assertEqual(author, '딸깍 (@ddal_kkak_)')
  self.assertEqual(thumb, 'https://cdn.test/p.jpg?a=1&b=2')
 def test_thread_topic_keeps_short_name(self):
  self.assertEqual(api.thread_topic('📝 자소서Lab | AI 두괄식 STAR 엔진 (@jasoseo_lab)'), '📝 자소서Lab')
  self.assertEqual(api.thread_topic('JobPT (@jobpt0710)'), 'JobPT')
 def test_other_sites_keep_og_title_without_author(self):
  with serve(PLAIN):
   thumb, title, author = api.link_meta('https://blog.test/post/1')
  self.assertEqual((title, author), ('보통 글 제목', ''))
 def test_merge_names_thread_with_author_but_keeps_existing_topic(self):
  data = {'items': []}
  with serve(THREADS):
   api.change(data, '/api/items', {'url': 'https://www.threads.com/share/one/'})
   api.change(data, '/api/items', {'url': 'https://www.threads.com/share/two/'})
  item = data['items'][0]
  self.assertEqual(item['topic'], '딸깍')
  self.assertEqual(item['entries'][0]['title'], 'word-break는 줄바꿈 후보를 지정합니다.')
  item['topic'] = '내가 정한 주제'
  with serve(THREADS):
   api.change(data, '/api/items', {'url': 'https://www.threads.com/share/three/'})
  self.assertEqual(item['topic'], '내가 정한 주제')
if __name__ == '__main__': unittest.main()
