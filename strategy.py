from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

DEFAULT_SCAN_CLAUSE = (
    '( {cash} ( latest close >= 50 and latest close > latest open and '
    'latest close > EMA(close,20) and latest close > SMA(close,50) '
    'and latest volume > 1.4 x SMA(volume,20) ) )'
)
DEFAULT_COLUMN_CLAUSE = (
    'latest close, industry, latest high, latest low, latest volume, '
    'SMA(close,20), SMA(close,50), EMA(close,20), EMA(close,50), '
    'RSI(14), MACD(12,26)'
)

EXCLUDE_KEYWORDS = ["NIFTY", "BANKNIFTY", "CNX", "FINNIFTY", "SENSEX"]


def _safe_float(value: Optional[object], default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default


def _get_field(row: Dict[str, object], field_name: str) -> Optional[object]:
    if field_name in row:
        return row[field_name]
    compact = field_name.replace(" ", "")
    if compact in row:
        return row[compact]
    lower = field_name.lower()
    if lower in row:
        return row[lower]
    lower_compact = compact.lower()
    return row.get(lower_compact)


@dataclass
class SwingPick:
    ticker: str
    name: str
    close: float
    percent_change: float
    volume: float
    avg_volume: Optional[float]
    high: float
    low: float
    sma20: float
    sma50: float
    ema20: float
    ema50: float
    rsi: float
    macd: float
    industry: str
    score: float
    target: float
    stop_loss: float
    entry: float
    holding_period: str
    risk_pct: float
    reward_pct: float
    comment: str


def is_valid_candidate(row: Dict[str, object], exclude_keywords: List[str]) -> bool:
    ticker = str(row.get("nsecode", "")).upper()
    name = str(row.get("name", "")).upper()
    if any(keyword in ticker or keyword in name for keyword in exclude_keywords):
        return False

    if _safe_float(_get_field(row, "latest close") or _get_field(row, "close")) < 50:
        return False

    volume = _safe_float(_get_field(row, "latest volume") or _get_field(row, "volume"))
    if volume < 1000:
        return False

    return True


def build_score(row: Dict[str, object]) -> float:
    close = _safe_float(_get_field(row, "latest close") or _get_field(row, "close"))
    sma20 = _safe_float(_get_field(row, "sma(close,20)"))
    sma50 = _safe_float(_get_field(row, "sma(close,50)"))
    ema20 = _safe_float(_get_field(row, "ema(close,20)"))
    ema50 = _safe_float(_get_field(row, "ema(close,50)"))
    volume = _safe_float(_get_field(row, "latest volume") or _get_field(row, "volume"))
    avg_volume_field = _get_field(row, "sma(volume,20)")
    avg_volume = _safe_float(avg_volume_field) if avg_volume_field is not None else None
    rsi = _safe_float(_get_field(row, "rsi(14)"), 60.0)
    macd = _safe_float(_get_field(row, "macd(12,26)"), 0.0)
    percent_change = _safe_float(_get_field(row, "per_chg"), 0.0)

    trend = 0.0
    if sma20 > 0:
        trend += max(0.0, (close / sma20 - 1.0) * 100.0) * 1.8
    if sma50 > 0:
        trend += max(0.0, (close / sma50 - 1.0) * 100.0) * 1.2
    if ema20 > 0:
        trend += max(0.0, (close / ema20 - 1.0) * 100.0) * 1.6
    if ema50 > 0:
        trend += max(0.0, (close / ema50 - 1.0) * 100.0) * 1.0

    if avg_volume and avg_volume > 0:
        volume_ratio = volume / avg_volume
        volume_score = min(volume_ratio, 5.0) * 18.0
    else:
        volume_ratio = min(volume / 10000.0, 5.0)
        volume_score = volume_ratio * 12.0

    rsi_distance = abs(rsi - 58.0)
    rsi_score = max(0.0, 24.0 - rsi_distance) * 1.3

    macd_score = 18.0 if macd > 0 else -12.0
    momentum_score = max(0.0, percent_change * 4.0)

    base = trend + volume_score + rsi_score + macd_score + momentum_score
    reward_boost = max(0.0, (volume_ratio - 1.0)) * 4.0
    return base + reward_boost


def compute_trade_levels(row: Dict[str, object]) -> tuple[float, float, float, float, float]:
    close = _safe_float(_get_field(row, "latest close") or _get_field(row, "close"))
    high = _safe_float(_get_field(row, "latest high"))
    low = _safe_float(_get_field(row, "latest low"), close)
    if high <= low:
        high = close
        low = close * 0.98

    range_pct = max(0.01, (high - low) / close)
    stop_distance = max(0.012, min(0.06, range_pct * 1.2))
    stop_loss = round(close * (1.0 - stop_distance), 2)
    entry = round(close, 2)
    target = round(close * (1.0 + stop_distance * 2.8), 2)
    risk_pct = round(stop_distance * 100.0, 2)
    reward_pct = round((target / close - 1.0) * 100.0, 2)
    return target, stop_loss, entry, risk_pct, reward_pct


def categorize_industry(raw_industry: Optional[str]) -> str:
    if not raw_industry:
        return "general"
    text = str(raw_industry).strip().lower()
    if any(keyword in text for keyword in ["auto", "tyre", "tyres", "cement", "steel", "metal", "oil", "gas", "power", "realty", "construction", "engineering", "capital"]):
        return "cyclical"
    if any(keyword in text for keyword in ["pharma", "health", "hospital", "consumer", "food", "fmcg", "telecom", "utility", "retail"]):
        return "defensive"
    if any(keyword in text for keyword in ["software", "tech", "it", "media", "chemical", "finance", "bank", "mining"]):
        return "growth"
    return "general"


def estimate_holding_period(pick: SwingPick) -> str:
    reward = pick.reward_pct
    trend_strength = max(
        0.0,
        ((pick.close / pick.ema20 if pick.ema20 > 0 else 1.0)
         + (pick.close / pick.ema50 if pick.ema50 > 0 else 1.0)
         + (pick.close / pick.sma20 if pick.sma20 > 0 else 1.0)
         + (pick.close / pick.sma50 if pick.sma50 > 0 else 1.0)) / 4.0 - 1.0,
    )
    volatility = max(0.0, (pick.high - pick.low) / pick.close * 100.0 if pick.close > 0 else 0.0)
    category = categorize_industry(pick.industry)

    if reward < 6.0:
        base_bucket = 0
    elif reward < 10.0:
        base_bucket = 1
    elif reward < 14.0:
        base_bucket = 2
    elif reward < 20.0:
        base_bucket = 3
    elif reward < 32.0:
        base_bucket = 4
    else:
        base_bucket = 5

    bucket = base_bucket

    if trend_strength >= 0.12 and volatility <= 3.5:
        bucket = max(0, bucket - 2)
    elif trend_strength >= 0.08 and volatility <= 5.0:
        bucket = max(0, bucket - 1)

    if volatility >= 8.0:
        bucket = min(bucket + 1, 5)

    if category == "cyclical" and trend_strength >= 0.06:
        bucket = max(0, bucket - 1)
    elif category == "defensive" and reward >= 12.0:
        bucket = min(bucket + 1, 5)
    elif category == "growth" and trend_strength >= 0.10 and reward >= 15.0:
        bucket = max(0, bucket - 1)

    buckets = [
        "1-4 days",
        "4-9 days",
        "1-2 weeks",
        "2-4 weeks",
        "4-8 weeks",
        "6-12 weeks",
    ]
    return buckets[bucket]


def build_analysis_text(pick: SwingPick) -> str:
    if pick.avg_volume and pick.avg_volume > 0:
        volume_text = f"Volume {pick.volume / pick.avg_volume:.1f}x 20-day average. "
    else:
        volume_text = "Volume strength confirmed by the scan filter. "
    return (
        f"Entry around {pick.entry:.2f}. {volume_text}"
        f"RSI {pick.rsi:.1f}, MACD {pick.macd:.1f}. "
        f"Target {pick.target:.2f}, SL {pick.stop_loss:.2f}. "
        f"Expected hold {pick.holding_period}."
    )


def build_scan_clause(scan_config: Optional[Dict[str, object]] = None) -> str:
    if scan_config and scan_config.get("scan_clause"):
        return str(scan_config["scan_clause"])
    min_close = _safe_float(scan_config.get("min_close", 50.0), 50.0) if scan_config else 50.0
    min_volume_ratio = _safe_float(scan_config.get("min_volume_ratio", 1.4), 1.4) if scan_config else 1.4
    return (
        f"( {{cash}} ( latest close >= {min_close:.1f} and latest close > latest open "
        f"and latest close > EMA(close,20) and latest close > SMA(close,50) "
        f"and latest volume > {min_volume_ratio:.1f} x SMA(volume,20) ) )"
    )


def build_swing_picks(
    rows: List[Dict[str, object]],
    top_n: int = 3,
    exclude_keywords: Optional[List[str]] = None,
) -> List[SwingPick]:
    exclude_keywords = exclude_keywords or EXCLUDE_KEYWORDS
    candidates: List[SwingPick] = []

    for row in rows:
        if not is_valid_candidate(row, exclude_keywords):
            continue

        target, stop_loss, entry, risk_pct, reward_pct = compute_trade_levels(row)
        industry = str(_get_field(row, "industry") or "").strip()
        pick = SwingPick(
            ticker=str(_get_field(row, "nsecode") or "").strip().upper(),
            name=str(_get_field(row, "name") or "").strip(),
            close=_safe_float(_get_field(row, "latest close") or _get_field(row, "close")),
            percent_change=_safe_float(_get_field(row, "per_chg"), 0.0),
            volume=_safe_float(_get_field(row, "latest volume") or _get_field(row, "volume")),
            avg_volume=_safe_float(_get_field(row, "sma(volume,20)")) if _get_field(row, "sma(volume,20)") is not None else None,
            high=_safe_float(_get_field(row, "latest high")),
            low=_safe_float(_get_field(row, "latest low")),
            sma20=_safe_float(_get_field(row, "sma(close,20)")),
            sma50=_safe_float(_get_field(row, "sma(close,50)")),
            ema20=_safe_float(_get_field(row, "ema(close,20)")),
            ema50=_safe_float(_get_field(row, "ema(close,50)")),
            rsi=_safe_float(_get_field(row, "rsi(14)"), 60.0),
            macd=_safe_float(_get_field(row, "macd(12,26)"), 0.0),
            industry=industry,
            score=0.0,
            target=target,
            stop_loss=stop_loss,
            entry=entry,
            holding_period="",
            risk_pct=risk_pct,
            reward_pct=reward_pct,
            comment="",
        )
        pick.score = build_score(row)
        pick.holding_period = estimate_holding_period(pick)
        pick.comment = build_analysis_text(pick)
        candidates.append(pick)

    candidates.sort(key=lambda p: p.score, reverse=True)
    return candidates[:top_n]
