import unittest

from discover_lola_sources import discover_links


class DiscoverLinksTests(unittest.TestCase):
    def test_relative_href_and_matching_text(self):
        html = '<a href="../files/LDEM_80S_20MPP_ADJ.TIF">Download DEM</a>'
        result = discover_links(html, "https://pgda.gsfc.nasa.gov/products/90", ("LDEM_80S_20MPP_ADJ.TIF",))
        self.assertEqual(result["LDEM_80S_20MPP_ADJ.TIF"], [
            "https://pgda.gsfc.nasa.gov/files/LDEM_80S_20MPP_ADJ.TIF"
        ])

    def test_src_attribute_and_case_insensitive_match(self):
        html = '<img src="/data/LDEM_87S_5MPP.TIF">'
        result = discover_links(html, "https://pgda.gsfc.nasa.gov/products/81", ("ldem_87s_5mpp",))
        self.assertEqual(result["ldem_87s_5mpp"], [
            "https://pgda.gsfc.nasa.gov/data/LDEM_87S_5MPP.TIF"
        ])

    def test_src_can_match_product_name_in_alt_text(self):
        html = '<img src="/download?id=123" alt="ldem_87s_5mpp GeoTIFF">'
        result = discover_links(html, "https://pgda.gsfc.nasa.gov/products/81", ("ldem_87s_5mpp",))
        self.assertEqual(result["ldem_87s_5mpp"], ["https://pgda.gsfc.nasa.gov/download?id=123"])

    def test_duplicate_urls_are_deduplicated(self):
        html = ('<a href="/data/file.tif">LDEM_80S_20MPP_ADJ.TIF</a>'
                '<img src="/data/file.tif" alt="LDEM_80S_20MPP_ADJ.TIF">')
        result = discover_links(html, "https://pgda.gsfc.nasa.gov/products/90", ("LDEM_80S_20MPP_ADJ.TIF",))
        self.assertEqual(len(result["LDEM_80S_20MPP_ADJ.TIF"]), 1)

    def test_non_http_urls_are_ignored(self):
        html = '<a href="javascript:download()">LDEM_80S_20MPP_ADJ.TIF</a>'
        with self.assertRaises(ValueError):
            discover_links(html, "https://pgda.gsfc.nasa.gov/products/90", ("LDEM_80S_20MPP_ADJ.TIF",))

    def test_missing_product_fails_without_guessing(self):
        with self.assertRaisesRegex(ValueError, "no href/src URL"):
            discover_links("<html><body>No data links</body></html>",
                           "https://pgda.gsfc.nasa.gov/products/90",
                           ("LDEM_80S_20MPP_ADJ.TIF",))


if __name__ == "__main__":
    unittest.main()
