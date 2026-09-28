import unittest

from cleaner import clean_url, find_cleanable_links


class CleanUrlTests(unittest.TestCase):
    def test_x_to_fixvx_and_strip_share_params(self):
        self.assertEqual(
            clean_url("https://x.com/user/status/123?s=20&t=abc"),
            "https://fixvx.com/user/status/123",
        )

    def test_twitter_and_mobile_hosts(self):
        self.assertEqual(clean_url("https://twitter.com/u/status/1"), "https://fixvx.com/u/status/1")
        self.assertEqual(clean_url("https://mobile.x.com/u/status/1"), "https://fixvx.com/u/status/1")
        self.assertEqual(clean_url("https://www.x.com/u/status/1"), "https://fixvx.com/u/status/1")

    def test_fix_x_disabled(self):
        self.assertEqual(clean_url("https://x.com/u/status/1?s=20", fix_x=False), "https://x.com/u/status/1")

    def test_does_not_touch_lookalike_domains(self):
        self.assertEqual(clean_url("https://notx.com/a?s=1"), "https://notx.com/a?s=1")

    def test_utm_and_fbclid(self):
        self.assertEqual(
            clean_url("https://example.com/page?id=5&utm_source=x&utm_medium=y&fbclid=zzz#top"),
            "https://example.com/page?id=5#top",
        )

    def test_youtube_keeps_video_and_time(self):
        self.assertEqual(
            clean_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=abc&t=42"),
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42",
        )
        self.assertEqual(clean_url("https://youtu.be/dQw4w9WgXcQ?si=abc"), "https://youtu.be/dQw4w9WgXcQ")

    def test_si_kept_on_unknown_sites(self):
        self.assertEqual(clean_url("https://example.com/?si=1"), "https://example.com/?si=1")

    def test_spotify(self):
        self.assertEqual(
            clean_url("https://open.spotify.com/track/abc?si=123"),
            "https://open.spotify.com/track/abc",
        )

    def test_amazon_regional(self):
        self.assertEqual(
            clean_url("https://www.amazon.co.uk/dp/B000?ref_=abc&tag=aff-21"),
            "https://www.amazon.co.uk/dp/B000",
        )

    def test_clean_link_unchanged(self):
        url = "https://example.com/a?b=c"
        self.assertEqual(clean_url(url), url)


class FindLinksTests(unittest.TestCase):
    def test_finds_only_changed_links(self):
        text = "look https://example.com/ok and https://x.com/a/status/1?s=46 cool"
        self.assertEqual(find_cleanable_links(text), ["https://fixvx.com/a/status/1"])

    def test_trailing_punctuation_and_parens(self):
        text = "(see https://x.com/a/status/1?s=20)."
        self.assertEqual(find_cleanable_links(text), ["https://fixvx.com/a/status/1"])

    def test_wikipedia_parens_preserved(self):
        text = "https://en.wikipedia.org/wiki/Foo_(bar)?utm_source=x"
        self.assertEqual(find_cleanable_links(text), ["https://en.wikipedia.org/wiki/Foo_(bar)"])

    def test_dedupes(self):
        text = "https://x.com/a/status/1 https://x.com/a/status/1?s=20"
        self.assertEqual(find_cleanable_links(text), ["https://fixvx.com/a/status/1"])

    def test_no_links(self):
        self.assertEqual(find_cleanable_links("hello there"), [])


if __name__ == "__main__":
    unittest.main()
