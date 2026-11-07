import unittest
from unittest.mock import Mock
from validate_remote_access import diagnose_url

class Response:
    def __init__(self, status, url, headers=None, content=b""):
        self.status_code, self.url = status, url
        self.headers, self.content = headers or {}, content

class RangeTests(unittest.TestCase):
    def setUp(self):
        self.s = Mock()
        self.s.head.return_value = Response(200, "https://x.test/a.tif")

    def get(self, status=206, cr="bytes 0-1023/9000", body=b"x"*1024, ct="image/tiff"):
        self.s.get.return_value = Response(status, "https://x.test/a.tif",
            {"Content-Range": cr, "Content-Type": ct}, body)

    def test_valid_206(self):
        self.get()
        self.assertEqual(diagnose_url(self.s, "https://x.test/a.tif")["status"], "PASS")

    def test_200_ignoring_range(self):
        self.get(status=200)
        with self.assertRaisesRegex(RuntimeError, "expected HTTP 206"):
            diagnose_url(self.s, "https://x.test/a.tif")

    def test_wrong_content_range(self):
        self.get(cr="bytes 1-1024/9000")
        with self.assertRaisesRegex(RuntimeError, "Content-Range"):
            diagnose_url(self.s, "https://x.test/a.tif")

    def test_truncated_body(self):
        self.get(body=b"x"*20)
        with self.assertRaisesRegex(RuntimeError, "Truncated"):
            diagnose_url(self.s, "https://x.test/a.tif")

    def test_html_body(self):
        self.get(body=b"<html>" + b"x"*1018, ct="text/html")
        with self.assertRaisesRegex(RuntimeError, "HTML"):
            diagnose_url(self.s, "https://x.test/a.tif")

    def test_transient_head_failure_is_reported(self):
        self.s.head.return_value = Response(503, "https://x.test/a.tif")
        with self.assertRaisesRegex(RuntimeError, "HEAD failed"):
            diagnose_url(self.s, "https://x.test/a.tif")
        self.s.get.assert_not_called()

if __name__ == "__main__":
    unittest.main()
