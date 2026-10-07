from test_sharing import api
import unittest

class PhotoUrl(unittest.TestCase):
 def test_returns_permanent_cdn_url_not_presigned(self):
  url = api.photo_url('photos/abc123.jpg')
  self.assertEqual(url, 'https://test/photos/abc123.jpg')
  self.assertNotIn('Signature', url)
  self.assertNotIn('Expires', url)
if __name__=='__main__':unittest.main()
