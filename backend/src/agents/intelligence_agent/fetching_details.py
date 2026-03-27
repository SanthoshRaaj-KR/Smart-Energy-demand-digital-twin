"""External data acquisition layer (weather, news, rss)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from .setup import NEWS_ARTICLE_LIMIT, RSS_FEEDS, RSS_ITEM_LIMIT

WEATHER_CODE_LABELS = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast clouds",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy intensity rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "light snowfall",
    73: "snowfall",
    75: "heavy snowfall",
    77: "snow grains",
    80: "rain showers",
    81: "rain showers",
    82: "violent rain showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm",
}

class DataFetcher:
    """
    Thin, stateless data layer.
    All methods return raw dicts/lists; no business logic here.
    """

    def __init__(self, gnews_key: str, newsdata_key: str, owm_key: str, log_fn=None):
        self._gnews_key    = gnews_key
        self._newsdata_key = newsdata_key
        self._owm_key      = owm_key
        self._log          = log_fn or (lambda tag, data: None)
        self._session      = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0 (GridBot/3.0)"})

    #  Weather 
    def fetch_owm_forecast(self, city: str, lat: float, lon: float) -> Dict[str, Any]:
        url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={lat}&lon={lon}&units=metric&appid={self._owm_key}"
        )
        try:
            r = self._session.get(url, timeout=10)
            r.raise_for_status()
            raw = r.json()

            daily: Dict[str, Dict] = {}
            for item in raw["list"]:
                day = item["dt_txt"][:10]
                if day not in daily:
                    daily[day] = {"temps": [], "humidity": [], "conditions": [], "rain_mm": 0.0}
                daily[day]["temps"].append(item["main"]["temp"])
                daily[day]["humidity"].append(item["main"]["humidity"])
                daily[day]["conditions"].append(item["weather"][0]["description"])
                daily[day]["rain_mm"] += item.get("rain", {}).get("3h", 0.0)

            forecast_days = []
            for day, v in sorted(daily.items())[:5]:
                max_t  = max(v["temps"])
                avg_h  = round(sum(v["humidity"]) / len(v["humidity"]))
                # Steadman heat-index approximation
                heat_index = round(
                    max_t + 0.33 * (avg_h / 100 * 6.105 * (17.27 * max_t / (237.3 + max_t))) - 4.0,
                    1,
                )
                forecast_days.append({
                    "date"              : day,
                    "max_c"             : round(max_t, 1),
                    "min_c"             : round(min(v["temps"]), 1),
                    "avg_humidity_pct"  : avg_h,
                    "heat_index_c"      : heat_index,
                    "dominant_condition": max(set(v["conditions"]), key=v["conditions"].count),
                    "total_rain_mm"     : round(v["rain_mm"], 1),
                })

            result = {
                "current_temp_c"       : round(raw["list"][0]["main"]["temp"], 1),
                "current_humidity_pct" : raw["list"][0]["main"]["humidity"],
                "current_condition"    : raw["list"][0]["weather"][0]["description"],
                "5_day_forecast"       : forecast_days,
                "week_max_c"           : max(d["max_c"] for d in forecast_days),
                "week_max_heat_index_c": max(d["heat_index_c"] for d in forecast_days),
                "week_total_rain_mm"   : round(sum(d["total_rain_mm"] for d in forecast_days), 1),
            }
            self._log(f"OWM_Forecast_{city}", json.dumps(result, indent=2))
            return result

        except Exception as exc:
            return {"error": str(exc)}

    def fetch_hourly_forecast_7d(self, city: str, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetch 7-day hourly weather forecast from Open-Meteo (no API key required).
        Returns data normalized for downstream routing and demand fusion.
        """
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,"
            "precipitation,windspeed_10m,weathercode"
            "&forecast_days=7"
            "&timezone=auto"
        )
        try:
            r = self._session.get(url, timeout=12)
            r.raise_for_status()
            raw = r.json()
            hourly = raw.get("hourly", {})

            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            humidity = hourly.get("relative_humidity_2m", [])
            apparent = hourly.get("apparent_temperature", [])
            precip = hourly.get("precipitation", [])
            wind = hourly.get("windspeed_10m", [])
            weathercode = hourly.get("weathercode", [])

            records: List[Dict[str, Any]] = []
            for idx in range(min(len(times), len(temps))):
                records.append(
                    {
                        "time": times[idx],
                        "temperature_c": round(float(temps[idx]), 1),
                        "apparent_temperature_c": round(float(apparent[idx]), 1) if idx < len(apparent) else None,
                        "humidity_pct": int(humidity[idx]) if idx < len(humidity) else None,
                        "precip_mm": round(float(precip[idx]), 2) if idx < len(precip) else 0.0,
                        "wind_kmh": round(float(wind[idx]), 1) if idx < len(wind) else None,
                        "weather_code": int(weathercode[idx]) if idx < len(weathercode) else None,
                        "condition": WEATHER_CODE_LABELS.get(int(weathercode[idx]), "unknown")
                        if idx < len(weathercode)
                        else "unknown",
                    }
                )

            result = {
                "source": "open-meteo",
                "city": city,
                "hourly_forecast_7d": records,
            }
            self._log(f"OpenMeteo_7D_Hourly_{city}", json.dumps(result, indent=2))
            return result
        except Exception as exc:
            return {"error": str(exc), "hourly_forecast_7d": []}

    #  GNews 
    def fetch_gnews(self, query: str, label: str) -> List[Dict]:
        url = (
            f"https://gnews.io/api/v4/search"
            f"?q={requests.utils.quote(query)}"
            f"&lang=en&country=in&max={NEWS_ARTICLE_LIMIT}&sortby=publishedAt"
            f"&apikey={self._gnews_key}"
        )
        try:
            r = self._session.get(url, timeout=10)
            r.raise_for_status()
            articles = r.json().get("articles", [])
            self._log(f"GNews_{label}", json.dumps(articles, indent=2))
            return articles
        except Exception as exc:
            print(f"    [!] GNews({label}): {exc}")
            return []

    #  NewsData.io 
    def fetch_newsdata(self, query: str, label: str) -> List[Dict]:
        url = (
            f"https://newsdata.io/api/1/news"
            f"?apikey={self._newsdata_key}"
            f"&q={requests.utils.quote(query)}"
            f"&country=in&language=en&size={NEWS_ARTICLE_LIMIT}"
        )
        try:
            r = self._session.get(url, timeout=10)
            r.raise_for_status()
            articles = [
                {
                    "title"      : a.get("title"),
                    "description": a.get("description"),
                    "source"     : a.get("source_id"),
                }
                for a in r.json().get("results", [])
            ]
            self._log(f"NewsData_{label}", json.dumps(articles, indent=2))
            return articles
        except Exception as exc:
            print(f"    [!] NewsData({label}): {exc}")
            return []

    #  RSS 
    def scrape_rss_feeds(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        for name, url in RSS_FEEDS.items():
            try:
                r = self._session.get(url, timeout=7)
                if r.status_code == 200:
                    soup  = BeautifulSoup(r.content, "xml")
                    items = soup.find_all("item", limit=RSS_ITEM_LIMIT)
                    lines = []
                    for item in items:
                        title = item.find("title")
                        desc  = item.find("description")
                        if title:
                            body = f"{title.text.strip()}"
                            if desc:
                                body += f" | {desc.text.strip()[:130]}"
                            lines.append(body)
                    result[name] = lines
                    print(f"    [RSS] {name}: {len(lines)} items")
            except Exception as exc:
                print(f"    [!] RSS({name}): {exc}")
                result[name] = []
        self._log("RSS_ALL_FEEDS", json.dumps(result, indent=2))
        return result
