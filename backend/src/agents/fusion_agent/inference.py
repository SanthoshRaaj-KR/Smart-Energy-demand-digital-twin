"""
inference.py
------------
Preprocesses 7-day input windows and runs autoregressive 7-day ahead
predictions using the trained LightGBM model.

Expected input (dict or DataFrame) per call:
    - Date          : list/array of 7 dates (str or datetime)
    - State         : list/array of 7 region names
                      (mapped → "Region 1", "Region 2", "Region 3", "Region 4")
    - Actual_Drawl  : list/array of 7 historical drawl values
    - om_temp_mean  : list/array of 7 values  (weather for the NEXT 7 days, i.e. forecast horizon)
    - nasa_solar    : ...
    - om_dewpoint   : ...
    - om_wind_gusts : ...

Returns:
    dict with keys "dates" and "predicted_drawl" (7 values, one per future day)
"""

import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import StandardScaler, LabelEncoder


# ---------------------------------------------------------------------------
# Region name normalisation map
# Extend this dict if the raw names differ from what's shown here.
# ---------------------------------------------------------------------------
REGION_NAME_MAP = {
    "Region 1": "Region 1",
    "Region 2": "Region 2",
    "Region 3": "Region 3",
    "Region 4": "Region 4",
    "Bihar": "Region 1",
    "BHR": "Region 1",
    "NR UP": "Region 2",
    "UP": "Region 2",
    "West Bengal": "Region 3",
    "WB": "Region 3",
    "SR Karnataka": "Region 4",
    "KAR": "Region 4",
}

# State label encoding must match training exactly.
# The model was trained with LabelEncoder on merged full_df['State'].
# Adjust this mapping to match your training encoder's output.
# STATE_LABEL_MAP and YEAR_TO_LABEL are loaded at runtime from inference_meta.json

# ---------------------------------------------------------------------------
# Load artefacts
# ---------------------------------------------------------------------------

# Populated by load_artefacts() — used inside _encode_year()
_YEAR_TO_LABEL   = {}
_STATE_LABEL_MAP = {}

def load_artefacts(model_path: str,
                   scaler_climate_path: str,
                   scaler_lagroll_path: str,
                   meta_path: str):
    """Load model, scalers, and label mappings saved during training."""
    global _YEAR_TO_LABEL, _STATE_LABEL_MAP

    import json
    model          = joblib.load(model_path)
    scaler_climate = joblib.load(scaler_climate_path)
    scaler_lagroll = joblib.load(scaler_lagroll_path)

    with open(meta_path) as f:
        meta = json.load(f)

    _YEAR_TO_LABEL   = {int(k): v for k, v in meta['year_to_label'].items()}
    _STATE_LABEL_MAP = meta['state_label_map']   # {"Region 1": 0, ...}

    return model, scaler_climate, scaler_lagroll


# ---------------------------------------------------------------------------
# Feature engineering helpers
# ---------------------------------------------------------------------------

CLIMATIC_COLS  = ['om_temp_mean', 'nasa_solar', 'om_dewpoint', 'om_wind_gusts']
LAG_WINDOWS    = [1, 7, 14, 28]
ROLL_WINDOWS   = [1, 7, 14, 28]
ROLLSTD_WINDOWS = [1, 7]

MODEL_FEATURE_ORDER = [
    'State',
    'om_temp_mean', 'nasa_solar', 'om_dewpoint', 'om_wind_gusts',
    'yyyy',
    'dd_sin', 'dd_cos', 'mm_sin', 'mm_cos',
    'lag_1', 'lag_7', 'lag_14', 'lag_28',
    'roll_mean_1', 'roll_mean_7', 'roll_mean_14', 'roll_mean_28',
    'roll_std_1', 'roll_std_7',
]


def _cyclical_encode(df: pd.DataFrame) -> pd.DataFrame:
    df['dd_sin'] = np.sin(2 * np.pi * df['dd'] / 31)
    df['dd_cos'] = np.cos(2 * np.pi * df['dd'] / 31)
    df['mm_sin'] = np.sin(2 * np.pi * df['mm'] / 12)
    df['mm_cos'] = np.cos(2 * np.pi * df['mm'] / 12)
    return df


def _encode_year(year: int) -> int:
    """Uses the year_to_label map loaded from inference_meta.json."""
    return _YEAR_TO_LABEL.get(year, max(_YEAR_TO_LABEL.values(), default=0) + 1)


# ---------------------------------------------------------------------------
# Core: build a single-row feature vector for one future day
# ---------------------------------------------------------------------------

def _build_row(date: pd.Timestamp,
               state_label: int,
               weather_row: dict,
               history: list) -> dict:
    """
    Construct one feature row for the model.

    Parameters
    ----------
    date         : the date being predicted
    state_label  : integer-encoded state
    weather_row  : dict with climatic feature values for `date`
    history      : list of known Actual_Drawl values (chronological),
                   length >= 28 ideally; at minimum 1.
    """
    row = {}

    # State
    row['State'] = state_label

    # Climatic features (raw; will be scaled later)
    for col in CLIMATIC_COLS:
        row[col] = weather_row[col]

    # Calendar
    row['yyyy']   = _encode_year(date.year)
    row['dd']     = date.day
    row['mm']     = date.month

    # Lag features — index from end of history
    h = np.array(history, dtype=float)
    n = len(h)

    for lag in LAG_WINDOWS:
        row[f'lag_{lag}'] = h[-lag] if n >= lag else np.nan

    # Rolling means (shift=1 → window ends at h[-1])
    for window in ROLL_WINDOWS:
        if n >= window:
            row[f'roll_mean_{window}'] = h[-window:].mean()
        else:
            row[f'roll_mean_{window}'] = h.mean() if n > 0 else np.nan

    # Rolling std
    for window in ROLLSTD_WINDOWS:
        if n >= window:
            row[f'roll_std_{window}'] = h[-window:].std(ddof=1) if window > 1 else np.nan
        else:
            row[f'roll_std_{window}'] = np.nan

    return row


# ---------------------------------------------------------------------------
# Main inference function
# ---------------------------------------------------------------------------

def predict_next_7_days(input_data: dict,
                        model,
                        scaler_climate: StandardScaler,
                        scaler_lagroll: StandardScaler) -> dict:
    """
    Given 7 days of historical input, predict Actual_Drawl for the next 7 days.

    Parameters
    ----------
    input_data : dict with keys:
        'Date'          – 7 date strings or datetime objects
        'State'         – 7 region name strings (will be normalised via REGION_NAME_MAP)
        'Actual_Drawl'  – 7 historical drawl floats
        'om_temp_mean'  – 7 weather forecast floats (for the prediction horizon)
        'nasa_solar'    – 7 floats
        'om_dewpoint'   – 7 floats
        'om_wind_gusts' – 7 floats

    Returns
    -------
    dict:
        'dates'           – list of 7 future date strings (YYYY-MM-DD)
        'predicted_drawl' – list of 7 predicted Actual_Drawl values (original scale)
    """

    # --- 1. Parse & validate input ---
    dates         = pd.to_datetime(input_data['Date'])
    raw_states    = input_data['State']
    actual_drawls = list(map(float, input_data['Actual_Drawl']))

    # All 4 regions must be the same region in a single call
    # (the model predicts one region at a time)
    normalized_states = [REGION_NAME_MAP.get(s, "Region 1") for s in raw_states]
    assert len(set(normalized_states)) == 1, \
        "All 7 input rows must belong to the same region."
    state_label = _STATE_LABEL_MAP.get(normalized_states[0], 0)

    weather_forecast = []
    for i in range(7):
        weather_forecast.append({
            col: float(input_data[col][i]) for col in CLIMATIC_COLS
        })

    # --- 2. Build rolling history buffer (we have 7 seed days) ---
    # For lag_28/roll_mean_28 we only have 7 days → those will be NaN for
    # the first ~21 future days. That's expected; the model handles NaN.
    history = actual_drawls.copy()   # grows as we predict each day
    last_date = dates[-1]

    # --- 3. Autoregressive loop: predict days 1–7 ---
    future_dates      = []
    predicted_drawls  = []  # in original scale

    for step in range(7):
        future_date  = last_date + pd.DateOffset(days=step + 1)
        weather_row  = weather_forecast[step]

        # Build raw feature row
        row = _build_row(future_date, state_label, weather_row, history)

        # Convert to DataFrame for scaling
        df_row = pd.DataFrame([row])
        _cyclical_encode(df_row)
        df_row = df_row.drop(columns=['dd', 'mm'])

        # Scale climatic cols
        df_row[CLIMATIC_COLS] = scaler_climate.transform(df_row[CLIMATIC_COLS])

        # Scale lag + rolling cols
        lag_roll_cols = [c for c in df_row.columns
                         if 'lag_' in c or 'roll_' in c]
        df_row[lag_roll_cols] = scaler_lagroll.transform(df_row[lag_roll_cols])

        # Ensure column order matches training
        X = df_row[MODEL_FEATURE_ORDER]

        # Predict 
        pred_scaled = model.predict(X)[0]

        # No target scaler used; assume the output is already in MW
        pred_original = pred_scaled

        future_dates.append(future_date.strftime('%Y-%m-%d'))
        predicted_drawls.append(round(pred_original, 4))

        # Feed prediction back into history for next step
        history.append(pred_original)

    return {
        'dates':           future_dates,
        'predicted_drawl': predicted_drawls,
    }

def predict_all_regions(inputs_by_region: dict,
                        model,
                        scaler_climate,
                        scaler_lagroll) -> dict:
    results = {}
    for region, input_data in inputs_by_region.items():
        results[region] = predict_next_7_days(
            input_data, model, scaler_climate, scaler_lagroll
        )
    return results
