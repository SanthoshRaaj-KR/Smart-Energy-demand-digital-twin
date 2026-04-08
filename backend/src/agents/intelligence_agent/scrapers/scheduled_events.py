"""
scheduled_events.py
==================
High-impact scheduled event database for grid intelligence.

Tracks known events that significantly impact power demand:
- Cricket matches (IPL, International)
- Elections (National, State, Local)
- Festivals (Diwali, Holi, Eid, etc.)
- Public holidays
- Major sporting events
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Optional


@dataclass
class ScheduledEvent:
    """A known high-impact event with predicted load characteristics."""
    event_id: str
    event_name: str
    event_type: str  # "cricket", "election", "festival", "holiday", "sports"
    date: str  # ISO format YYYY-MM-DD
    time_start: Optional[str]  # HH:MM format (optional)
    time_end: Optional[str]
    affected_states: List[str]  # State codes: UP, BHR, WB, KAR, etc.
    is_national: bool
    flags: List[str]  # Semantic load descriptors
    estimated_demand_delta_mw: float  # Positive = increased demand
    confidence: float  # 0.0-1.0
    description: str


# ============================================================================
# IPL 2026 SCHEDULE (April matches)
# ============================================================================

IPL_2026_APRIL = [
    ScheduledEvent(
        event_id="ipl_2026_match_01",
        event_name="IPL 2026: Chennai Super Kings vs Mumbai Indians (Eden Gardens, Kolkata)",
        event_type="cricket",
        date="2026-04-05",
        time_start="19:30",
        time_end="23:00",
        affected_states=["WB", "BHR", "OR", "JH", "AS"],  # Eastern states
        is_national=True,  # Entire nation watches IPL
        flags=[
            "stadium_lighting",
            "residential_tv_surge",
            "commercial_restaurant_surge",
            "evening_peak_amplification",
            "air_conditioning_surge"
        ],
        estimated_demand_delta_mw=800.0,  # Stadium + TV viewership
        confidence=0.95,
        description="IPL evening match at Eden Gardens. Expect 800 MW surge in WB + neighboring states from stadium lighting (50 MW) + residential TV viewership (500 MW) + commercial establishments (250 MW)."
    ),
    ScheduledEvent(
        event_id="ipl_2026_match_02",
        event_name="IPL 2026: Royal Challengers Bangalore vs Delhi Capitals (Chinnaswamy Stadium, Bangalore)",
        event_type="cricket",
        date="2026-04-08",
        time_start="19:30",
        time_end="23:00",
        affected_states=["KAR", "TN", "AP", "TS"],  # Southern states
        is_national=True,
        flags=[
            "stadium_lighting",
            "residential_tv_surge",
            "commercial_restaurant_surge",
            "evening_peak_amplification"
        ],
        estimated_demand_delta_mw=900.0,  # Bangalore's high AC usage
        confidence=0.95,
        description="IPL match in Bangalore. Higher AC load due to tropical climate. 900 MW surge expected."
    ),
    ScheduledEvent(
        event_id="ipl_2026_match_03",
        event_name="IPL 2026: Kolkata Knight Riders vs Rajasthan Royals (Eden Gardens, Kolkata)",
        event_type="cricket",
        date="2026-04-12",
        time_start="15:30",
        time_end="19:00",
        affected_states=["WB", "BHR", "OR"],
        is_national=True,
        flags=[
            "stadium_lighting",
            "residential_tv_surge",
            "afternoon_demand_spike",
            "air_conditioning_surge"
        ],
        estimated_demand_delta_mw=700.0,
        confidence=0.90,
        description="Afternoon IPL match. Lower delta due to daytime (no stadium lighting surge). AC load increases."
    ),
    ScheduledEvent(
        event_id="ipl_2026_match_04",
        event_name="IPL 2026: Lucknow Super Giants vs Punjab Kings (Ekana Stadium, Lucknow)",
        event_type="cricket",
        date="2026-04-15",
        time_start="19:30",
        time_end="23:00",
        affected_states=["UP", "MP", "UK", "HP", "PB"],  # North India
        is_national=True,
        flags=[
            "stadium_lighting",
            "residential_tv_surge",
            "commercial_restaurant_surge",
            "evening_peak_amplification"
        ],
        estimated_demand_delta_mw=850.0,
        confidence=0.95,
        description="IPL match in Lucknow, UP. High viewership in northern states. 850 MW surge."
    ),
    ScheduledEvent(
        event_id="ipl_2026_match_05",
        event_name="IPL 2026: Mumbai Indians vs Gujarat Titans (Wankhede Stadium, Mumbai)",
        event_type="cricket",
        date="2026-04-20",
        time_start="19:30",
        time_end="23:00",
        affected_states=["MH", "GJ", "MP", "GA"],  # Western states
        is_national=True,
        flags=[
            "stadium_lighting",
            "residential_tv_surge",
            "commercial_restaurant_surge",
            "evening_peak_amplification"
        ],
        estimated_demand_delta_mw=1000.0,  # Mumbai's high density
        confidence=0.95,
        description="IPL match in Mumbai. Highest urban density. 1000 MW surge expected from residential + commercial load."
    ),
    ScheduledEvent(
        event_id="ipl_2026_match_06",
        event_name="IPL 2026: Sunrisers Hyderabad vs Chennai Super Kings (Uppal Stadium, Hyderabad)",
        event_type="cricket",
        date="2026-04-25",
        time_start="19:30",
        time_end="23:00",
        affected_states=["TS", "AP", "KAR", "TN"],
        is_national=True,
        flags=[
            "stadium_lighting",
            "residential_tv_surge",
            "commercial_restaurant_surge",
            "evening_peak_amplification"
        ],
        estimated_demand_delta_mw=800.0,
        confidence=0.95,
        description="IPL match in Hyderabad. 800 MW surge in Telangana and neighboring states."
    ),
]


# ============================================================================
# ELECTION 2026 (April dates)
# ============================================================================

ELECTIONS_2026_APRIL = [
    ScheduledEvent(
        event_id="election_2026_up_phase1",
        event_name="Uttar Pradesh Assembly Election - Phase 1 Polling",
        event_type="election",
        date="2026-04-10",
        time_start="07:00",
        time_end="18:00",
        affected_states=["UP"],
        is_national=False,
        flags=[
            "industrial_shutdown",
            "commercial_closure",
            "public_transport_reduced",
            "daytime_demand_reduction"
        ],
        estimated_demand_delta_mw=-1200.0,  # NEGATIVE = reduced demand
        confidence=0.95,
        description="UP Assembly elections Phase 1. Model Code of Conduct enforces factory closures, reduced industrial activity. Expect 1200 MW demand drop during polling hours."
    ),
    ScheduledEvent(
        event_id="election_2026_up_phase2",
        event_name="Uttar Pradesh Assembly Election - Phase 2 Polling",
        event_type="election",
        date="2026-04-17",
        time_start="07:00",
        time_end="18:00",
        affected_states=["UP"],
        is_national=False,
        flags=[
            "industrial_shutdown",
            "commercial_closure",
            "public_transport_reduced",
            "daytime_demand_reduction"
        ],
        estimated_demand_delta_mw=-1200.0,
        confidence=0.95,
        description="UP Assembly elections Phase 2. Similar demand reduction as Phase 1."
    ),
    ScheduledEvent(
        event_id="election_2026_wb_polling",
        event_name="West Bengal Municipal Elections - Polling Day",
        event_type="election",
        date="2026-04-22",
        time_start="07:00",
        time_end="17:00",
        affected_states=["WB"],
        is_national=False,
        flags=[
            "industrial_shutdown",
            "commercial_closure",
            "public_transport_reduced",
            "daytime_demand_reduction"
        ],
        estimated_demand_delta_mw=-800.0,
        confidence=0.90,
        description="WB Municipal elections. Local impact. 800 MW demand drop in industrial belts."
    ),
    ScheduledEvent(
        event_id="election_2026_kar_local",
        event_name="Karnataka Gram Panchayat Elections",
        event_type="election",
        date="2026-04-28",
        time_start="07:00",
        time_end="17:00",
        affected_states=["KAR"],
        is_national=False,
        flags=[
            "rural_industrial_shutdown",
            "commercial_closure",
            "daytime_demand_reduction"
        ],
        estimated_demand_delta_mw=-500.0,
        confidence=0.85,
        description="Karnataka local body elections. Rural focus. 500 MW demand reduction."
    ),
]


# ============================================================================
# FESTIVALS & HOLIDAYS (April 2026)
# ============================================================================

FESTIVALS_2026_APRIL = [
    ScheduledEvent(
        event_id="festival_2026_eid",
        event_name="Eid al-Fitr (Ramadan End)",
        event_type="festival",
        date="2026-04-02",
        time_start="06:00",
        time_end="23:59",
        affected_states=["UP", "BHR", "WB", "KAR", "TN", "KL", "TS", "MH"],  # High Muslim population
        is_national=True,
        flags=[
            "commercial_restaurant_surge",
            "residential_cooking_surge",
            "decorative_lighting",
            "shopping_mall_surge",
            "evening_peak_amplification"
        ],
        estimated_demand_delta_mw=600.0,
        confidence=0.90,
        description="Eid celebrations. Increased commercial activity, decorative lighting, extended shopping hours. 600 MW surge in Muslim-majority areas."
    ),
    ScheduledEvent(
        event_id="festival_2026_mahavir_jayanti",
        event_name="Mahavir Jayanti (Jain Festival)",
        event_type="festival",
        date="2026-04-06",
        time_start="06:00",
        time_end="23:59",
        affected_states=["GJ", "RJ", "MH", "MP", "KAR"],
        is_national=False,
        flags=[
            "temple_lighting",
            "residential_surge",
            "commercial_closure"
        ],
        estimated_demand_delta_mw=200.0,
        confidence=0.75,
        description="Mahavir Jayanti. Moderate impact. Temple lighting + residential activities. 200 MW increase."
    ),
    ScheduledEvent(
        event_id="festival_2026_ambedkar_jayanti",
        event_name="Dr. Ambedkar Jayanti (Public Holiday)",
        event_type="holiday",
        date="2026-04-14",
        time_start="00:00",
        time_end="23:59",
        affected_states=["ALL"],  # National holiday
        is_national=True,
        flags=[
            "industrial_shutdown",
            "commercial_partial_closure",
            "residential_surge",
            "daytime_demand_reduction"
        ],
        estimated_demand_delta_mw=-400.0,
        confidence=0.90,
        description="Ambedkar Jayanti public holiday. Industrial closures reduce demand by 400 MW. Residential load slightly increases."
    ),
    ScheduledEvent(
        event_id="festival_2026_tamil_new_year",
        event_name="Tamil New Year (Puthandu)",
        event_type="festival",
        date="2026-04-14",
        time_start="06:00",
        time_end="23:59",
        affected_states=["TN", "PY", "KAR"],
        is_national=False,
        flags=[
            "residential_cooking_surge",
            "temple_lighting",
            "commercial_restaurant_surge"
        ],
        estimated_demand_delta_mw=300.0,
        confidence=0.85,
        description="Tamil New Year in South India. Residential cooking + temple activities. 300 MW surge in TN/KAR."
    ),
]


# ============================================================================
# AGGREGATED CALENDAR
# ============================================================================

ALL_SCHEDULED_EVENTS_APRIL_2026 = (
    IPL_2026_APRIL + 
    ELECTIONS_2026_APRIL + 
    FESTIVALS_2026_APRIL
)


# ============================================================================
# QUERY FUNCTIONS
# ============================================================================

def fetch_scheduled_events(date_obj: date | str) -> List[ScheduledEvent]:
    """
    Fetch all scheduled high-impact events for a given date.
    
    Args:
        date_obj: Either a datetime.date object or ISO string "YYYY-MM-DD"
    
    Returns:
        List of ScheduledEvent objects for that date
    """
    if isinstance(date_obj, str):
        date_str = date_obj
    else:
        date_str = date_obj.strftime("%Y-%m-%d")
    
    events = [
        event for event in ALL_SCHEDULED_EVENTS_APRIL_2026
        if event.date == date_str
    ]
    
    return events


def fetch_events_for_state(state_id: str, date_obj: date | str) -> List[ScheduledEvent]:
    """
    Fetch scheduled events affecting a specific state on a given date.
    
    Args:
        state_id: State code (e.g., "UP", "WB", "KAR", "BHR")
        date_obj: Date to query
    
    Returns:
        List of events affecting that state
    """
    all_events = fetch_scheduled_events(date_obj)
    
    state_events = [
        event for event in all_events
        if state_id in event.affected_states or event.is_national
    ]
    
    return state_events


def get_date_summary(date_obj: date | str) -> Dict[str, any]:
    """
    Get a summary of all events on a date.
    
    Returns:
        {
            "date": "2026-04-10",
            "event_count": 2,
            "total_demand_delta_mw": 600.0,
            "events": [...]
        }
    """
    events = fetch_scheduled_events(date_obj)
    
    if isinstance(date_obj, str):
        date_str = date_obj
    else:
        date_str = date_obj.strftime("%Y-%m-%d")
    
    total_delta = sum(event.estimated_demand_delta_mw for event in events)
    
    return {
        "date": date_str,
        "event_count": len(events),
        "total_demand_delta_mw": total_delta,
        "events": [
            {
                "event_name": e.event_name,
                "event_type": e.event_type,
                "delta_mw": e.estimated_demand_delta_mw,
                "flags": e.flags,
                "affected_states": e.affected_states,
            }
            for e in events
        ],
    }


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================

def get_all_events_json() -> str:
    """Export all scheduled events as JSON for caching."""
    import json
    events_dict = [
        {
            "event_id": e.event_id,
            "event_name": e.event_name,
            "event_type": e.event_type,
            "date": e.date,
            "time_start": e.time_start,
            "time_end": e.time_end,
            "affected_states": e.affected_states,
            "is_national": e.is_national,
            "flags": e.flags,
            "estimated_demand_delta_mw": e.estimated_demand_delta_mw,
            "confidence": e.confidence,
            "description": e.description,
        }
        for e in ALL_SCHEDULED_EVENTS_APRIL_2026
    ]
    return json.dumps(events_dict, indent=2)


if __name__ == "__main__":
    # Demo usage
    print("=== Scheduled Events for April 2026 ===\n")
    
    # Test specific dates
    test_dates = ["2026-04-05", "2026-04-10", "2026-04-14", "2026-04-20"]
    
    for date_str in test_dates:
        summary = get_date_summary(date_str)
        print(f"📅 {date_str}: {summary['event_count']} events, Total Delta: {summary['total_demand_delta_mw']:+.0f} MW")
        for evt in summary['events']:
            print(f"   • {evt['event_name']}: {evt['delta_mw']:+.0f} MW")
        print()
    
    # Test state-specific queries
    print("\n=== Events for Uttar Pradesh (UP) ===")
    up_events = fetch_events_for_state("UP", "2026-04-10")
    for evt in up_events:
        print(f"• {evt.event_name}: {evt.estimated_demand_delta_mw:+.0f} MW")
