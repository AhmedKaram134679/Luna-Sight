import unittest
from unittest.mock import patch
from diagnose_cog_range_failures import parse_range, RangeReader

class COGRangeTests(unittest.TestCase):
    def test_parse_valid_range(self):
        self.assertEqual(parse_range("10-19"), (10,19))
    def test_reject_invalid_range(self):
        with self.assertRaises(Exception): parse_range("20-10")
    def test_requests_206_exact_range(self):
        reader=RangeReader("https://example.test/a.tif")
        result=reader._validate("requests",100,199,206,"https://cdn.test/a.tif",
            "Content-Range: bytes 100-199/1000\\nContent-Length: 100\\nContent-Type: image/tiff",b"x"*100)
        self.assertTrue(result["pass"])
        self.assertEqual(result["final_host"],"cdn.test")
    def test_reject_403(self):
        reader=RangeReader("https://example.test/a.tif")
        result=reader._validate("requests",100,199,403,"https://example.test/a.tif",
            "Content-Type: text/html",b"denied")
        self.assertFalse(result["pass"])
        self.assertEqual(result["reason"],"expected HTTP 206")
    def test_reject_wrong_content_range(self):
        reader=RangeReader("https://example.test/a.tif")
        result=reader._validate("requests",100,199,206,"https://example.test/a.tif",
            "Content-Range: bytes 0-99/1000",b"x"*100)
        self.assertFalse(result["pass"])
    def test_reject_truncated_body(self):
        reader=RangeReader("https://example.test/a.tif")
        result=reader._validate("requests",100,199,206,"https://example.test/a.tif",
            "Content-Range: bytes 100-199/1000",b"x"*8)
        self.assertFalse(result["pass"])

if __name__=="__main__": unittest.main()
