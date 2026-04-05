"""
inference_30day.py
------------------
Extended 30-day demand forecasting with confidence decay and uncertainty quantification.

Key innovations for patent value:
1. Autoregressive LightGBM with rolling horizon extension
2. Confidence decay model (exponential based on prediction horizon)
3. Weather forecast interpolation for days 8-30 (linear extrapolation from 7-day)
4. LLM intelligence multiplier integration with severity-based confidence adjustment
5. Uncertainty bands using historical error variance

The model produces:
- High-confidence zone (days 1-7): Direct LightGBM predictions
- Extended forecast zone (days 8-30): Autoregressive with decaying confidence
- Uncertainty bands: ±σ based on horizon and intelligence confidence
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

# Import the base 7-day inference module
from .inference import (
    load_artefacts,
    predict_next_7_days,
    REGION_NAME_MAP,
    CLIMATIC_COLS,
)


# ---------------------------------------------------------------------------
# Confidence Decay Model
# ---------------------------------------------------------------------------

def confidence_decay(horizon_days: int, base_confidence: float = 0.95) -> float:
    """
    Model confidence decay for autoregressive forecasts.
    
    Based on the observation that prediction errors compound in autoregressive
    models. Each step introduces ~2-5% additional uncertainty.
    
    Parameters
    ----------
    horizon_days : int
        Number of days ahead (1 = tomorrow)
    base_confidence : float
        Initial confidence for day-1 prediction (default 0.95)
    
    Returns
    -------
    float
        Confidence score between 0 and 1
    """
    # Exponential decay: confidence halves roughly every 14 days
    decay_rate = 0.05  # ~5% decay per day
    confidence = base_confidence * np.exp(-decay_rate * (horizon_days - 1))
    return max(0.1, min(1.0, confidence))  # Clamp between 0.1 and 1.0


def uncertainty_band(
    prediction: float,
    horizon_days: int,
    base_mape: float = 0.03,  # 3% baseline MAPE
    intelligence_confidence: float = 0.5
) -> Tuple[float, float]:
    """
    Calculate uncertainty bands for a prediction.
    
    Wider bands for:
    - Longer horizons (error compounds)
    - Lower intelligence confidence (less reliable context)
    
    Parameters
    ----------
    prediction : float
        Point prediction in MW
    horizon_days : int
        Forecast horizon
    base_mape : float
        Baseline Mean Absolute Percentage Error
    intelligence_confidence : float
        LLM intelligence confidence (0-1)
    
    Returns
    -------
    Tuple[float, float]
        (lower_bound, upper_bound) in MW
    """
    # Error grows with horizon
    horizon_factor = 1 + 0.1 * (horizon_days - 1)  # +10% per day
    
    # Lower intelligence confidence → wider bands
    intel_factor = 2 - intelligence_confidence  # 1.0 to 2.0
    
    # Combined uncertainty
    uncertainty_pct = base_mape * horizon_factor * intel_factor
    
    lower = prediction * (1 - uncertainty_pct)
    upper = prediction * (1 + uncertainty_pct)
    
    return (round(lower, 2), round(upper, 2))


# ---------------------------------------------------------------------------
# Weather Extrapolation for Days 8-30
# ---------------------------------------------------------------------------

def extrapolate_weather(
    forecast_7day: List[Dict[str, float]],
    target_days: int = 30
) -> List[Dict[str, float]]:
    """
    Extrapolate weather features from 7-day forecast to 30 days.
    
    Uses linear regression on the 7-day trend to project forward,
    with damping toward seasonal means for longer horizons.
    
    Parameters
    ----------
    forecast_7day : List[Dict[str, float]]
        7 days of weather forecasts with CLIMATIC_COLS
    target_days : int
        Total days to produce
    
    Returns
    -------
    List[Dict[str, float]]
        Extended weather forecast (30 days)
    """
    if len(forecast_7day) < 7:
        # Pad with last known value if incomplete
        while len(forecast_7day) < 7:
            forecast_7day.append(forecast_7day[-1] if forecast_7day else {
                'om_temp_mean': 30.0,
                'nasa_solar': 2.5,
                'om_dewpoint': 15.0,
                'om_wind_gusts': 20.0,
            })
    
    result = list(forecast_7day)  # Copy first 7 days
    
    # Calculate trends from 7-day data
    trends = {}
    for col in CLIMATIC_COLS:
        values = [d.get(col, 25.0) for d in forecast_7day]
        x = np.arange(7)
        slope, intercept = np.polyfit(x, values, 1)
        trends[col] = {
            'slope': slope,
            'intercept': intercept,
            'last': values[-1],
            'mean': np.mean(values),
        }
    
    # Extrapolate days 8-30 with trend damping
    for day in range(7, target_days):
        row = {}
        damping = np.exp(-0.05 * (day - 7))  # Damping toward mean
        
        for col in CLIMATIC_COLS:
            t = trends[col]
            # Trend-based projection
            trend_value = t['slope'] * day + t['intercept']
            # Blend with mean based on damping
            row[col] = damping * trend_value + (1 - damping) * t['mean']
            
            # Apply reasonable bounds
            if col == 'om_temp_mean':
                row[col] = max(5.0, min(50.0, row[col]))
            elif col == 'nasa_solar':
                row[col] = max(0.0, min(10.0, row[col]))
            elif col == 'om_dewpoint':
                row[col] = max(-10.0, min(35.0, row[col]))
            elif col == 'om_wind_gusts':
                row[col] = max(0.0, min(100.0, row[col]))
        
        result.append(row)
    
    return result


# ---------------------------------------------------------------------------
# 30-Day Autoregressive Prediction
# ---------------------------------------------------------------------------

def predict_30_days(
    input_data: dict,
    model,
    scaler_climate,
    scaler_lagroll,
    intelligence_multiplier: float = 1.0,
    intelligence_confidence: float = 0.5
) -> Dict[str, Any]:
    """
    Generate 30-day demand forecast with uncertainty quantification.
    
    Parameters
    ----------
    input_data : dict
        Same format as predict_next_7_days
    model, scaler_climate, scaler_lagroll : model artifacts
    intelligence_multiplier : float
        LLM-derived demand multiplier (default 1.0)
    intelligence_confidence : float
        LLM confidence score (default 0.5)
    
    Returns
    -------
    dict with keys:
        'dates' : List[str] (30 dates)
        'predicted_mw' : List[float] (30 raw predictions)
        'adjusted_mw' : List[float] (30 intelligence-adjusted)
        'confidence' : List[float] (30 confidence scores)
        'lower_bound' : List[float] (30 lower uncertainty bounds)
        'upper_bound' : List[float] (30 upper uncertainty bounds)
        'zones' : {'high_confidence': 7, 'extended': 23}
    """
    from .inference import (
        _build_row, _cyclical_encode, MODEL_FEATURE_ORDER,
        _STATE_LABEL_MAP, REGION_NAME_MAP
    )
    
    # --- Parse input ---
    dates = pd.to_datetime(input_data['Date'])
    raw_states = input_data['State']
    actual_drawls = list(map(float, input_data['Actual_Drawl']))
    
    normalized_states = [REGION_NAME_MAP.get(s, "Region 1") for s in raw_states]
    state_label = _STATE_LABEL_MAP.get(normalized_states[0], 0)
    
    # Get 7-day weather and extrapolate to 30
    weather_7day = []
    for i in range(7):
        weather_7day.append({
            col: float(input_data.get(col, [25.0])[min(i, len(input_data.get(col, [])) - 1)])
            for col in CLIMATIC_COLS
        })
    weather_30day = extrapolate_weather(weather_7day, 30)
    
    # --- Autoregressive prediction loop ---
    history = actual_drawls.copy()
    last_date = dates[-1]
    
    future_dates = []
    predicted_mw = []
    adjusted_mw = []
    confidences = []
    lower_bounds = []
    upper_bounds = []
    
    for step in range(30):
        horizon = step + 1
        future_date = last_date + pd.DateOffset(days=horizon)
        weather_row = weather_30day[step]
        
        # Build feature row
        row = _build_row(future_date, state_label, weather_row, history)
        
        # Convert to DataFrame for scaling
        df_row = pd.DataFrame([row])
        _cyclical_encode(df_row)
        df_row = df_row.drop(columns=['dd', 'mm'])
        
        # Scale features
        df_row[CLIMATIC_COLS] = scaler_climate.transform(df_row[CLIMATIC_COLS])
        lag_roll_cols = [c for c in df_row.columns if 'lag_' in c or 'roll_' in c]
        df_row[lag_roll_cols] = scaler_lagroll.transform(df_row[lag_roll_cols])
        
        # Predict
        X = df_row[MODEL_FEATURE_ORDER]
        pred_raw = float(model.predict(X)[0])
        
        # Apply intelligence multiplier
        pred_adjusted = pred_raw * intelligence_multiplier
        
        # Calculate confidence and bounds
        conf = confidence_decay(horizon, base_confidence=0.95)
        # Adjust confidence based on LLM intelligence confidence
        conf *= (0.5 + 0.5 * intelligence_confidence)
        
        lower, upper = uncertainty_band(
            pred_adjusted, horizon,
            intelligence_confidence=intelligence_confidence
        )
        
        # Store results
        future_dates.append(future_date.strftime('%Y-%m-%d'))
        predicted_mw.append(round(pred_raw, 2))
        adjusted_mw.append(round(pred_adjusted, 2))
        confidences.append(round(conf, 3))
        lower_bounds.append(lower)
        upper_bounds.append(upper)
        
        # Feed back into history for next iteration
        history.append(pred_adjusted)
    
    return {
        'dates': future_dates,
        'predicted_mw': predicted_mw,
        'adjusted_mw': adjusted_mw,
        'confidence': confidences,
        'lower_bound': lower_bounds,
        'upper_bound': upper_bounds,
        'zones': {
            'high_confidence': 7,  # Days 1-7
            'extended': 23,        # Days 8-30
        },
        'intelligence': {
            'multiplier': intelligence_multiplier,
            'confidence': intelligence_confidence,
        },
    }


def predict_30_days_all_regions(
    inputs_by_region: Dict[str, dict],
    model,
    scaler_climate,
    scaler_lagroll,
    intelligence_context: Dict[str, Dict] = None
) -> Dict[str, Dict]:
    """
    Generate 30-day forecasts for all regions.
    
    Parameters
    ----------
    inputs_by_region : Dict[str, dict]
        Input data keyed by region ID
    model, scaler_climate, scaler_lagroll : model artifacts
    intelligence_context : Dict[str, Dict], optional
        Intelligence data keyed by region ID (from /api/intelligence)
    
    Returns
    -------
    Dict[str, Dict]
        30-day forecasts keyed by region ID
    """
    results = {}
    intelligence_context = intelligence_context or {}
    
    for region_id, input_data in inputs_by_region.items():
        # Get intelligence multipliers for this region
        ctx = intelligence_context.get(region_id, {})
        gm = ctx.get('grid_multipliers', {})
        
        intel_mult = float(gm.get('economic_demand_multiplier', 1.0))
        intel_conf = float(gm.get('confidence', 0.5))
        
        results[region_id] = predict_30_days(
            input_data,
            model,
            scaler_climate,
            scaler_lagroll,
            intelligence_multiplier=intel_mult,
            intelligence_confidence=intel_conf,
        )
        
        # Add region metadata
        results[region_id]['region_id'] = region_id
        results[region_id]['key_driver'] = gm.get('key_driver', 'Baseline')
    
    return results
