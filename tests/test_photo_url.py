from test_sharing import api
import unittest

class PhotoUrl(unittest.TestCase):
 def test_returns_permanent_cdn_url_not_presigned(self):
  url = api.photo_url('photos/abc123.jpg')
  self.assertEqual(url, 'https://test/photos/abc123.jpg')
  self.assertNotIn('Signature', url)
  self.assertNotIn('Expires', url)
 def test_site_url_overrides_bucket_domain(self):
  orig=api.SITE_URL
  try:
   api.SITE_URL='https://new.example.com'
   self.assertEqual(api.photo_url('photos/abc123.jpg'),'https://new.example.com/photos/abc123.jpg')
  finally:api.SITE_URL=orig
if __name__=='__main__':unittest.main()
