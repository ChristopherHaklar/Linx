import unittest

from cleaner import clean_url, find_cleanable_links, find_cleanable_links_async
from shortlinks import is_real_destination, short_link_target


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

    def test_amazon_product_path_canonicalized(self):
        self.assertEqual(
            clean_url("https://www.amazon.com/Anker-Charger-Foldable/dp/B0B2MLTP7K/ref=sr_1_3?crid=2X&keywords=anker&qid=17&sr=8-3"),
            "https://www.amazon.com/dp/B0B2MLTP7K",
        )
        self.assertEqual(
            clean_url("https://www.amazon.de/gp/product/B0B2MLTP7K/ref=ppx_yo_dt_b?ie=UTF8&psc=1"),
            "https://www.amazon.de/dp/B0B2MLTP7K",
        )

    def test_amazon_ref_path_segment_removed_elsewhere(self):
        self.assertEqual(
            clean_url("https://www.amazon.com/s/ref=nb_sb_noss?k=usb+cable"),
            "https://www.amazon.com/s?k=usb+cable",
        )

    def test_amazon_lookalike_untouched(self):
        url = "https://amazon.example.com/Thing/dp/B0B2MLTP7K/ref=x"
        self.assertEqual(clean_url(url), url)

    def test_google_search_keeps_query(self):
        self.assertEqual(
            clean_url("https://www.google.com/search?q=linx+bot&sca_esv=abc&ei=xyz&ved=0ah&oq=linx&gs_lp=Egx&sclient=gws-wiz&udm=2"),
            "https://www.google.com/search?q=linx+bot&udm=2",
        )
        self.assertEqual(clean_url("https://www.google.co.uk/search?q=tea&client=firefox-b-d"), "https://www.google.co.uk/search?q=tea")

    def test_google_subdomains_untouched(self):
        url = "https://docs.google.com/document/d/abc/edit?source=x"
        self.assertEqual(clean_url(url), url)

    def test_google_redirect_unwrapped(self):
        self.assertEqual(
            clean_url("https://www.google.com/url?sa=t&url=https%3A%2F%2Fexample.com%2Fa%3Futm_source%3Dg%26id%3D1&ved=2ah&usg=AOv"),
            "https://example.com/a?id=1",
        )

    def test_facebook_redirect_unwrapped(self):
        self.assertEqual(
            clean_url("https://l.facebook.com/l.php?u=https%3A%2F%2Fexample.com%2Fpost%3Ffbclid%3Dabc&h=AT0"),
            "https://example.com/post",
        )

    def test_redirect_to_non_http_ignored(self):
        url = "https://www.google.com/url?q=javascript:alert(1)"
        self.assertEqual(clean_url(url), url)

    def test_facebook_params(self):
        self.assertEqual(
            clean_url("https://www.facebook.com/groups/123/posts/456/?mibextid=abc&__cft__[0]=AZX&__tn__=%2CO%2CP-R&rdid=Q"),
            "https://www.facebook.com/groups/123/posts/456/",
        )

    def test_tiktok_expanded_share_params(self):
        self.assertEqual(
            clean_url("https://www.tiktok.com/@/video/7439986250209135928?_r=1&_d=secCg&u_code=eah&share_item_id=74&timestamp=17&utm_campaign=client_share&share_app_id=1233"),
            "https://www.tiktok.com/@/video/7439986250209135928",
        )


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


class ExpandTests(unittest.IsolatedAsyncioTestCase):
    async def test_expanded_link_is_cleaned(self):
        async def expand(url):
            return {"https://amzn.to/3abc": "https://www.amazon.com/Thing/dp/B0B2MLTP7K?tag=aff-20"}.get(url, url)

        text = "buy https://amzn.to/3abc and https://example.com/ok"
        self.assertEqual(await find_cleanable_links_async(text, expand=expand), ["https://www.amazon.com/dp/B0B2MLTP7K"])

    async def test_without_expander_matches_sync(self):
        text = "https://x.com/a/status/1?s=20"
        self.assertEqual(await find_cleanable_links_async(text), find_cleanable_links(text))


class ShortLinkRuleTests(unittest.TestCase):
    def test_recognized_short_links(self):
        for url in ["https://amzn.to/3abc", "https://a.co/d/7hG8jKq", "https://vm.tiktok.com/ZMabc/",
                    "https://www.tiktok.com/t/ZTRabc123/", "https://www.reddit.com/r/pics/s/abc123XYZ",
                    "https://spotify.link/abc", "https://pin.it/abc"]:
            self.assertIsNotNone(short_link_target(url), url)

    def test_regular_links_not_requested(self):
        for url in ["https://www.tiktok.com/@user/video/1", "https://www.reddit.com/r/pics/comments/abc/x/",
                    "https://example.com/t/abc", "https://notamzn.to/x"]:
            self.assertIsNone(short_link_target(url), url)

    def test_dead_codes_rejected(self):
        amazon = short_link_target("https://amzn.to/x")
        self.assertFalse(is_real_destination("https://www.amazon.com/", amazon))
        self.assertTrue(is_real_destination("https://www.amazon.com/dp/B0B2MLTP7K", amazon))
        self.assertFalse(is_real_destination("https://evil.example/dp/B0B2MLTP7K", amazon))
        reddit = short_link_target("https://www.reddit.com/r/pics/s/abc")
        self.assertFalse(is_real_destination("https://www.reddit.com/r/pics/", reddit))
        self.assertTrue(is_real_destination("https://www.reddit.com/r/pics/comments/1abc/title/", reddit))


if __name__ == "__main__":
    unittest.main()
