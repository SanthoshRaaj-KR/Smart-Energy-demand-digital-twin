"""
monitors/classifier.py
======================
Keyword-based real-time event classifier.

Classifies RawArticles into EnrichedEvents with:
- Category (energy, economic, political, weather, military, geopolitical)
- Severity (LOW → CRITICAL)
- Affected Indian states
- Estimated MW delta
- Impact direction
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# DATA CLASSES (self-contained, no circular import)
# ---------------------------------------------------------------------------

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


@dataclass
class EnrichedEvent:
    event_id: str
    title: str
    summary: str
    url: str
    published: str
    source: str
    feed_type: str
    category: str
    subcategory: str
    severity: str
    confidence: float
    affected_states: List[str]
    affected_regions: List[str]
    is_national: bool
    estimated_delta_mw: float
    impact_direction: str
    eta_hours: float
    duration_hours: float
    keywords_matched: List[str]
    raw_text: str


# ---------------------------------------------------------------------------
# TAXONOMY & KEYWORDS
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS: Dict[str, Dict[str, List[str]]] = {

    "energy": {
        "power_outage": [
            "blackout", "power cut", "load shedding", "load-shedding",
            "power outage", "electricity cut", "power failure", "tripping",
            "grid failure", "grid collapse", "frequency dip",
        ],
        "coal_supply": [
            "coal shortage", "coal crisis", "coal stock", "coal supply",
            "pit-head stock", "coal dispatch", "coal rake",
            "thermal plant shutdown", "thermal unit tripped",
        ],
        "fuel_supply": [
            "gas shortage", "lng shortage", "fuel shortage", "fuel supply",
            "gas supply disruption", "pipeline", "regasification",
        ],
        "renewable": [
            "solar power", "wind power", "renewable energy", "green energy",
            "hydro power", "dam", "hydroelectric", "solar capacity",
        ],
        "transmission": [
            "transmission line", "substation", "transformer failure",
            "grid congestion", "interstate transfer", "hvdc",
        ],
        "capacity_addition": [
            "new plant", "capacity addition", "commissioning", "inaugurated",
            "power plant commissioned", "mw added",
        ],
    },

    "economic": {
        "coal_price": [
            "coal price", "coal cost", "thermal coal price",
            "coal auction", "linkage coal", "e-auction coal",
        ],
        "fuel_price": [
            "crude oil price", "oil price", "brent crude", "wti crude",
            "lng price", "natural gas price", "fuel cost", "petrol price",
            "diesel price", "fuel hike",
        ],
        "tariff_regulation": [
            "electricity tariff", "tariff hike", "tariff revision",
            "power tariff", "regulatory commission", "cerc", "serc",
            "tariff order", "wheeling charge", "cross subsidy",
        ],
        "market_price": [
            "iex price", "power exchange", "day-ahead market", "dam price",
            "spot price", "real time market", "rtm", "power price",
            "ppa", "power purchase agreement",
        ],
        "inflation_forex": [
            "inflation", "rupee fall", "rupee depreciation", "forex",
            "dollar rate", "import cost", "trade deficit",
            "rbi", "interest rate", "repo rate",
        ],
        "subsidy_reform": [
            "power subsidy", "free electricity", "subsidy scheme",
            "dbt", "privatization", "discoms", "discom losses",
            "electricity reform", "billing reform",
        ],
    },

    "political": {
        "strike": [
            "power workers strike", "electricity employees strike",
            "workers strike", "labour strike", "labour unrest",
            "union strike", "work stoppage", "dharna", "chakka jam",
            "pen down strike",
        ],
        "bandh": [
            "bandh", "hartal", "shutdown", "total bandh",
            "bharat bandh", "state bandh",
        ],
        "election": [
            "election", "polling day", "voting", "lok sabha",
            "assembly election", "by-election", "model code of conduct",
            "election commission",
        ],
        "protest": [
            "protest", "agitation", "demonstration", "march",
            "farmer protest", "student protest",
        ],
        "policy": [
            "energy policy", "power ministry", "electricity act",
            "mnre", "ministry of power", "cabinet decision",
            "parliament session", "budget", "power sector reform",
        ],
        "civil_unrest": [
            "curfew", "riot", "communal", "section 144",
            "violence", "shutdown order",
        ],
    },

    "weather": {
        "heatwave": [
            "heatwave", "heat wave", "temperature record", "extreme heat",
            "45 degree", "46 degree", "47 degree", "48 degree",
        ],
        "coldwave": [
            "cold wave", "coldwave", "fog", "cold snap", "dense fog",
            "visibility", "winter demand",
        ],
        "cyclone": [
            "cyclone", "super cyclone", "cyclonic storm", "landfall",
            "imd warning", "red alert",
        ],
        "flood": [
            "flood", "flooding", "heavy rain", "cloudburst",
            "dam breach", "submerged", "inundation",
        ],
        "drought": [
            "drought", "water shortage", "reservoir low",
            "hydro generation fall", "monsoon deficient",
        ],
    },

    "military": {
        "conflict": [
            "war", "airstrike", "military strike", "missile attack",
            "artillery", "shelling", "ceasefire", "combat",
        ],
        "india_border": [
            "india pakistan", "india china", "loc", "lac",
            "border tension", "border standoff", "line of actual control",
            "line of control", "doklam", "galwan", "aksai chin",
        ],
        "sanctions": [
            "sanctions", "export ban", "import ban", "embargo",
            "trade war", "tariff war",
        ],
    },

    "geopolitical": {
        "middle_east": [
            "middle east", "iran", "iraq", "saudi arabia", "opec",
            "strait of hormuz", "gulf", "suez canal", "red sea",
        ],
        "russia_ukraine": [
            "russia", "ukraine", "ukraine war", "russian oil",
            "russian gas", "nord stream", "energy sanctions",
        ],
        "global_supply": [
            "global supply chain", "shipping", "freight cost",
            "port congestion", "coal import", "coal ship",
        ],
        "diplomacy": [
            "bilateral", "trade agreement", "g20", "summit",
            "indo-pacific", "quad", "brics",
        ],
    },
}

# ---------------------------------------------------------------------------
# STATE GEOGRAPHY
# ---------------------------------------------------------------------------

# Full state + DISCOM alias → canonical state code
STATE_MAP: Dict[str, str] = {
    # Full names
    "andhra pradesh": "AP", "telangana": "TS", "karnataka": "KAR",
    "kerala": "KL", "tamil nadu": "TN", "goa": "GA",
    "maharashtra": "MH", "gujarat": "GJ", "rajasthan": "RJ",
    "madhya pradesh": "MP", "chhattisgarh": "CG",
    "uttar pradesh": "UP", "uttarakhand": "UK",
    "delhi": "DL", "haryana": "HR", "punjab": "PB",
    "himachal pradesh": "HP", "jammu and kashmir": "JK",
    "west bengal": "WB", "odisha": "OD", "jharkhand": "JH",
    "bihar": "BH", "assam": "AS", "meghalaya": "ML",
    "manipur": "MN", "tripura": "TR", "nagaland": "NL",
    # Abbreviations
    "ap": "AP", "ts": "TS", "ka": "KAR", "kl": "KL",
    "tn": "TN", "mh": "MH", "gj": "GJ", "rj": "RJ",
    "mp": "MP", "cg": "CG", "up": "UP", "uk": "UK",
    "dl": "DL", "hr": "HR", "pb": "PB", "hp": "HP",
    "jk": "JK", "wb": "WB", "od": "OD", "jh": "JH",
    "bh": "BH", "as": "AS",
    # DISCOMs → state
    "uppcl": "UP", "mvvnl": "UP", "pvvnl": "UP",
    "nbpdcl": "BH", "sbpdcl": "BH",
    "cesc": "WB", "wbsedcl": "WB",
    "bescom": "KAR", "gescom": "KAR",
    "msedcl": "MH", "adani electricity": "MH",
    "tneb": "TN", "tangedco": "TN",
    "pspcl": "PB", "uhbvn": "HR", "dhbvn": "HR",
    "jvvnl": "RJ", "avvnl": "RJ",
    "ugvcl": "GJ", "mgvcl": "GJ", "dgvcl": "GJ", "pgvcl": "GJ",
    # Cities
    "mumbai": "MH", "pune": "MH", "nagpur": "MH",
    "bengaluru": "KAR", "bangalore": "KAR", "mysuru": "KAR",
    "chennai": "TN", "coimbatore": "TN", "madurai": "TN",
    "kolkata": "WB", "patna": "BH", "ranchi": "JH",
    "lucknow": "UP", "noida": "UP", "agra": "UP", "kanpur": "UP",
    "bhopal": "MP", "indore": "MP",
    "raipur": "CG", "bilaspur": "CG",
    "bhubaneswar": "OD", "cuttack": "OD",
    "ahmedabad": "GJ", "surat": "GJ",
    "jaipur": "RJ", "jodhpur": "RJ",
    "hyderabad": "TS", "vijayawada": "AP", "visakhapatnam": "AP",
    "thiruvananthapuram": "KL", "kochi": "KL",
    "guwahati": "AS", "shillong": "ML",
    "new delhi": "DL",
    "chandigarh": "PB",
    "dehradun": "UK",
    "shimla": "HP",
    "srinagar": "JK", "jammu": "JK",
}

REGION_MAP: Dict[str, List[str]] = {
    "north":       ["DL", "UP", "UK", "HR", "PB", "HP", "JK", "RJ"],
    "south":       ["AP", "TS", "KAR", "KL", "TN", "GA"],
    "west":        ["MH", "GJ", "RJ", "GA"],
    "east":        ["WB", "OD", "JH", "BH", "AS", "ML", "MN", "TR", "NL"],
    "central":     ["MP", "CG"],
}

NATIONAL_TRIGGERS = [
    "india", "national", "grid", "nldc", "all states", "pan india",
    "coal india", "ministry of power", "central government", "cabinet",
    "parliament", "rbi", "budget", "bharat",
]

# ---------------------------------------------------------------------------
# IMPACT ESTIMATION
# ---------------------------------------------------------------------------

# Typical peak MW per state (rough)
STATE_PEAK_MW: Dict[str, float] = {
    "UP": 28000, "MH": 31000, "GJ": 21000, "RJ": 16000,
    "TN": 18000, "KAR": 16000, "WB": 9500, "AP": 11000,
    "TS": 9000, "MP": 14000, "CG": 6000, "BH": 7000,
    "JH": 4000, "OD": 5500, "PB": 13000, "HR": 11000,
    "DL": 8000, "KL": 5000, "HP": 1200, "UK": 1800,
    "JK": 2200, "AS": 2800, "ML": 500, "GA": 500,
}

# Category × severity → (pct_of_peak, direction)
IMPACT_TABLE: Dict[str, Dict[str, Tuple[float, str]]] = {
    "energy_power_outage":     {"LOW": (0.04, "supply_down"), "MEDIUM": (0.08, "supply_down"), "HIGH": (0.15, "supply_down"), "CRITICAL": (0.25, "supply_down")},
    "energy_coal_supply":      {"LOW": (0.03, "supply_down"), "MEDIUM": (0.07, "supply_down"), "HIGH": (0.12, "supply_down"), "CRITICAL": (0.20, "supply_down")},
    "energy_fuel_supply":      {"LOW": (0.02, "supply_down"), "MEDIUM": (0.05, "supply_down"), "HIGH": (0.10, "supply_down"), "CRITICAL": (0.18, "supply_down")},
    "energy_transmission":     {"LOW": (0.02, "supply_down"), "MEDIUM": (0.05, "supply_down"), "HIGH": (0.10, "supply_down"), "CRITICAL": (0.15, "supply_down")},
    "energy_capacity_addition":{"LOW": (0.02, "supply_up"),   "MEDIUM": (0.04, "supply_up"),   "HIGH": (0.07, "supply_up"),   "CRITICAL": (0.10, "supply_up")},
    "energy_renewable":        {"LOW": (0.01, "supply_up"),   "MEDIUM": (0.03, "supply_up"),   "HIGH": (0.06, "supply_up"),   "CRITICAL": (0.10, "supply_up")},
    "economic_coal_price":     {"LOW": (0.01, "demand_down"), "MEDIUM": (0.03, "supply_down"), "HIGH": (0.06, "supply_down"), "CRITICAL": (0.10, "supply_down")},
    "economic_fuel_price":     {"LOW": (0.01, "demand_down"), "MEDIUM": (0.03, "supply_down"), "HIGH": (0.05, "supply_down"), "CRITICAL": (0.09, "supply_down")},
    "economic_tariff_regulation":{"LOW":(0.01, "demand_down"),"MEDIUM": (0.03, "demand_down"), "HIGH": (0.05, "both"),        "CRITICAL": (0.08, "both")},
    "economic_market_price":   {"LOW": (0.00, "both"),        "MEDIUM": (0.01, "both"),        "HIGH": (0.03, "both"),        "CRITICAL": (0.05, "both")},
    "economic_inflation_forex": {"LOW": (0.01, "demand_down"),"MEDIUM": (0.02, "supply_down"), "HIGH": (0.04, "supply_down"), "CRITICAL": (0.07, "supply_down")},
    "economic_subsidy_reform": {"LOW": (0.01, "demand_down"), "MEDIUM": (0.03, "both"),        "HIGH": (0.05, "both"),        "CRITICAL": (0.08, "both")},
    "political_strike":        {"LOW": (0.04, "supply_down"), "MEDIUM": (0.08, "supply_down"), "HIGH": (0.15, "supply_down"), "CRITICAL": (0.25, "supply_down")},
    "political_bandh":         {"LOW": (0.02, "demand_down"), "MEDIUM": (0.06, "demand_down"), "HIGH": (0.10, "both"),        "CRITICAL": (0.15, "both")},
    "political_election":      {"LOW": (0.01, "demand_up"),   "MEDIUM": (0.03, "demand_up"),   "HIGH": (0.05, "demand_up"),   "CRITICAL": (0.07, "demand_up")},
    "political_protest":       {"LOW": (0.01, "demand_down"), "MEDIUM": (0.03, "demand_down"), "HIGH": (0.06, "both"),        "CRITICAL": (0.10, "both")},
    "political_civil_unrest":  {"LOW": (0.02, "both"),        "MEDIUM": (0.05, "both"),        "HIGH": (0.10, "supply_down"), "CRITICAL": (0.18, "supply_down")},
    "weather_heatwave":        {"LOW": (0.03, "demand_up"),   "MEDIUM": (0.07, "demand_up"),   "HIGH": (0.12, "demand_up"),   "CRITICAL": (0.20, "demand_up")},
    "weather_coldwave":        {"LOW": (0.02, "demand_up"),   "MEDIUM": (0.04, "demand_up"),   "HIGH": (0.08, "demand_up"),   "CRITICAL": (0.12, "demand_up")},
    "weather_cyclone":         {"LOW": (0.03, "supply_down"), "MEDIUM": (0.08, "supply_down"), "HIGH": (0.15, "supply_down"), "CRITICAL": (0.25, "supply_down")},
    "weather_flood":           {"LOW": (0.02, "supply_down"), "MEDIUM": (0.06, "supply_down"), "HIGH": (0.12, "supply_down"), "CRITICAL": (0.20, "supply_down")},
    "weather_drought":         {"LOW": (0.02, "supply_down"), "MEDIUM": (0.05, "supply_down"), "HIGH": (0.10, "supply_down"), "CRITICAL": (0.15, "supply_down")},
    "military_conflict":       {"LOW": (0.03, "both"),        "MEDIUM": (0.08, "supply_down"), "HIGH": (0.15, "both"),        "CRITICAL": (0.30, "both")},
    "military_india_border":   {"LOW": (0.02, "demand_up"),   "MEDIUM": (0.05, "both"),        "HIGH": (0.10, "both"),        "CRITICAL": (0.20, "both")},
    "military_sanctions":      {"LOW": (0.03, "supply_down"), "MEDIUM": (0.06, "supply_down"), "HIGH": (0.12, "supply_down"), "CRITICAL": (0.20, "supply_down")},
    "geopolitical_middle_east":{"LOW": (0.02, "supply_down"), "MEDIUM": (0.05, "supply_down"), "HIGH": (0.10, "supply_down"), "CRITICAL": (0.18, "supply_down")},
    "geopolitical_russia_ukraine":{"LOW":(0.02,"supply_down"),"MEDIUM": (0.05, "supply_down"), "HIGH": (0.10, "supply_down"), "CRITICAL": (0.18, "supply_down")},
    "geopolitical_global_supply":{"LOW":(0.01,"supply_down"), "MEDIUM": (0.03, "supply_down"), "HIGH": (0.07, "supply_down"), "CRITICAL": (0.12, "supply_down")},
    "default":                 {"LOW": (0.01, "both"),        "MEDIUM": (0.02, "both"),        "HIGH": (0.04, "both"),        "CRITICAL": (0.08, "both")},
}

# Severity escalation based on keyword intensity
ESCALATION_KEYWORDS = {
    "CRITICAL": ["collapse", "catastrophic", "emergency", "crisis", "chaos",
                 "massive outage", "total failure", "war", "airstrike", "missile"],
    "HIGH":     ["severe", "major", "significant", "critical", "acute",
                 "shortage", "strike", "cyclone", "heatwave"],
    "MEDIUM":   ["moderate", "concern", "disruption", "warning", "hike",
                 "protest", "alert", "tension"],
}

# Duration heuristics by subcategory
DURATION_HOURS: Dict[str, float] = {
    "power_outage": 12.0, "coal_supply": 72.0, "fuel_supply": 48.0,
    "transmission": 24.0, "strike": 48.0, "bandh": 24.0,
    "heatwave": 120.0, "coldwave": 96.0, "cyclone": 72.0, "flood": 168.0,
    "election": 16.0, "protest": 8.0, "civil_unrest": 48.0,
    "tariff_regulation": 720.0, "market_price": 24.0,
    "coal_price": 168.0, "fuel_price": 72.0,
    "middle_east": 168.0, "russia_ukraine": 720.0,
    "conflict": 720.0, "india_border": 336.0,
    "default": 24.0,
}


# ---------------------------------------------------------------------------
# CLASSIFIER
# ---------------------------------------------------------------------------

class EventClassifier:
    """Classifies RawArticles into EnrichedEvents without any LLM."""

    GRID_FILTER_KEYWORDS = [
        # Energy (always relevant)
        "power", "electricity", "grid", "energy", "coal", "gas", "fuel",
        "mw", "gw", "megawatt", "gigawatt", "thermal", "solar", "wind",
        "hydro", "renewable", "plant", "substation", "discom",
        # Economic (always relevant)
        "tariff", "price", "cost", "inflation", "rupee", "rbi", "subsidy",
        "reform", "auction", "iex", "spot", "crude", "lng", "opec",
        # Events that drive demand
        "heatwave", "heat wave", "cold wave", "cyclone", "flood",
        "election", "bandh", "strike", "protest",
        # Geopolitical / supply risk
        "war", "conflict", "border", "sanction", "embargo", "india pakistan",
        "india china", "russia", "iran", "middle east", "opec",
        "india", "bharat",  # catch all India news (filter will narrow later)
    ]

    def __init__(self):
        pass

    def classify(self, article: RawArticle) -> Optional[EnrichedEvent]:
        """Classify a single article. Returns None if not grid-relevant."""
        text = f"{article.title} {article.description}".lower()

        # Quick relevance gate
        if not any(kw in text for kw in self.GRID_FILTER_KEYWORDS):
            return None

        # Find best category + subcategory
        category, subcategory, matched_kws = self._find_category(text)
        if not category:
            return None

        # Severity
        severity = self._assess_severity(text, category, subcategory)

        # Geography
        states = self._extract_states(text)
        regions = self._extract_regions(states)
        is_national = self._is_national(text, states)

        # If truly nothing geographic and not national, skip
        if not states and not is_national:
            # Still include for geopolitical / global supply chain
            if category not in ("geopolitical", "military", "economic"):
                return None

        # MW estimate
        delta_mw, direction = self._estimate_impact(
            category, subcategory, severity, states, is_national
        )

        # Check for explicit MW in text
        explicit_mw = self._extract_explicit_mw(text)
        if explicit_mw > 0:
            delta_mw = max(delta_mw, explicit_mw)

        # ETA
        eta = self._estimate_eta(article, subcategory)

        # Duration
        dur = DURATION_HOURS.get(subcategory, DURATION_HOURS["default"])

        # Confidence
        try:
            from ..scrapers.multi_source import MultiSourceScraper as _MS
        except ImportError:  # pragma: no cover - fallback for direct script mode
            from scrapers.multi_source import MultiSourceScraper as _MS
        trust = _MS.trust_score(article.source_name)

        event_id = hashlib.md5(
            f"{article.title[:60]}|{article.published}".encode()
        ).hexdigest()[:12]

        return EnrichedEvent(
            event_id=event_id,
            title=article.title,
            summary=article.description[:400],
            url=article.url,
            published=article.published,
            source=article.source_name,
            feed_type=article.feed_type,
            category=category,
            subcategory=subcategory,
            severity=severity,
            confidence=round(trust, 3),
            affected_states=states,
            affected_regions=regions,
            is_national=is_national,
            estimated_delta_mw=round(delta_mw, 1),
            impact_direction=direction,
            eta_hours=eta,
            duration_hours=dur,
            keywords_matched=matched_kws[:8],
            raw_text=f"{article.title} | {article.description}"[:600],
        )

    def classify_batch(self, articles: List[RawArticle]) -> List[EnrichedEvent]:
        events = []
        for art in articles:
            ev = self.classify(art)
            if ev is not None:
                events.append(ev)
        # Sort by impact (high → low)
        events.sort(key=lambda e: e.estimated_delta_mw, reverse=True)
        return events

    # ------------------------------------------------------------------
    # INTERNALS
    # ------------------------------------------------------------------

    def _find_category(self, text: str) -> Tuple[str, str, List[str]]:
        best_cat, best_sub, best_kws = "", "", []
        best_score = 0
        for cat, subs in CATEGORY_KEYWORDS.items():
            for sub, keywords in subs.items():
                hits = [kw for kw in keywords if kw in text]
                if len(hits) > best_score:
                    best_score = len(hits)
                    best_cat = cat
                    best_sub = sub
                    best_kws = hits
        return (best_cat, best_sub, best_kws) if best_score > 0 else ("", "", [])

    def _assess_severity(self, text: str, category: str, subcategory: str) -> str:
        for sev in ("CRITICAL", "HIGH", "MEDIUM"):
            if any(kw in text for kw in ESCALATION_KEYWORDS.get(sev, [])):
                return sev

        # Number-based heuristics
        degrees = re.findall(r"(\d+)\s*degree|(\d+)\s*°c", text)
        if degrees:
            temps = [int(d[0] or d[1]) for d in degrees if d[0] or d[1]]
            if temps:
                max_t = max(temps)
                if max_t >= 47: return "CRITICAL"
                if max_t >= 44: return "HIGH"
                if max_t >= 40: return "MEDIUM"

        # MW magnitude
        mw = self._extract_explicit_mw(text)
        if mw >= 2000: return "HIGH"
        if mw >= 500: return "MEDIUM"

        return "LOW"

    def _extract_states(self, text: str) -> List[str]:
        found: Set[str] = set()
        for alias, code in STATE_MAP.items():
            # word-boundary match
            if re.search(r"\b" + re.escape(alias) + r"\b", text):
                found.add(code)
        return sorted(found)

    def _extract_regions(self, states: List[str]) -> List[str]:
        regions = set()
        for region, codes in REGION_MAP.items():
            if any(s in codes for s in states):
                regions.add(region)
        return sorted(regions)

    def _is_national(self, text: str, states: List[str]) -> bool:
        if len(states) >= 5:
            return True
        return any(t in text for t in NATIONAL_TRIGGERS)

    def _estimate_impact(
        self, cat: str, sub: str, severity: str,
        states: List[str], is_national: bool
    ) -> Tuple[float, str]:
        key = f"{cat}_{sub}"
        table = IMPACT_TABLE.get(key, IMPACT_TABLE["default"])
        pct, direction = table.get(severity, table.get("LOW", (0.01, "both")))

        if is_national or not states:
            # National: sum top 5 states
            top_states = sorted(STATE_PEAK_MW.values(), reverse=True)[:5]
            base_mw = sum(top_states)
        else:
            base_mw = sum(STATE_PEAK_MW.get(s, 5000) for s in states)

        return base_mw * pct, direction

    def _extract_explicit_mw(self, text: str) -> float:
        mw_pattern = r"(\d[\d,]*(?:\.\d+)?)\s*(?:mw|megawatt)"
        gw_pattern = r"(\d[\d,]*(?:\.\d+)?)\s*(?:gw|gigawatt)"
        total = 0.0
        for m in re.findall(mw_pattern, text):
            total += float(m.replace(",", ""))
        for m in re.findall(gw_pattern, text):
            total += float(m.replace(",", "")) * 1000
        return total

    def _estimate_eta(self, article: RawArticle, subcategory: str) -> float:
        """Articles that are scheduled events have future ETA, else 0."""
        scheduled_subs = {"election", "strike", "bandh", "tariff_regulation"}
        if subcategory in scheduled_subs:
            # Try to parse future date from title/description
            future_patterns = [
                r"on\s+(\w+\s+\d{1,2})", r"from\s+(\w+\s+\d{1,2})",
                r"tomorrow", r"next week",
            ]
            text = article.title.lower()
            if "tomorrow" in text:
                return 18.0
            if "next week" in text:
                return 120.0
        return 0.0
