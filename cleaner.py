"""Link cleaning: strips tracking query params and rewrites X/Twitter links to fixvx.com."""

import asyncio
import re
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qsl, unquote, unquote_plus, urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)

# Query params removed from every URL (compared case-insensitively). Each exists to identify
# a person, a campaign or a click; none changes which page you land on.
GLOBAL_TRACKING_PARAMS = {p.lower() for p in {
    # Ad click IDs
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid", "gad_source", "gad_campaignid", "srsltid",
    "msclkid", "yclid", "ysclid", "ymclid", "ttclid", "twclid", "li_fat_id", "ScCid", "epik", "rb_clickid",
    # Google Analytics cross-domain
    "_ga", "_gl",
    # Adobe Analytics
    "s_cid", "s_kwcid", "ef_id", "sc_cid", "sc_campaign", "sc_channel", "sc_content", "sc_medium",
    "sc_outcome", "sc_geo", "sc_country",
    # Meta / Instagram
    "fb_action_ids", "fb_action_types", "fb_ref", "fb_source", "fbadid", "igshid", "igsh", "ig_rid", "ig_mid",
    # X / Twitter
    "ref_src", "ref_url",
    # Reddit, Snapchat
    "rdt_cid", "sc_referrer", "sc_ua",
    # Yandex / Mail.ru
    "_openstat", "etext", "frommail",
    # Email and marketing automation
    "mc_cid", "mc_eid", "mkt_tok", "_kx", "__s", "_hsenc", "_hsmi", "__hsfp", "__hssc", "__hstc",
    "hsCtaTracking", "elqTrack", "elqTrackId", "elqaid", "elqat", "elqCampaignId", "wickedid", "wickedsource",
    # Affiliate networks
    "irclickid", "irgwc", "cjevent", "cjdata", "sscid", "zanpid", "awc", "ranMID", "ranEAID", "ranSiteID",
    "ps_partner_key", "ps_xid", "gsxid", "gspk",
    # Content recommendation widgets
    "obOrigUrl", "ob_click_id", "dicbo", "tblci", "cto_pld",
    # Publisher conventions
    "at_medium", "at_campaign", "at_custom1", "at_custom2", "at_custom3", "at_custom4",
    "ns_campaign", "ns_mchannel", "ns_source", "ns_linkname", "ns_fee", "xtor", "ito", "cmpid", "cmp",
    "wt_mc", "WT.mc_id", "WT.tsrc", "guccounter", "guce_referrer", "guce_referrer_sig", "referrer",
    # Shopify storefronts (custom domains, so these can't be scoped to shopify.com)
    "_pos", "_sid", "_ss", "_psq",
}}
GLOBAL_TRACKING_PREFIXES = ("utm_", "pk_", "mtm_", "piwik_", "matomo_", "hsa_", "vero_", "oly_")

TLD = r"(?:com|co\.[a-z]{2}|com\.[a-z]{2}|[a-z]{2})"  # .com, .co.uk, .com.au, .de, ...


def _host(pattern: str, subdomains: bool = True) -> re.Pattern:
    prefix = r"(?:[a-z0-9-]+\.)*" if subdomains else r"(?:www\.|m\.)?"
    return re.compile(f"{prefix}(?:{pattern})")


AMAZON_HOST = _host(rf"amazon\.{TLD}")
GOOGLE_HOST = _host(rf"google\.{TLD}", subdomains=False)  # search only; not docs., maps., play.
X_HOST = _host(r"(?:x|twitter)\.com")
X_REWRITE_HOST = re.compile(r"(?:www\.|m\.|mobile\.)?(?:x|twitter)\.com")  # not api.x.com etc.

# Params that are only tracking on specific sites (they may be meaningful elsewhere).
# A host collects the params of every rule it matches.
SITE_RULES: list[tuple[re.Pattern, set[str]]] = [(host, {p.lower() for p in params}) for host, params in [
    (X_HOST, {"s", "t", "cxt", "rw_tt_thread"}),
    (_host(r"youtube\.com|youtu\.be"), {"si", "is", "feature", "pp", "ab_channel", "kw", "source_ve_path",
                                        "embeds_referring_euri", "embeds_referring_origin"}),
    (_host(r"spotify\.com"), {"si", "nd", "context", "_branch_match_id", "_branch_referrer"}),
    (_host(r"instagram\.com"), {"igsh", "img_index"}),
    (_host(r"tiktok\.com"), {"_r", "_d", "_t", "is_from_webapp", "sender_device", "sender_web_id", "web_id",
                             "share_app_id", "share_item_id", "share_link_id", "u_code", "user_id", "timestamp",
                             "social_share_type", "sec_user_id", "checksum", "tt_from", "tt_medium", "source",
                             "refer"}),
    (_host(r"reddit\.com"), {"share_id", "share_source", "share_recommendation", "correlation_id", "rdt",
                             "ref_source", "ref_campaign", "chainedposts", "post_fullname"}),
    (_host(r"linkedin\.com"), {"trk", "trkinfo", "trackingid", "lipi", "rcm", "refid", "ebp", "otptoken",
                               "original_referer", "licu", "originalsubdomain", "midtoken", "midsig"}),
    (_host(r"facebook\.com"), {"mibextid", "rdid", "sfnsn", "__tn__", "__cft__", "__xts__", "extid", "ref",
                               "fref", "hc_ref", "hc_location", "paipv", "eav", "acontext", "notif_id", "notif_t",
                               "comment_tracking", "xts"}),
    (_host(rf"pinterest\.{TLD}"), {"invite_code", "sender", "sfo"}),
    (_host(r"bing\.com"), {"cvid", "form"}),
    (AMAZON_HOST, {"ref", "ref_", "tag", "psc", "th", "linkcode", "creative", "camp", "creativeasin", "ascsubtag",
                   "keywords", "qid", "sr", "crid", "sprefix", "dib", "dib_tag", "content-id", "_encoding",
                   "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_dr", "pf_rd_p", "pf_rd_r", "pf_rd_s",
                   "pf_rd_t", "pf_rd_i", "pf_rd_m", "social_share", "starsleft", "linkid", "ie", "rsd", "edk"}),
    (_host(rf"(?:aliexpress|temu)\.{TLD}"), {"spm", "scm", "pvid", "algo_pvid", "algo_exp_id", "aff_platform",
                                            "aff_trace_key", "aff_short_key", "aff_fcid", "aff_fsk",
                                            "aff_request_id", "terminal_id", "sk", "btsid", "ws_ab_test",
                                            "pdp_npi", "curpageloguid", "_t", "_x_ads_channel", "_x_sessn_id",
                                            "refer_page_name", "refer_page_id", "srcsp", "top_gallery_url"}),
    (_host(rf"ebay\.{TLD}"), {"_trkparms", "_trksid", "mkcid", "mkrid", "mkevt", "campid", "customid", "toolid",
                              "siteid", "amdata", "norover", "ssspo", "sssrc", "ssuid", "widget_ver"}),
    (_host(r"etsy\.com"), {"click_key", "click_sum", "frs", "sc_g", "organic_search_click", "ga_order",
                           "ga_search_type", "ga_view_type", "ga_search_query", "ref", "ls", "sr_prefetch",
                           "pf_from", "cns", "sts", "content_source", "logging_key", "plkey", "pro", "sca"}),
    (_host(r"walmart\.com"), {"athbdg", "athcpid", "athena", "athpgid", "athznid", "from", "sid", "veh",
                              "adsredirect"}),
    (_host(r"bestbuy\.com"), {"intl", "loc", "acampid"}),
    (_host(r"(?:myshopify|shopify)\.com"), {"_v"}),
    # Search-page noise; q, tbm, udm, tbs, start and hl are kept.
    (GOOGLE_HOST, {"ei", "ved", "uact", "oq", "gs_lp", "gs_lcrp", "gs_lcp", "gs_l", "gs_ssp", "sclient", "sxsrf",
                   "sca_esv", "sca_upv", "source", "sourceid", "ie", "oe", "rlz", "bih", "biw", "dpr", "iflsig",
                   "aqs", "client", "sa", "usg", "cshid", "fbs", "prmd", "lei", "mstk", "csui", "zx", "no_sw_cr",
                   "cd", "cad", "rct"}),
]]

# Link wrappers that hide the real destination: (host, path or None, query keys).
# No keys means the destination is everything after the "?".
UNWRAPPERS: list[tuple[re.Pattern, re.Pattern | None, tuple[str, ...]]] = [
    (GOOGLE_HOST, re.compile(r"/url"), ("q", "url")),
    (re.compile(r"l\.facebook\.com|lm\.facebook\.com|l\.messenger\.com|l\.instagram\.com"), None, ("u",)),
    (_host(r"youtube\.com", subdomains=False), re.compile(r"/redirect"), ("q",)),
    (re.compile(r"out\.reddit\.com"), None, ("url",)),
    (re.compile(r"away\.vk\.com"), None, ("to",)),
    (_host(r"vk\.com", subdomains=False), re.compile(r"/away\.php"), ("to",)),
    (re.compile(r"t\.umblr\.com"), None, ("z",)),
    (re.compile(r"href\.li"), None, ()),
    (_host(r"medium\.com"), re.compile(r"/r/?"), ("url",)),
    (re.compile(r"steamcommunity\.com"), re.compile(r"/linkfilter/?"), ("url", "u")),
    (_host(r"safelinks\.protection\.outlook\.com"), None, ("url",)),
    (_host(r"deviantart\.com", subdomains=False), re.compile(r"/users/outgoing"), ()),
    (_host(r"linkedin\.com", subdomains=False), re.compile(r"/redir/redirect"), ("url",)),
    (_host(r"xing\.com", subdomains=False), re.compile(r"/social/external_link.*"), ("url",)),
    (re.compile(r"(?:www\.)?slack-redir\.net"), None, ("url",)),
    (_host(r"getpocket\.com", subdomains=False), re.compile(r"/redirect"), ("url",)),
]
GOOGLE_AMP_PATH = re.compile(r"/amp/(?:s/)?(.+)")

# Product pages reduced to their ID: Amazon /dp/<ASIN>, Best Buy /site/<sku>.p, Walmart /ip/<id>,
# Etsy /listing/<id>/<name> (with an optional country prefix like /uk).
AMAZON_PRODUCT_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?=/|$)", re.IGNORECASE)
AMAZON_PRODUCT_KEEP = ("smid",)  # the ASIN already pins the item and variant; smid picks the seller
BESTBUY_HOST = _host(r"bestbuy\.com")
BESTBUY_PRODUCT_RE = re.compile(r"/site/(?:[^/]+/)?(\d+)\.p")
WALMART_HOST = _host(r"walmart\.com")
WALMART_PRODUCT_RE = re.compile(r"/ip/(?:[^/]+/)?(\d+)")
ETSY_HOST = _host(r"etsy\.com")
ETSY_LISTING_RE = re.compile(r"(?:/[a-z]{2}(?:-[a-z]{2})?)?/listing/\d+(?:/[^/]+)?", re.IGNORECASE)
PLAY_STORE_HOST = re.compile(r"play\.google\.com")
PLAY_STORE_KEEP = ("id", "hl", "gl")

FIX_X_HOST = "fixvx.com"

TRAILING_PUNCT = ".,!?;:"


def _site_params(host: str) -> set[str]:
    params: set[str] = set()
    for pattern, site_params in SITE_RULES:
        if pattern.fullmatch(host):
            params |= site_params
    return params


def _is_tracking(key: str, site_params: set[str]) -> bool:
    k = key.lower().split("[", 1)[0]  # __cft__[0] -> __cft__
    return k in GLOBAL_TRACKING_PARAMS or k.startswith(GLOBAL_TRACKING_PREFIXES) or k in site_params


def _as_url(value: str) -> str | None:
    """Return `value` as an http(s) URL, decoding it again if it was double-encoded."""
    for _ in range(3):
        if value.lower().startswith(("http://", "https://")):
            return value
        decoded = unquote(value)
        if decoded == value:
            return None
        value = decoded
    return None


def _unwrap_once(url: str) -> str | None:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    amp = GOOGLE_AMP_PATH.fullmatch(parts.path)
    if amp and GOOGLE_HOST.fullmatch(host):
        target = unquote(amp.group(1))
        return target if target.lower().startswith(("http://", "https://")) else "https://" + target
    for host_re, path_re, keys in UNWRAPPERS:
        if not host_re.fullmatch(host) or (path_re and not path_re.fullmatch(parts.path)):
            continue
        if not keys:
            return _as_url(url.split("?", 1)[1]) if "?" in url else None
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        for key in keys:
            target = _as_url(query.get(key, ""))
            if target:
                return target
    return None


def _unwrap(url: str) -> str:
    """Follow google.com/url?q=, l.facebook.com/l.php?u= and similar wrappers to their destination."""
    for _ in range(5):  # wrappers can be nested
        try:
            target = _unwrap_once(url)
        except ValueError:
            return url
        if target is None:
            return url
        url = target
    return url


def _clean_fragment(fragment: str, site_params: set[str]) -> str:
    """Some senders put tracking after the #, e.g. #utm_source=... Leave route and text fragments alone."""
    if "=" not in fragment or fragment.startswith(":~:"):
        return fragment
    parts = fragment.split("&")
    kept = [p for p in parts if not _is_tracking(p.split("=", 1)[0], site_params)]
    return fragment if len(kept) == len(parts) else "&".join(kept)


def _filter_query(query: str, keep: Callable[[str], bool]) -> str:
    """Drop params whose name fails `keep`, leaving the kept ones exactly as they were written."""
    segments = [seg for seg in query.split("&") if seg]
    kept = [seg for seg in segments if keep(unquote_plus(seg.split("=", 1)[0]))]
    return query if len(kept) == len(segments) else "&".join(kept)


def clean_url(url: str, fix_x: bool = True) -> str:
    """Return the URL with tracking params removed and (optionally) X links sent to fixvx."""
    url = _unwrap(url)
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    host = (parts.hostname or "").lower().rstrip(".")
    netloc = parts.netloc
    path = parts.path
    query = parts.query
    site_params = _site_params(host)

    if PLAY_STORE_HOST.fullmatch(host):
        query = _filter_query(query, lambda k: k in PLAY_STORE_KEEP)
    else:
        query = _filter_query(query, lambda k: not _is_tracking(k, site_params))

    fragment = _clean_fragment(parts.fragment, site_params)

    if AMAZON_HOST.fullmatch(host):
        product = AMAZON_PRODUCT_RE.search(path)
        if product:
            path = f"/dp/{product.group(1)}"
            query = _filter_query(parts.query, lambda k: k.lower() in AMAZON_PRODUCT_KEEP)
        else:
            path = "/".join(seg for seg in path.split("/") if not seg.lower().startswith("ref="))
    elif BESTBUY_HOST.fullmatch(host) and (product := BESTBUY_PRODUCT_RE.search(path)):
        path, query = f"/site/{product.group(1)}.p", ""  # skuId repeats the path
    elif WALMART_HOST.fullmatch(host) and (product := WALMART_PRODUCT_RE.search(path)):
        path = f"/ip/{product.group(1)}"
    elif ETSY_HOST.fullmatch(host) and (listing := ETSY_LISTING_RE.match(path)):
        path, query = listing.group(0), ""  # the listing ID pins the item; every listing param is tracking

    if fix_x and X_REWRITE_HOST.fullmatch(host):
        netloc = FIX_X_HOST

    return urlunsplit((parts.scheme, netloc, path, query, fragment))


def _split_trailing(url: str) -> tuple[str, str]:
    """Separate punctuation that ended a sentence rather than the URL itself."""
    tail = ""
    while url:
        if url[-1] in TRAILING_PUNCT:
            tail = url[-1] + tail
            url = url[:-1]
        elif url[-1] == ")" and url.count(")") > url.count("("):
            tail = url[-1] + tail
            url = url[:-1]
        else:
            break
    return url, tail


def extract_urls(text: str) -> list[str]:
    """Return every http(s) link in `text`, without sentence-ending punctuation."""
    return [_split_trailing(match.group(0))[0] for match in URL_RE.finditer(text)]


def _collect(urls: list[str], targets: list[str], fix_x: bool) -> list[str]:
    results: list[str] = []
    for url, target in zip(urls, targets):
        cleaned = clean_url(target, fix_x=fix_x)
        if cleaned != url and cleaned not in results:
            results.append(cleaned)
    return results


def find_cleanable_links(text: str, fix_x: bool = True) -> list[str]:
    """Return cleaned versions of every link in `text` that actually changed (deduped, in order)."""
    urls = extract_urls(text)
    return _collect(urls, urls, fix_x)


async def find_cleanable_links_async(
    text: str, fix_x: bool = True, expand: Callable[[str], Awaitable[str]] | None = None
) -> list[str]:
    """Like find_cleanable_links, but first runs each link through `expand` (e.g. to follow short links)."""
    urls = extract_urls(text)
    targets = await asyncio.gather(*(expand(u) for u in urls)) if expand else urls
    return _collect(urls, list(targets), fix_x)
