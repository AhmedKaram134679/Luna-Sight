import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from diagnose_cog_range_client_matrix import response_record, atomic_json

class ClientMatrixTests(unittest.TestCase):
    def test_exact_206_is_pass(self):
        r=response_record("requests",100,109,206,"https://host/file.tif",
                          {"Content-Range":"bytes 100-109/1000","Content-Length":"10",
                           "Content-Type":"image/tiff"},b"x"*10,0.1)
        self.assertTrue(r["pass"])
    def test_403_body_fingerprint_and_size_are_preserved(self):
        body=b"<html>denied</html>"
        r=response_record("curl",197624,197639,403,"https://host/file.tif",
                          {"Content-Type":"text/html"},body,0.2)
        self.assertFalse(r["pass"])
        self.assertEqual(r["error_body"]["bytes"],len(body))
        self.assertEqual(r["error_body"]["sha256"],hashlib.sha256(body).hexdigest())
        self.assertIn("denied",r["error_body"]["preview_utf8"])
    def test_wrong_range_and_short_body_fail(self):
        r=response_record("requests",10,19,206,"https://host/file.tif",
                          {"Content-Range":"bytes 0-9/100"},b"x"*10,0)
        self.assertFalse(r["pass"])
        r=response_record("requests",10,19,206,"https://host/file.tif",
                          {"Content-Range":"bytes 10-19/100"},b"x",0)
        self.assertFalse(r["pass"])
    def test_atomic_json_writes_report(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"report.json"
            atomic_json(path,{"status":"PARTIAL_FAILURE"})
            self.assertIn("PARTIAL_FAILURE",path.read_text())
            self.assertFalse(path.with_name(path.name+".tmp").exists())

if __name__=="__main__": unittest.main()
