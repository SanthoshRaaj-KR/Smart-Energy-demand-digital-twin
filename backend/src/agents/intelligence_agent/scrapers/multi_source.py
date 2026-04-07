"""
scrapers/multi_source.py
========================
Real-Time Multi-Source Scraper for India Energy Intelligence

Sources:
1. Official Indian Grid / Government RSS feeds
2. Google News RSS (no API key required, real-time)
3. GDELT GEO API (free, real-time global news with geo tagging)
4. Economic/Financial RSS feeds
5. Direct HTML scraping (fallback)
"""

from __future__ import annotations

import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

# Disable SSL warnings for government sites with bad certificates
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ---------------------------------------------------------------------------
# FEED REGISTRY
# ---------------------------------------------------------------------------

# ── Tier 1: Official Indian Grid & Government (highest trust, 0.95+)
OFFICIAL_FEEDS: Dict[str, str] = {
    "Grid-India NLDC":     "https://grid-india.in/feed/",
    "NRLDC North":         "https://nrldc.in/feed/",
    "WRLDC West":          "https://wrldc.in/feed/",
    "SRLDC South":         "https://srldc.in/feed/",
    "ERLDC East":          "https://erldc.in/feed/",
    "PIB India":           "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
    "CEA India":           "https://cea.nic.in/rss_feed/",
    "Coal India":          "https://www.coal.gov.in/rss",
}

# ── Tier 2: Energy & Economic News (trust 0.78–0.88)
ENERGY_ECONOMY_FEEDS: Dict[str, str] = {
    "ET Energy":           "https://energy.economictimes.indiatimes.com/rss/topstories",
    "Business Standard Power": "https://www.business-standard.com/rss/power-102.rss",
    "Moneycontrol Energy": "https://www.moneycontrol.com/rss/energy.xml",
    "LiveMint Energy":     "https://www.livemint.com/rss/industry",
    "ET Economy":          "https://economictimes.indiatimes.com/rssfeeds/1373380680.cms",
    "Bloomberg Quint":     "https://www.ndtvprofit.com/feed",
    "Oilprice.com":        "https://oilprice.com/rss/main",
    "Platts Energy":       "https://www.spglobal.com/commodityinsights/en/rss-feed/oil",
}

# ── Tier 3: General India News (political, social, war — trust 0.68–0.80)
INDIA_NEWS_FEEDS: Dict[str, str] = {
    "TOI India":           "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms",
    "Hindustan Times":     "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
    "NDTV India":          "https://www.ndtv.com/rss/india",
    "The Hindu":           "https://www.thehindu.com/news/national/feeder/default.rss",
    "Indian Express":      "https://indianexpress.com/feed/",
    "Scroll.in":           "https://scroll.in/feed",
    "The Wire":            "https://thewire.in/feed",
}

# ── Tier 4: Geopolitical / War / International (trust 0.72–0.85)
GEOPOLITICAL_FEEDS: Dict[str, str] = {
    "Reuters World":       "https://feeds.reuters.com/reuters/worldnews",
    "Reuters Business":    "https://feeds.reuters.com/reuters/businessnews",
    "AP News World":       "https://rsshub.app/apnews/topics/world-news",
    "Al Jazeera":          "https://www.aljazeera.com/xml/rss/all.xml",
    "BBC South Asia":      "https://feeds.bbci.co.uk/news/world/south_asia/rss.xml",
    "BBC Business":        "https://feeds.bbci.co.uk/news/business/rss.xml",
    "France24 Economy":    "https://www.france24.com/en/economy/rss",
    "Defense News":        "https://www.defensenews.com/arc/outboundfeeds/rss/",
}

# ── Google News RSS queries (real-time, no API key)
GNEWS_RSS_QUERIES: Dict[str, str] = {
    "India energy crisis":     "India+energy+crisis+power",
    "India coal shortage":     "India+coal+shortage+electricity",
    "India electricity":       "India+electricity+grid+power+shortage",
    "India economic":          "India+economy+inflation+fuel+prices",
    "India political unrest":  "India+strike+protest+bandh+unrest",
    "India war geopolitical":  "India+war+border+conflict+geopolitical",
    "India Pakistan tension":  "India+Pakistan+tension+border",
    "India China border":      "India+China+border+LAC",
    "crude oil prices":        "crude+oil+prices+OPEC+India",
    "LNG gas prices India":    "LNG+natural+gas+prices+India+import",
    "India solar wind power":  "India+solar+wind+renewable+energy",
    "India floods heatwave":   "India+floods+heatwave+cyclone+weather",
    "India election":          "India+election+voting+BJP+Congress",
    "India subsidy tariff":    "India+electricity+tariff+subsidy+reform",
}


def _gnews_rss_url(query: str) -> str:
    return f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"


# GDELT GEO - free real-time news API with geographic tagging
GDELT_GEO_THEMES = [
    "ENERGY",
    "ECON_INFLATION",
    "ECON_OILPRICE",
    "PROTEST",
    "ELECTION_GENERAL",
    "WAR",
    "MILITARY",
    "UNREST_STRIKES",
    "NATURAL_DISASTER",
    "WEATHER_STORM",
]


SOURCE_TRUST: Dict[str, float] = {
    "grid-india": 0.97, "nldc": 0.97, "nrldc": 0.95, "wrldc": 0.95,
    "srldc": 0.95, "erldc": 0.95, "pib": 0.92, "cea": 0.90,
    "coal india": 0.88, "economic times": 0.82, "et energy": 0.84,
    "business standard": 0.80, "livemint": 0.79, "moneycontrol": 0.79,
    "bloomberg": 0.85, "reuters": 0.88, "bbc": 0.86, "ap news": 0.86,
    "the hindu": 0.80, "hindustan times": 0.74, "ndtv": 0.72,
    "times of india": 0.71, "indian express": 0.76, "al jazeera": 0.78,
    "france24": 0.77, "oilprice": 0.75, "defense news": 0.78,
    "google news": 0.68, "gdelt": 0.65, "scroll": 0.70, "the wire": 0.72,
}


# ---------------------------------------------------------------------------
# RAW ARTICLE DATACLASS (inline to avoid circular import)
# ---------------------------------------------------------------------------
from dataclasses import dataclass


@dataclass
class RawArticle:
    source_name: str
    source_url: str
    title: str
    description: str
    url: str
    published: str
    scraped_at: str
    feed_type: str


# ---------------------------------------------------------------------------
# SCRAPER
# ---------------------------------------------------------------------------

class MultiSourceScraper:
    """
    Aggregates real-time news from:
      - Official Indian grid/government RSS
      - Energy & economic RSS
      - General India news RSS
      - Geopolitical RSS
      - Google News RSS (live query-based, no API key)
      - GDELT GEO API (free, real-time, geo-tagged)
    """

    MAX_ITEMS_PER_FEED = 20
    REQUEST_TIMEOUT = 12
    MAX_WORKERS = 12

    def __init__(self):
        self._session = self._build_session()
        self._seen: Set[str] = set()
        self._lock = Lock()

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------

    def scrape_all(self, include_gdelt: bool = True) -> List[RawArticle]:
        """Scrape all sources and return deduplicated articles."""
        self._seen.clear()
        articles: List[RawArticle] = []

        # Build task list: (feed_name, url, feed_type)
        tasks: List[tuple] = []

        for name, url in OFFICIAL_FEEDS.items():
            tasks.append((name, url, "rss_official"))
        for name, url in ENERGY_ECONOMY_FEEDS.items():
            tasks.append((name, url, "rss_energy"))
        for name, url in INDIA_NEWS_FEEDS.items():
            tasks.append((name, url, "rss_india"))
        for name, url in GEOPOLITICAL_FEEDS.items():
            tasks.append((name, url, "rss_geo"))
        for name, query in GNEWS_RSS_QUERIES.items():
            tasks.append((name, _gnews_rss_url(query), "gnews_rss"))

        print(f"\n[MultiSourceScraper] Scraping {len(tasks)} feeds in parallel...")

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as pool:
            futures = {
                pool.submit(self._scrape_feed, name, url, ftype): (name, url)
                for name, url, ftype in tasks
            }
            # Add timeout to prevent indefinite hanging
            completed = 0
            total = len(futures)
            try:
                for future in as_completed(futures, timeout=60):  # 60 second total timeout
                    try:
                        result = future.result(timeout=15)  # 15 second per-future timeout
                        articles.extend(result)
                        completed += 1
                        print(f"  Progress: {completed}/{total} feeds completed")
                    except Exception as e:
                        name, url = futures[future]
                        print(f"  ERR [{name}]: {str(e)[:60]}")
                        completed += 1
            except TimeoutError:
                print(f"\n⏰ Time's up! Leaving {total - completed} slow websites behind and proceeding with {completed} feeds collected.")
                print(f"   Collected {len(articles)} articles so far. Moving on...")

        # GDELT (sequential — single HTTP call)
        if include_gdelt:
            try:
                gdelt_articles = self._scrape_gdelt()
                articles.extend(gdelt_articles)
                print(f"  [GDELT] {len(gdelt_articles)} articles")
            except Exception as e:
                print(f"  [GDELT] Failed: {str(e)[:60]}")

        # Sort newest first
        articles.sort(key=lambda a: a.published, reverse=True)
        print(f"[MultiSourceScraper] Total unique articles: {len(articles)}")
        return articles

    def scrape_targeted(self, extra_queries: List[str] = None) -> List[RawArticle]:
        """Run only Google News targeted queries + official feeds."""
        self._seen.clear()
        articles: List[RawArticle] = []
        tasks = []

        for name, url in OFFICIAL_FEEDS.items():
            tasks.append((name, url, "rss_official"))
        for name, url in ENERGY_ECONOMY_FEEDS.items():
            tasks.append((name, url, "rss_energy"))

        queries = dict(GNEWS_RSS_QUERIES)
        if extra_queries:
            for q in extra_queries:
                queries[q] = q.replace(" ", "+")

        for name, query in queries.items():
            tasks.append((name, _gnews_rss_url(query), "gnews_rss"))

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as pool:
            futures = {
                pool.submit(self._scrape_feed, name, url, ftype): (name, url)
                for name, url, ftype in tasks
            }
            # Add timeout to prevent indefinite hanging
            completed = 0
            total = len(futures)
            try:
                for future in as_completed(futures, timeout=60):  # 60 second total timeout
                    try:
                        result = future.result(timeout=15)  # 15 second per-future timeout
                        articles.extend(result)
                        completed += 1
                    except Exception as e:
                        name, url = futures[future]
                        print(f"  ERR [{name}]: {str(e)[:60]}")
                        completed += 1
            except TimeoutError:
                print(f"\n⏰ Time's up! Leaving {total - completed} slow websites behind. Proceeding with {len(articles)} articles.")

        articles.sort(key=lambda a: a.published, reverse=True)
        return articles

    # ------------------------------------------------------------------
    # GDELT
    # ------------------------------------------------------------------

    def _scrape_gdelt(self) -> List[RawArticle]:
        """
        Query GDELT GEO API — free, no API key, real-time.
        Filters for India + energy/political/economic themes.
        """
        articles = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # GDELT Article Search API v2
        base = "https://api.gdeltproject.org/api/v2/doc/doc"
        queries = [
            "India energy electricity power",
            "India coal fuel shortage",
            "India war conflict border military",
            "India protest strike bandh",
            "India economy inflation tariff",
            "India Pakistan China geopolitical",
            "crude oil LNG price India",
            "India heatwave flood cyclone disaster",
        ]

        for idx, query in enumerate(queries):
            try:
                params = {
                    "query": f"{query} sourcelang:english",
                    "mode": "artlist",
                    "maxrecords": 25,
                    "sort": "DateDesc",
                    "format": "json",
                    "timespan": "12h",  # last 12 hours only
                }
                r = self._session.get(base, params=params, timeout=10, verify=True)  # GDELT has valid SSL
                if r.status_code != 200:
                    print(f"  [GDELT] Query {idx+1}/{len(queries)}: HTTP {r.status_code}")
                    continue
                data = r.json()
                count = 0
                for art in data.get("articles", []):
                    title = art.get("title", "").strip()
                    url_ = art.get("url", "")
                    if not title or not url_:
                        continue
                    if not self._is_unique(title, url_):
                        continue
                    articles.append(RawArticle(
                        source_name="GDELT",
                        source_url="https://gdeltproject.org",
                        title=title,
                        description=art.get("seendescription", "")[:400],
                        url=url_,
                        published=art.get("seendate", now_iso),
                        scraped_at=now_iso,
                        feed_type="gdelt",
                    ))
                    count += 1
                print(f"  [GDELT] Query {idx+1}/{len(queries)}: {count} articles")
                time.sleep(0.5)  # respect rate limit
            except requests.exceptions.Timeout:
                print(f"  [GDELT] Query {idx+1}/{len(queries)}: Timeout")
            except Exception as e:
                print(f"  [GDELT] Query {idx+1}/{len(queries)}: {str(e)[:40]}")

        return articles

    # ------------------------------------------------------------------
    # RSS
    # ------------------------------------------------------------------

    def _scrape_feed(
        self, feed_name: str, url: str, feed_type: str
    ) -> List[RawArticle]:
        articles = []
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # SSL bypass for government sites with bad certificates
        verify_ssl = True
        gov_domains = ['nldc.in', 'nrldc.in', 'wrldc.in', 'srldc.in', 'erldc.in', 
                       'grid-india.in', 'cea.nic.in', 'pib.gov.in', 'coal.gov.in']
        if any(domain in url.lower() for domain in gov_domains):
            verify_ssl = False

        for attempt in range(1, 3):
            try:
                r = self._session.get(url, timeout=self.REQUEST_TIMEOUT, verify=verify_ssl)
                if r.status_code not in (200, 301, 302):
                    break

                feed = feedparser.parse(r.content)
                entries = feed.entries[: self.MAX_ITEMS_PER_FEED]

                for entry in entries:
                    title = self._get_text(entry, "title")
                    if not title:
                        continue
                    desc = self._get_text(entry, "summary") or self._get_text(entry, "description") or ""
                    desc = BeautifulSoup(desc, "html.parser").get_text()[:500]
                    link = getattr(entry, "link", url)
                    pub = self._parse_date(entry)

                    if not self._is_unique(title, link):
                        continue

                    articles.append(RawArticle(
                        source_name=feed_name,
                        source_url=url,
                        title=title,
                        description=desc,
                        url=link,
                        published=pub,
                        scraped_at=now_iso,
                        feed_type=feed_type,
                    ))

                if articles or feed.entries:
                    print(f"  OK  [{feed_type}] {feed_name}: {len(articles)} items")
                    break

            except requests.exceptions.Timeout:
                if attempt == 2:
                    print(f"  ERR [{feed_type}] {feed_name}: Timeout")
            except Exception as e:
                if attempt == 2:
                    print(f"  ERR [{feed_type}] {feed_name}: {str(e)[:60]}")
            time.sleep(0.5 * attempt)

        return articles

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        # Stealth headers - pretend to be a real Chrome browser
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml, application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        # Retry adapter
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        return s

    def _is_unique(self, title: str, url: str) -> bool:
        key = hashlib.md5(
            f"{title[:80].lower().strip()}|{urlparse(url).netloc}".encode()
        ).hexdigest()
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            return True

    @staticmethod
    def _get_text(entry: Any, attr: str) -> str:
        val = getattr(entry, attr, None)
        if val is None:
            return ""
        if isinstance(val, str):
            return val.strip()
        if isinstance(val, list) and val:
            return str(val[0].get("value", "")).strip()
        return str(val).strip()

    @staticmethod
    def _parse_date(entry: Any) -> str:
        for attr in ("published", "updated", "created"):
            raw = getattr(entry, f"{attr}_parsed", None)
            if raw:
                try:
                    import calendar
                    ts = calendar.timegm(raw)
                    return datetime.utcfromtimestamp(ts).isoformat()
                except Exception:
                    pass
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def trust_score(source_name: str) -> float:
        low = source_name.lower()
        for key, score in SOURCE_TRUST.items():
            if key in low:
                return score
        return 0.62
