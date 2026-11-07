import unittest
from unittest.mock import patch
from diagnose_cog_range_failures import parse_range, RangeReader, read_exact

class COGRangeTests(unittest.TestCase):
    def test_parse_valid_range(self):
        self.assertEqual(parse_range("10-19"), (10,19))
    def test_reject_invalid_range(self):
        with self.assertRaises(Exception): parse_range("20-10")
    def test_requests_206_exact_range(self):
        reader=RangeReader("https://example.test/a.tif")
        result=reader._validate("requests",100,199,206,"https://cdn.test/a.tif",
            "Content-Range: bytes 100-199/1000\nContent-Length: 100\nContent-Type: image/tiff",b"x"*100)
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

    def test_reject_html_even_with_206(self):
        reader=RangeReader("https://example.test/a.tif")
        result=reader._validate("requests",0,9,206,"https://example.test/a.tif",
            "Content-Range: bytes 0-9/100\nContent-Type: text/html",b"<html>xx</html>")
        self.assertFalse(result["pass"])


    def test_read_exact_uses_one_get_and_returns_same_response_body(self):
        class FakeReader:
            def __init__(self):
                self.calls = []
            def get(self, start, end, client="requests", include_body=False):
                self.calls.append((start, end, client, include_body))
                return {"pass": True, "_body": b"TIFFDATA"}
        reader = FakeReader()
        self.assertEqual(read_exact(reader, 16, 8), b"TIFFDATA")
        self.assertEqual(reader.calls, [(16, 23, "requests", True)])

    def test_read_exact_chunks_large_structure_and_concatenates_in_order(self):
        class FakeReader:
            def __init__(self):
                self.calls = []
            def get(self, start, end, client="requests", include_body=False):
                self.calls.append((start, end, include_body))
                body = bytes(range(start, end + 1))
                return {"pass": True, "_body": body}
        reader = FakeReader()
        self.assertEqual(read_exact(reader, 100, 10, chunk_size=4),
                         bytes(range(100, 110)))
        self.assertEqual(reader.calls, [
            (100, 103, True), (104, 107, True), (108, 109, True)
        ])

    def test_read_exact_stops_on_failed_later_chunk(self):
        class FakeReader:
            def __init__(self):
                self.calls = []
            def get(self, start, end, client="requests", include_body=False):
                self.calls.append((start, end))
                if start >= 104:
                    return {"pass": False, "http_status": 403,
                            "content_range": "", "received_bytes": 238,
                            "expected_bytes": end-start+1}
                return {"pass": True, "_body": b"x" * (end-start+1)}
        reader = FakeReader()
        with self.assertRaisesRegex(RuntimeError, "104\\+4"):
            read_exact(reader, 100, 10, chunk_size=4)
        self.assertEqual(reader.calls, [(100, 103), (104, 107)])

    def test_read_exact_rejects_unvalidated_range_without_second_request(self):
        class FakeReader:
            def __init__(self):
                self.calls = 0
            def get(self, start, end, client="requests", include_body=False):
                self.calls += 1
                return {"pass": False, "http_status": 200, "reason": "expected HTTP 206"}
        reader = FakeReader()
        with self.assertRaisesRegex(RuntimeError, "Cannot read TIFF structure"):
            read_exact(reader, 16, 8)
        self.assertEqual(reader.calls, 1)

    def test_read_exact_rejects_missing_or_wrong_sized_retained_body(self):
        class FakeReader:
            def get(self, start, end, client="requests", include_body=False):
                return {"pass": True, "_body": b"short"}
        with self.assertRaisesRegex(RuntimeError, "did not retain"):
            read_exact(FakeReader(), 16, 8)

if __name__=="__main__": unittest.main()
