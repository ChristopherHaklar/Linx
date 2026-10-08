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
        self.assertEqual(clean_url("https://youtu.be/CxeWlx2p2tw?is=_gkH2uPLvCzwGjPP"), "https://youtu.be/CxeWlx2p2tw")
        self.assertEqual(clean_url("https://www.youtube.com/watch?v=CxeWlx2p2tw&is=_gkH2uPLvCzwGjPP"), "https://www.youtube.com/watch?v=CxeWlx2p2tw")

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

    def test_amazon_product_keeps_only_seller(self):
        # What a.co/d/ share links expand to: encrypted share tokens nobody listed.
        self.assertEqual(
            clean_url("https://www.amazon.com/dp/B08Z99DPDK?rsd=BUsmTEm8%2FB37&edk=AQIDAHi1lw%2FM8U%3D%3D&unknown_new=1"),
            "https://www.amazon.com/dp/B08Z99DPDK",
        )
        self.assertEqual(
            clean_url("https://www.amazon.com/Thing/dp/B08Z99DPDK/ref=x?smid=A1B2C3&tag=aff-20"),
            "https://www.amazon.com/dp/B08Z99DPDK?smid=A1B2C3",
        )

    def test_amazon_search_keeps_query_but_drops_share_tokens(self):
        self.assertEqual(
            clean_url("https://www.amazon.com/s?k=usb+cable&rsd=abc&edk=def"),
            "https://www.amazon.com/s?k=usb+cable",
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


class ExpandedRuleTests(unittest.TestCase):
    """Rules added after comparing with linkcleaner.online."""

    def assertCleans(self, dirty, clean):
        self.assertEqual(clean_url(dirty), clean)

    def test_global_analytics_and_affiliate_params(self):
        self.assertCleans(
            "https://shop.example/item?id=7&mtm_campaign=a&s_kwcid=b&gad_source=1&irclickid=c&cjevent=d&tblci=e"
            "&__hstc=f&_kx=g&WT.mc_id=h&ScCid=i&guccounter=1",
            "https://shop.example/item?id=7",
        )

    def test_global_prefixes(self):
        self.assertCleans("https://a.example/?piwik_kwd=x&matomo_source=y&vero_conv=z&page=2",
                          "https://a.example/?page=2")

    def test_ref_kept_on_github(self):
        url = "https://github.com/o/r/blob/main/f.py?ref=feature"
        self.assertCleans(url, url)

    def test_more_youtube_params_keep_timestamp(self):
        self.assertCleans("https://www.youtube.com/watch?v=abc&ab_channel=Chan&t=30&source_ve_path=MTM",
                          "https://www.youtube.com/watch?v=abc&t=30")

    def test_spotify_branch_params(self):
        self.assertCleans("https://open.spotify.com/track/x?si=1&nd=1&_branch_match_id=2",
                          "https://open.spotify.com/track/x")

    def test_x_extra_params_and_api_host_untouched(self):
        self.assertCleans("https://x.com/u/status/1?cxt=abc", "https://fixvx.com/u/status/1")
        self.assertCleans("https://api.x.com/2/tweets?s=1", "https://api.x.com/2/tweets")

    def test_reddit_linkedin_instagram(self):
        self.assertCleans("https://www.reddit.com/r/a/comments/b/c/?share_source=x&correlation_id=y",
                          "https://www.reddit.com/r/a/comments/b/c/")
        self.assertCleans("https://www.linkedin.com/posts/abc?trackingId=x&otpToken=secret&original_referer=y",
                          "https://www.linkedin.com/posts/abc")
        self.assertCleans("https://www.instagram.com/p/abc/?ig_rid=1&ig_mid=2", "https://www.instagram.com/p/abc/")

    def test_ebay_etsy_temu(self):
        self.assertCleans("https://www.ebay.co.uk/itm/123?_trkparms=a&_trksid=b&mkcid=1&var=5",
                          "https://www.ebay.co.uk/itm/123?var=5")
        self.assertCleans("https://www.etsy.com/listing/9/mug?click_key=a&click_sum=b&ga_order=c",
                          "https://www.etsy.com/listing/9/mug")
        self.assertCleans("https://www.temu.com/goods.html?goods_id=6&_x_sessn_id=a&refer_page_name=b",
                          "https://www.temu.com/goods.html?goods_id=6")

    def test_shopify_params_on_custom_domain(self):
        self.assertCleans("https://store.example/products/mug?_pos=1&_sid=a&_ss=r&variant=4",
                          "https://store.example/products/mug?variant=4")

    def test_bestbuy_and_walmart_product_ids(self):
        self.assertCleans("https://www.bestbuy.com/site/apple-airpods-pro/6447382.p?skuId=6447382&intl=nosplash",
                          "https://www.bestbuy.com/site/6447382.p")
        self.assertCleans("https://www.walmart.com/ip/Some-Toaster-2-Slice/123456789?athbdg=L1600&from=/search",
                          "https://www.walmart.com/ip/123456789")

    def test_etsy_listing_drops_all_params(self):
        self.assertCleans(
            "https://www.etsy.com/listing/4563934562/vintage-1990s-seiko-tank-7n00-5b29-black?ls=s"
            "&ga_order=most_relevant&ga_search_type=all&ga_view_type=gallery&ga_search_query=seiko+5p30+tank+black"
            "&ref=sr_gallery-1-2&sr_prefetch=1&pf_from=search&cns=1&sts=1"
            "&content_source=68eefb20%253ALT59a77e&organic_search_click=1&logging_key=68eefb20%3ALT59a77e",
            "https://www.etsy.com/listing/4563934562/vintage-1990s-seiko-tank-7n00-5b29-black",
        )
        self.assertCleans("https://www.etsy.com/uk/listing/123/some-mug?ref=shop_home_active_1&frs=1",
                          "https://www.etsy.com/uk/listing/123/some-mug")
        self.assertCleans("https://www.etsy.com/listing/123?click_key=abc", "https://www.etsy.com/listing/123")

    def test_etsy_search_keeps_query(self):
        self.assertCleans("https://www.etsy.com/search?q=seiko+tank&ref=search_bar&ga_search_query=seiko",
                          "https://www.etsy.com/search?q=seiko+tank")

    def test_kept_params_are_not_reencoded(self):
        self.assertCleans("https://example.com/a?x=1:2&list=a,b&q=a%20b&s=a+b&utm_source=z",
                          "https://example.com/a?x=1:2&list=a,b&q=a%20b&s=a+b")
        self.assertCleans("https://www.amazon.com/dp/B0B2MLTP7K?smid=A1B:2&tag=x",
                          "https://www.amazon.com/dp/B0B2MLTP7K?smid=A1B:2")

    def test_play_store_keeps_only_id_and_locale(self):
        self.assertCleans(
            "https://play.google.com/store/apps/details?id=com.discord&hl=en&gl=US&referrer=utm_source%3Dx&pcampaignid=y",
            "https://play.google.com/store/apps/details?id=com.discord&hl=en&gl=US",
        )

    def test_google_extra_search_params(self):
        self.assertCleans("https://www.google.com/search?q=a&cd=1&cad=rja&rct=j", "https://www.google.com/search?q=a")

    def test_more_redirect_wrappers(self):
        dest = "https%3A%2F%2Fexample.com%2Fa%3Futm_source%3Dx"
        for wrapped in [
            f"https://www.youtube.com/redirect?event=video_description&redir_token=QUF&q={dest}&v=abc",
            f"https://nam12.safelinks.protection.outlook.com/?url={dest}&data=05&reserved=0",
            f"https://steamcommunity.com/linkfilter/?u={dest}",
            f"https://out.reddit.com/t3_abc?url={dest}&token=x",
            f"https://t.umblr.com/redirect?z={dest}&t=abc",
            f"https://medium.com/r/?url={dest}",
            f"https://www.linkedin.com/redir/redirect?url={dest}&urlhash=abc",
            f"https://slack-redir.net/link?url={dest}",
            f"https://vk.com/away.php?to={dest}",
            "https://href.li/?https://example.com/a?utm_source=x",
        ]:
            self.assertCleans(wrapped, "https://example.com/a")

    def test_double_encoded_wrapper(self):
        self.assertCleans("https://www.google.com/url?q=https%253A%252F%252Fexample.com%252Fa",
                          "https://example.com/a")

    def test_nested_wrappers(self):
        inner = "https%3A%2F%2Fwww.google.com%2Furl%3Fq%3Dhttps%253A%252F%252Fexample.com%252Fa"
        self.assertCleans(f"https://l.facebook.com/l.php?u={inner}", "https://example.com/a")

    def test_google_amp(self):
        self.assertCleans("https://www.google.com/amp/s/www.example.com/news/story.amp",
                          "https://www.example.com/news/story.amp")

    def test_tracking_in_fragment(self):
        self.assertCleans("https://example.com/page#utm_source=news&utm_medium=email",
                          "https://example.com/page")
        self.assertCleans("https://example.com/page#section=2&utm_source=x", "https://example.com/page#section=2")

    def test_route_and_text_fragments_untouched(self):
        for url in ["https://app.example/#/inbox?id=3", "https://example.com/a#:~:text=utm_source=x",
                    "https://example.com/a#top"]:
            self.assertCleans(url, url)

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
                    "https://spotify.link/abc", "https://pin.it/abc", "https://bit.ly/3xyz",
                    "https://t.co/abc", "https://tinyurl.com/abc", "https://spoti.fi/abc"]:
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
        generic = short_link_target("https://bit.ly/x")
        self.assertTrue(is_real_destination("http://github.com/kamal/github.dcproj/tree/master", generic))
        self.assertFalse(is_real_destination("https://buffer.com/", generic))
        self.assertFalse(is_real_destination("http://tinyurl.com/#example", generic))
        reddit = short_link_target("https://www.reddit.com/r/pics/s/abc")
        self.assertFalse(is_real_destination("https://www.reddit.com/r/pics/", reddit))
        self.assertTrue(is_real_destination("https://www.reddit.com/r/pics/comments/1abc/title/", reddit))


if __name__ == "__main__":
    unittest.main()
