"""Static setup/config for intelligence agent regions."""

from __future__ import annotations

from typing import Dict, Any


CITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    "UP": {
        "name": "Uttar Pradesh",
        "lat": 26.8467,
        "lon": 80.9462,
        "aliases": ["uttar pradesh", "up", "lucknow", "kanpur", "noida", "agra"],
        "primary_fuel_sources": ["Coal", "Hydro imports", "Gas peakers"],
        "fuel_supply_routes": [
            "Coal rail corridors from Jharkhand/Chhattisgarh to UP thermal plants",
            "Interstate transmission imports via UP-WB and UP-BHR corridors",
        ],
        "neighboring_exchange": ["BHR", "WB", "KAR"],
        "seasonal_demand_factors": ["Summer AC surge", "Irrigation pump loads", "Festival evening peaks"],
        "key_vulnerabilities": ["Coal logistics disruption", "Transmission congestion", "Election shutdown swings"],
    },
    "BHR": {
        "name": "Bihar",
        "lat": 25.5941,
        "lon": 85.1376,
        "aliases": ["bihar", "bhr", "bh", "patna", "gaya", "muzaffarpur"],
        "primary_fuel_sources": ["Coal-dominant thermal", "Interstate imports"],
        "fuel_supply_routes": [
            "Coal rail links from Jharkhand coal belts",
            "Power imports via BHR-UP and BHR-WB transmission corridors",
        ],
        "neighboring_exchange": ["UP", "WB", "KAR"],
        "seasonal_demand_factors": ["Agricultural pumps", "Summer residential cooling"],
        "key_vulnerabilities": ["Coal stock depletion", "Eastern grid disturbances", "Rail movement bottlenecks"],
    },
    "WB": {
        "name": "West Bengal",
        "lat": 22.5726,
        "lon": 88.3639,
        "aliases": ["west bengal", "wb", "kolkata", "howrah", "durgapur", "asansol"],
        "primary_fuel_sources": ["Coal thermal", "Port-linked fuel imports", "Hydro exchanges"],
        "fuel_supply_routes": [
            "Coal flow from eastern coalfields and rail-fed thermal stations",
            "Grid transfers through WB-BHR and WB-UP corridors",
        ],
        "neighboring_exchange": ["UP", "BHR", "KAR"],
        "seasonal_demand_factors": ["Urban evening peaks", "Industrial corridor loads", "Festival lighting demand"],
        "key_vulnerabilities": ["Cyclone transmission damage", "Port/logistics disruptions", "Industrial strike events"],
    },
    "KAR": {
        "name": "Karnataka",
        "lat": 12.9716,
        "lon": 77.5946,
        "aliases": ["karnataka", "kar", "bangalore", "bengaluru", "mysuru", "hubli"],
        "primary_fuel_sources": ["Hydro + thermal mix", "Renewables", "Interstate imports"],
        "fuel_supply_routes": [
            "Coal and fuel movement from eastern/western supply chains to thermal units",
            "Interstate transfer corridors via KAR-UP, KAR-WB, KAR-BHR links",
        ],
        "neighboring_exchange": ["UP", "BHR", "WB"],
        "seasonal_demand_factors": ["IT corridor cooling loads", "Evening commercial demand", "Monsoon hydro variance"],
        "key_vulnerabilities": ["Heatwave AC spikes", "Fuel price sensitivity", "Interstate corridor derating"],
    },
}

