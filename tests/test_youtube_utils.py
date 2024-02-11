import unittest
import youtube_utils

TEST_URL1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
TEST_URL2 = "https://youtu.be/dQw4w9WgXcQ"

class Test_YoutubeUtils(unittest.TestCase):
    def test_url_matcher(self):
        self.assertEqual(
            youtube_utils.url_matcher(TEST_URL1),
            {
                "protocol" : "https",
                "subdomain" : "www",
                "domain" : "youtube",
                "top_level_domain" : "com",
                "directory" : None,
                "page" : "watch?v=dQw4w9WgXcQ",
            }
        )

        self.assertEqual(
            youtube_utils.url_matcher(TEST_URL2),
            {
                "protocol" : "https",
                "subdomain" : None,
                "domain" : "youtu",
                "top_level_domain" : "be",
                "directory" : None,
                "page" : "dQw4w9WgXcQ",
            }
        )

        # no protocol url
        self.assertEqual(
            youtube_utils.url_matcher("www.youtube.com/watch?v=dQw4w9WgXcQ"),
            {
                "protocol" : None,
                "subdomain" : "www",
                "domain" : "youtube",
                "top_level_domain" : "com",
                "directory" : None,
                "page" : "watch?v=dQw4w9WgXcQ",
            }
        )

        self.assertEqual(
            youtube_utils.url_matcher("https://open.spotify.com/track/5ES1j81Tyrkw9i5KyVc25f?si=b2064db40b9c4d89")["domain"], #type: ignore
            "spotify"
        )
        self.assertEqual(youtube_utils.url_matcher("hi"), None)

    def test_extract_yt_url_from(self):
        self.assertEqual(
            youtube_utils.extract_yt_url_from(TEST_URL1),
            TEST_URL1
        )
        self.assertEqual(
            youtube_utils.extract_yt_url_from(f"GG EZ {TEST_URL1}"),
            TEST_URL1
        )

        self.assertEqual(
            youtube_utils.extract_yt_url_from(f"GG EZ <{TEST_URL1}>"),
            TEST_URL1
        )

        self.assertEqual(youtube_utils.extract_yt_url_from("WOW"), None)

if __name__ == "__main__":
    unittest.main()
