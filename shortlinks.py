"""Expand short links (amzn.to, vm.tiktok.com, ...) by reading their redirect, so the real link can be cleaned."""

import logging
import re
from urllib.parse import urljoin, urlsplit

import aiohttp

log = logging.getLogger("linx.shortlinks")

AMAZON_HOST = r"(?:www\.|smile\.)?amazon\.[a-z.]+"
TIKTOK_HOST = r"(?:www\.|m\.)?tiktok\.com"

# Shortener host -> pattern the final host must match. Only these hosts are ever requested.
SHORTENERS = {
    "amzn.to": AMAZON_HOST,
    "amzn.eu": AMAZON_HOST,
    "amzn.asia": AMAZON_HOST,
    "a.co": AMAZON_HOST,
    "vm.tiktok.com": TIKTOK_HOST,
    "vt.tiktok.com": TIKTOK_HOST,
    "spotify.link": r"open\.spotify\.com",
    "pin.it": r"(?:[a-z]{2}\.|www\.)?pinterest\.[a-z.]+",
}
# Short links that live on the main site, recognized by path.
PATH_SHORTENERS = {
    "tiktok.com": (re.compile(r"/t/[A-Za-z0-9]+/?"), TIKTOK_HOST),
    "reddit.com": (re.compile(r"/r/[^/]+/s/[A-Za-z0-9]+/?"), r"(?:www\.|old\.|new\.)?reddit\.com"),
}
# Pinterest bounces through its API host before reaching the pin.
PASSTHROUGH_HOSTS = {"api.pinterest.com"}

MAX_HOPS = 5
TIMEOUT = aiohttp.ClientTimeout(total=6)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
}


def _strip_www(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def short_link_target(url: str) -> str | None:
    """If `url` is a known short link, return the pattern its destination host must match."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if host in SHORTENERS:
        return SHORTENERS[host]
    rule = PATH_SHORTENERS.get(_strip_www(host))
    if rule and rule[0].fullmatch(parts.path):
        return rule[1]
    return None


def is_real_destination(url: str, host_pattern: str) -> bool:
    """Reject redirects to a homepage or listing, which is where dead short codes end up."""
    parts = urlsplit(url)
    if not re.fullmatch(host_pattern, (parts.hostname or "").lower()):
        return False
    path = parts.path.rstrip("/")
    if not path:
        return False
    if "reddit" in host_pattern and "/comments/" not in path:
        return False
    return True


class ShortLinkExpander:
    """Follows redirects from known shorteners only, without loading the destination page."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def __call__(self, url: str) -> str:
        """Return the expanded link, or `url` unchanged if it isn't a short link or can't be expanded."""
        host_pattern = short_link_target(url)
        if host_pattern is None:
            return url
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=TIMEOUT, headers=HEADERS)
        current = url
        try:
            for _ in range(MAX_HOPS):
                async with self._session.get(current, allow_redirects=False) as resp:
                    location = resp.headers.get("Location")
                    if resp.status not in (301, 302, 303, 307, 308) or not location:
                        break
                current = urljoin(current, location)
                host = (urlsplit(current).hostname or "").lower()
                if short_link_target(current) is None and host not in PASSTHROUGH_HOSTS:
                    break  # reached the destination; no need to load it
        except (aiohttp.ClientError, TimeoutError) as exc:
            log.info("Could not expand %s: %s", url, exc)
            return url
        if current != url and is_real_destination(current, host_pattern):
            return current
        return url
