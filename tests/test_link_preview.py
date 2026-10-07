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
 def test_threads_uses_post_text_as_title(self):
  with serve(THREADS):
   thumb, title = api.fetch_link_preview('https://www.threads.com/share/abc/')
  self.assertEqual(title, 'word-break는 줄바꿈 후보를 지정합니다.')
  self.assertEqual(thumb, 'https://cdn.test/p.jpg?a=1&b=2')
 def test_other_sites_keep_og_title(self):
  with serve(PLAIN):
   self.assertEqual(api.fetch_link_preview('https://blog.test/post/1')[1], '보통 글 제목')
 def test_merge_does_not_put_author_into_topic(self):
  data = {'items': []}
  with serve(THREADS):
   api.change(data, '/api/items', {'url': 'https://www.threads.com/share/one/'})
   api.change(data, '/api/items', {'url': 'https://www.threads.com/share/two/'})
  item = data['items'][0]
  self.assertFalse(item.get('topic'))
  self.assertEqual(item['entries'][0]['title'], 'word-break는 줄바꿈 후보를 지정합니다.')

class InferredTopic(unittest.TestCase):
 def complete(self, item, topic):
  data = {'items': [item]}
  job = api.change(data, '/worker/claim', {})['item']
  api.change(data, '/worker/complete', {'id': job['id'], 'lease': job['lease'], 'revision': job['revision'],
                                        'result': {'status': 'ready', 'title': '제목', 'topic': topic}})
  return data['items'][0]
 def base(self, **kw):
  return {'id': 'a', 'url': 'https://x.test/1', 'title': 't', 'folder': 'f', 'status': 'queued', 'created': 1, 'revision': 1, **kw}
 def test_thread_gets_ai_topic(self):
  item = self.complete(self.base(entries=[{'kind': 'link', 'url': 'https://x.test/2', 'title': '둘째 글'}]), 'CSS 줄바꿈')
  self.assertEqual(item['topic'], 'CSS 줄바꿈')
 def test_user_topic_is_kept(self):
  item = self.complete(self.base(topic='내 주제', entries=[{'kind': 'link', 'url': 'https://x.test/2', 'title': '둘째 글'}]), 'AI 주제')
  self.assertEqual(item['topic'], '내 주제')
 def test_single_card_gets_no_topic(self):
  self.assertFalse(self.complete(self.base(), '주제').get('topic'))
if __name__ == '__main__': unittest.main()
