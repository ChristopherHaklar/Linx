"""Link cleaning: strips tracking query params and rewrites X/Twitter links to fixvx.com."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
SITE_TRACKING_PARAMS = {
    "x.com": {"s", "t"},
    "twitter.com": {"s", "t"},
    "youtube.com": {"si", "feature", "pp"},
    "youtu.be": {"si", "feature"},
    "open.spotify.com": {"si", "context"},
    "instagram.com": {"igsh", "img_index"},
    "tiktok.com": {"_r", "_t", "is_from_webapp", "sender_device", "sender_web_id", "share_app_id"},
    "reddit.com": {"share_id", "rdt"},
    "amazon.com": {"ref", "ref_", "tag", "psc", "th", "linkcode", "creative", "camp"},
    "aliexpress.com": {"spm", "scm", "pvid", "algo_pvid", "algo_exp_id"},
    "linkedin.com": {"trk", "trackingid", "lipi", "rcm"},
}

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


def _site_params(host: str) -> set[str]:
    base = _base_domain(host)
    for domain, params in SITE_TRACKING_PARAMS.items():
        # match amazon.com, amazon.co.uk, amazon.de, etc. via the second-level name
        if base == domain or base.endswith("." + domain):
            return params
        if domain == "amazon.com" and re.fullmatch(r"amazon\.[a-z.]+", base):
            return params
    return set()


def _is_tracking(key: str, host: str) -> bool:
    k = key.lower()
    return (
        k in GLOBAL_TRACKING_PARAMS
        or k.startswith(GLOBAL_TRACKING_PREFIXES)
        or k in _site_params(host)
    )


def clean_url(url: str, fix_x: bool = True) -> str:
    """Return the URL with tracking params removed and (optionally) X links sent to fixvx."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    host = parts.hostname or ""
    netloc = parts.netloc
    query = parts.query

    if query:
        pairs = parse_qsl(query, keep_blank_values=True)
        kept = [(k, v) for k, v in pairs if not _is_tracking(k, host)]
        if len(kept) != len(pairs):
            query = urlencode(kept, doseq=True)

    if fix_x and _base_domain(host) in X_HOSTS:
        netloc = FIX_X_HOST

    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


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


def find_cleanable_links(text: str, fix_x: bool = True) -> list[str]:
    """Return cleaned versions of every link in `text` that actually changed (deduped, in order)."""
    results: list[str] = []
    for match in URL_RE.finditer(text):
        url, _ = _split_trailing(match.group(0))
        cleaned = clean_url(url, fix_x=fix_x)
        if cleaned != url and cleaned not in results:
            results.append(cleaned)
    return results
