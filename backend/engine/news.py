"""News aggregator: publisher RSS feeds + Finnhub (general + company news), deduplicated and tagged with tickers.

Only the headline, a short summary and the link are kept: the article opens on the publisher's site.
"""

from __future__ import annotations

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

RSS_FEEDS: list[tuple[str, str]] = [
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_marketpulse"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
    ("Nasdaq", "https://www.nasdaq.com/feed/rssoutbound?category=Markets"),
    ("Nasdaq", "https://www.nasdaq.com/feed/rssoutbound?category=Earnings"),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml"),
    ("Fox Business", "https://moxie.foxbusiness.com/google-publisher/markets.xml"),
]
MAX_AGE = timedelta(hours=48)
_TAG = re.compile(r"<[^>]+>")
_CASHTAG = re.compile(r"\$([A-Z]{1,5}(?:\.[A-Z])?)\b")
_EXCH = re.compile(r"\((?:NYSE|NASDAQ|Nasdaq|NYSEARCA|AMEX)\s*:\s*([A-Z]{1,5}(?:\.[A-Z])?)\)")
_SUFFIX = re.compile(r"[,.]?\s+(Inc|Incorporated|Corp|Corporation|Co|Company|Ltd|plc|PLC|Holdings|Group|Class [A-C]|N\.V|S\.A|SE|AG)\.?$")


def _clean(s: str | None, n: int = 400) -> str:
    s = html.unescape(_TAG.sub(" ", s or ""))
    return re.sub(r"\s+", " ", s).strip()[:n]


def _date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def parse_feed(xml: bytes | str, source: str) -> list[dict]:
    """RSS 2.0 or Atom → [{title, url, summary, published, source}]."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    atom = "{http://www.w3.org/2005/Atom}"
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        get = lambda name: next((c for c in it if c.tag.split("}")[-1] == name), None)
        title = _clean(getattr(get("title"), "text", ""), 300)
        link_el = get("link")
        url = (link_el.text or "").strip() if link_el is not None and link_el.text else (link_el.get("href") if link_el is not None else "")
        summary = _clean(getattr(get("description"), "text", None) or getattr(get("summary"), "text", None) or "")
        pub = _date(getattr(get("pubDate"), "text", None) or getattr(get("published"), "text", None) or getattr(get("updated"), "text", None))
        if title and url:
            out.append({"title": title, "url": url, "summary": summary, "published": pub, "source": source})
    _ = atom
    return out


def name_index(meta: dict[str, dict]) -> list[tuple[re.Pattern, str]]:
    """Company names → ticker, for tagging headlines ("Nvidia shares jump" → NVDA). Only distinctive names."""
    out = []
    for sym, m in meta.items():
        name = _SUFFIX.sub("", (m.get("name") or "").strip())
        name = _SUFFIX.sub("", name)
        if m.get("sector") in ("ETF", "Index") or len(name) < 4 or name.lower() in {"target", "visa", "apple inc", "general", "first", "united"}:
            continue
        out.append((re.compile(r"\b" + re.escape(name) + r"('s)?\b", re.IGNORECASE), sym))
    return out


def tickers(text: str, known: set[str], names: list[tuple[re.Pattern, str]]) -> list[str]:
    found = [t for t in _CASHTAG.findall(text) + _EXCH.findall(text) if t in known]
    if not found:
        found = [sym for rx, sym in names if rx.search(text)]
    return list(dict.fromkeys(found))[:3]


def _key(title: str) -> str:
    norm = re.sub(r"[^a-z0-9 ]", "", title.lower())
    norm = re.sub(r"\s+", " ", norm).strip()[:90]
    return "news:" + hashlib.sha1(norm.encode()).hexdigest()[:16]


def to_feed_items(items: list[dict], known: set[str], names: list[tuple[re.Pattern, str]], now: datetime | None = None,
                  skip_keys: set[str] | None = None, limit: int | None = None) -> list[dict]:
    """Feed items (kind "news"), newest first, one per headline even if several publishers carry it.
    Headlines already stored (skip_keys) are dropped and at most `limit` are kept before the (costly) ticker tagging."""
    now = now or datetime.now(timezone.utc)
    seen, fresh = set(skip_keys or ()), []
    for n in sorted(items, key=lambda x: x.get("published") or now, reverse=True):
        if n.get("published") and now - n["published"] > MAX_AGE:
            continue
        k = _key(n["title"])
        if k in seen:
            continue
        seen.add(k)
        fresh.append((k, n))
        if limit is not None and len(fresh) >= limit:
            break
    out = []
    for k, n in fresh:
        syms = n.get("symbols") or tickers(f"{n['title']} {n.get('summary', '')}", known, names)
        out.append({"key": k, "kind": "news", "symbol": syms[0] if syms else None, "severity": "info", "title": n["title"],
                    "body": n.get("summary", ""), "url": n["url"]})
    return out


def keys_of(items: list[dict]) -> list[str]:
    return list(dict.fromkeys(_key(n["title"]) for n in items if n.get("title")))


def finnhub_items(rows: list[dict], source_default: str = "Finnhub") -> list[dict]:
    out = []
    for n in rows:
        title = _clean(n.get("headline") or n.get("title"), 300)
        if not title or not n.get("url"):
            continue
        related = [s for s in (n.get("related") or "").split(",") if s and s.isupper() and len(s) <= 6]
        pub = datetime.fromtimestamp(n["datetime"], tz=timezone.utc) if isinstance(n.get("datetime"), (int, float)) else None
        out.append({"title": title, "url": n["url"], "summary": _clean(n.get("summary")), "published": pub,
                    "source": n.get("source") or source_default, "symbols": related})
    return out


def collect(fetch, fh=None, company_symbols: list[str] | None = None, finnhub_general: bool = True) -> list[dict]:
    """All headlines: fetch(url) -> bytes for the RSS feeds (failures skipped), plus Finnhub when configured."""
    items: list[dict] = []
    for source, url in RSS_FEEDS:
        try:
            items += parse_feed(fetch(url), source)
        except Exception:
            continue
    if fh is not None and finnhub_general:
        for cat in ("general", "merger"):
            try:
                items += finnhub_items(fh.get("/news", category=cat) or [])
            except Exception:
                pass
    if fh is not None:
        for sym in company_symbols or []:
            try:
                items += finnhub_items(fh.news(sym, days=2))
            except Exception:
                continue
    return items
