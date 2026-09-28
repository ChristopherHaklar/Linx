"""Link cleaning: strips tracking query params and rewrites X/Twitter links to fixvx.com."""

import asyncio
import re
from collections.abc import Awaitable, Callable
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit

URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)

# Query params removed from every URL.
GLOBAL_TRACKING_PARAMS = {
    "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid", "msclkid", "yclid",
    "ttclid", "twclid", "li_fat_id", "igshid", "igsh", "mc_cid", "mc_eid",
    "_hsenc", "_hsmi", "mkt_tok", "oly_anon_id", "oly_enc_id", "vero_id",
    "rb_clickid", "wt_mc", "_ga", "_gl", "ref_src", "ref_url", "srsltid",
}
GLOBAL_TRACKING_PREFIXES = ("utm_", "pk_", "hsa_")

# Params that are only tracking on specific sites (they may be meaningful elsewhere).
# Subdomains match too, so "reddit.com" covers old.reddit.com.
SITE_TRACKING_PARAMS = {
    "x.com": {"s", "t"},
    "twitter.com": {"s", "t"},
    "youtube.com": {"si", "feature", "pp"},
    "youtu.be": {"si", "feature"},
    "open.spotify.com": {"si", "context"},
    "instagram.com": {"igsh", "img_index"},
    "tiktok.com": {"_r", "_d", "_t", "is_from_webapp", "sender_device", "sender_web_id", "share_app_id",
                   "share_item_id", "share_link_id", "u_code", "timestamp", "social_share_type",
                   "sec_user_id", "checksum", "tt_from", "source", "refer"},
    "reddit.com": {"share_id", "rdt"},
    "aliexpress.com": {"spm", "scm", "pvid", "algo_pvid", "algo_exp_id"},
    "linkedin.com": {"trk", "trackingid", "lipi", "rcm"},
    "facebook.com": {"mibextid", "rdid", "sfnsn", "__tn__", "__cft__", "extid", "ref", "fref", "hc_ref",
                     "hc_location", "paipv", "eav", "acontext", "notif_id", "notif_t", "comment_tracking", "xts"},
}

# Sites spread across country domains (amazon.co.uk, google.de, ...), matched by name.
COUNTRY_SITE_PARAMS = {
    "amazon": {"ref", "ref_", "tag", "psc", "th", "linkcode", "creative", "camp", "creativeasin", "ascsubtag",
               "keywords", "qid", "sr", "crid", "sprefix", "dib", "dib_tag", "content-id", "_encoding",
               "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t",
               "pf_rd_i", "pf_rd_m", "social_share", "starsleft", "linkid", "ie"},
    # Search-page noise; q, tbm, udm, tbs, start and hl are kept.
    "google": {"ei", "ved", "uact", "oq", "gs_lp", "gs_lcrp", "gs_l", "gs_ssp", "sclient", "sxsrf", "sca_esv",
               "sca_upv", "source", "sourceid", "ie", "oe", "rlz", "bih", "biw", "dpr", "iflsig", "aqs",
               "client", "sa", "usg", "cshid", "fbs", "prmd", "lei", "mstk", "csui", "zx", "no_sw_cr"},
}
COUNTRY_TLD = r"(?:com|co\.[a-z]{2}|com\.[a-z]{2}|[a-z]{2})"

# Link wrappers that carry the real destination in a query param.
FACEBOOK_WRAPPER_HOSTS = {"l.facebook.com", "lm.facebook.com", "l.messenger.com", "l.instagram.com"}

# Amazon product pages: /Some-Product-Name/dp/B0XXXXXXXX/ref=... -> /dp/B0XXXXXXXX
AMAZON_PRODUCT_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?=/|$)", re.IGNORECASE)

X_HOSTS = {"x.com", "twitter.com"}
FIX_X_HOST = "fixvx.com"

TRAILING_PUNCT = ".,!?;:"


def _base_domain(host: str) -> str:
    """Strip common subdomains so www.youtube.com / m.youtube.com match youtube.com."""
    host = host.lower().rstrip(".")
    for prefix in ("www.", "m.", "mobile.", "music."):
        if host.startswith(prefix):
            return host[len(prefix):]
    return host


def _country_site(host: str) -> str | None:
    """Return "amazon" for amazon.co.uk, "google" for www.google.de, etc."""
    base = _base_domain(host)
    for name in COUNTRY_SITE_PARAMS:
        if re.fullmatch(rf"{name}\.{COUNTRY_TLD}", base):
            return name
    return None


def _site_params(host: str) -> set[str]:
    country_site = _country_site(host)
    if country_site:
        return COUNTRY_SITE_PARAMS[country_site]
    base = _base_domain(host)
    for domain, params in SITE_TRACKING_PARAMS.items():
        if base == domain or base.endswith("." + domain):
            return params
    return set()


def _is_tracking(key: str, host: str) -> bool:
    k = key.lower().split("[", 1)[0]  # __cft__[0] -> __cft__
    return (
        k in GLOBAL_TRACKING_PARAMS
        or k.startswith(GLOBAL_TRACKING_PREFIXES)
        or k in _site_params(host)
    )


def _unwrap(url: str) -> str:
    """Follow google.com/url?q= and l.facebook.com/l.php?u= style wrappers to their destination."""
    for _ in range(3):  # wrappers can be nested
        try:
            parts = urlsplit(url)
        except ValueError:
            return url
        host = (parts.hostname or "").lower()
        query = parse_qs(parts.query)
        if host in FACEBOOK_WRAPPER_HOSTS and parts.path in ("/l.php", "/"):
            keys = ("u",)
        elif _country_site(host) == "google" and parts.path == "/url":
            keys = ("q", "url")
        else:
            return url
        target = next((query[k][0] for k in keys if k in query), "")
        if not target.lower().startswith(("http://", "https://")):
            return url
        url = target
    return url


def clean_url(url: str, fix_x: bool = True) -> str:
    """Return the URL with tracking params removed and (optionally) X links sent to fixvx."""
    url = _unwrap(url)
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    host = parts.hostname or ""
    netloc = parts.netloc
    path = parts.path
    query = parts.query

    if query:
        pairs = parse_qsl(query, keep_blank_values=True)
        kept = [(k, v) for k, v in pairs if not _is_tracking(k, host)]
        if len(kept) != len(pairs):
            query = urlencode(kept, doseq=True)

    if _country_site(host) == "amazon":
        product = AMAZON_PRODUCT_RE.search(path)
        if product:
            path = f"/dp/{product.group(1)}"
        else:
            path = "/".join(seg for seg in path.split("/") if not seg.lower().startswith("ref="))

    if fix_x and _base_domain(host) in X_HOSTS:
        netloc = FIX_X_HOST

    return urlunsplit((parts.scheme, netloc, path, query, parts.fragment))


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
