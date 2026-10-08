import ast,re,unittest
from pathlib import Path
source=ast.parse((Path(__file__).resolve().parents[1]/'server.py').read_text())
nodes=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('normalize_folder','classification_fields')]
ns={'re':re};exec(compile(ast.Module(body=nodes,type_ignores=[]),'normalize_folder','exec'),ns)
class Classification(unittest.TestCase):
 def test_food_types(self):
  for given,want in [('밥','맛집'),('커피/음료','카페'),('커피','카페'),('빵','빵집'),('서울(빵)','서울(빵집)'),('상해(카페)','상하이(카페)'),('타이베이(카페)','대만(카페)'),('타이난(빵집)','대만(빵집)'),('대만(맛집)','대만(맛집)'),('차','차')]:
   with self.subTest(given=given):self.assertEqual(ns['normalize_folder'](given),want)
 def test_korea_country_folder_unified(self):
  for given,want in [('한국(빵집)','대한민국(빵집)'),('대한민국(맛집)','대한민국(맛집)'),('한국','한국')]:
   with self.subTest(given=given):self.assertEqual(ns['normalize_folder'](given),want)
 def test_empty_string_placeholder_is_removed(self):
  for given,want in [('(빈 문자열)(카페)','카페'),('빈 문자열','받은 편지함'),('(빈 문자열)','받은 편지함'),('서울(빈 문자열)','서울'),('서울(카페)','서울(카페)')]:
   with self.subTest(given=given):self.assertEqual(ns['normalize_folder'](given),want)
 def test_exam_folders_use_language_not_test_name(self):
  for given,want in [('공부(토익)','공부(영어)'),('공부(토플)','공부(영어)'),('공부(오픽)','공부(영어)'),('공부(HSK)','공부(중국어)'),('공부(JLPT)','공부(일본어)'),('공부(영어)','공부(영어)'),('공부(IT)','공부(IT)')]:
   with self.subTest(given=given):self.assertEqual(ns['normalize_folder'](given),want)
 def test_ai_folder_variants_unified(self):
  for given in ('꿀팁(AI)','인공지능','AI 소식','꿀팁-AI'):
   with self.subTest(given=given):self.assertEqual(ns['normalize_folder'](given),'AI')
  self.assertEqual(ns['normalize_folder']('AI'),'AI')
 def test_job_hunting_subfolders(self):
  for given,want in [('자소서','취준(자소서)'),('자기소개서','취준(자소서)'),('꿀팁(자소서)','취준(자소서)'),
                      ('면접','취준(면접)'),('꿀팁(면접)','취준(면접)'),
                      ('이력서','취준(이력서)'),('경력기술서','취준(이력서)'),('포트폴리오','취준(이력서)'),('증명사진','취준(이력서)'),('꿀팁(이력서)','취준(이력서)'),
                      ('꿀팁(취준)','취준'),('취준','취준'),('취준(자소서)','취준(자소서)')]:
   with self.subTest(given=given):self.assertEqual(ns['normalize_folder'](given),want)
 def test_classified_but_not_summarizable_is_ready_with_no_tag(self):
  summary,folder,status,reason,error=ns['classification_fields']({'sufficient':False,'folder':'동물>강아지','summary':''})
  self.assertEqual(status,'ready');self.assertEqual(summary,'');self.assertEqual(error,'')
 def test_unclassifiable_stays_needs_content(self):
  summary,folder,status,reason,error=ns['classification_fields']({'sufficient':False,'folder':'받은 편지함','summary':''})
  self.assertEqual(status,'needs_content');self.assertEqual(folder,'받은 편지함')
 def test_sufficient_is_ready_with_summary(self):
  summary,folder,status,reason,error=ns['classification_fields']({'sufficient':True,'folder':'AI','summary':'요약 내용'})
  self.assertEqual(status,'ready');self.assertEqual(summary,'요약 내용')
if __name__=='__main__':unittest.main()
