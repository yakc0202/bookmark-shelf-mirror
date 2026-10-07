import ast,json,re,unittest,urllib.parse
from pathlib import Path
source=ast.parse((Path(__file__).resolve().parents[1]/'server.py').read_text())
nodes=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('is_naver_place','naver_place_info')]
ns={'re':re,'json':json,'urllib':urllib};exec(compile(ast.Module(body=nodes,type_ignores=[]),'naver','exec'),ns)
class NaverPlace(unittest.TestCase):
 def test_hosts(self):
  for url,want in [('https://m.place.naver.com/restaurant/1/home',True),('https://naver.me/abc',True),('https://pcmap.place.naver.com/x',True),('https://blog.naver.com/x',False),('https://example.com',False)]:
   with self.subTest(url=url):self.assertEqual(ns['is_naver_place'](url),want)
 def test_extracts_name_category_address(self):
  html='<script>{"address":"주소","category":"카페,디저트","roadAddress":"서울 마포구 월드컵로10길 40","address":"서울 마포구 서교동 478-14"}</script>'
  self.assertEqual(ns['naver_place_info'](html,'루카스초이스 : 네이버'),'가게 이름: 루카스초이스\n업종: 카페,디저트\n주소: 서울 마포구 월드컵로10길 40')
 def test_falls_back_to_address_and_decodes_escapes(self):
  html='{"address":"주소"}{"address":"\\uc11c\\uc6b8 \\uc911\\uad6c"}'
  self.assertEqual(ns['naver_place_info'](html,'가게'),'가게 이름: 가게\n주소: 서울 중구')
if __name__=='__main__':unittest.main()
