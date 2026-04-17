from __future__ import annotations

import pandas as pd

from quant.common.enums import ActionSignal


def _validate_required_columns(feature_df: pd.DataFrame) -> None:
    required_cols = [
        "symbol_state",
        "sector_state_sector",
        "macro_state_macro",
    ]
    missing = [c for c in required_cols if c not in feature_df.columns]
    if missing:
        raise ValueError(f"Missing required columns for signal engine: {missing}")


def _parse_action(value: str) -> ActionSignal:
    try:
        return ActionSignal(value)
    except ValueError as exc:
        raise ValueError(f"Invalid action config value: {value}") from exc


def _normalize_state_value(value) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    if hasattr(value, "value"):
        return str(value.value).lower()

    return str(value).lower()


def compute_action_signals(
    feature_df: pd.DataFrame,
    config: dict,
) -> pd.Series:
    """
    Compute action signals from unified feature frame.
    """

    _validate_required_columns(feature_df)
    print("\n=== symbol_state value counts ===")
    print(feature_df["symbol_state"].value_counts(dropna=False))

    print("\n=== sector_state_sector value counts ===")
    print(feature_df["sector_state_sector"].value_counts(dropna=False))

    print("\n=== macro_state_macro value counts ===")
    print(feature_df["macro_state_macro"].value_counts(dropna=False))

    signal_cfg = config.get("signal", config)

    signal_cfg = config.get("signal", config)

    enable_risk_filter = bool(signal_cfg.get("enable_risk_filter", True))
    enable_sector_filter = bool(signal_cfg.get("enable_sector_filter", True))

    allow_trend_buy = bool(signal_cfg.get("allow_trend_buy", True))
    allow_pullback_buy = bool(signal_cfg.get("allow_pullback_buy", True))
    allow_breakout_buy = bool(signal_cfg.get("allow_breakout_buy", True))

    breakout_requires_non_weak_sector = bool(
        signal_cfg.get("breakout_requires_non_weak_sector", True)
    )

    exhausted_action = _parse_action(signal_cfg.get("exhausted_action", "reduce"))
    breakdown_action = _parse_action(signal_cfg.get("breakdown_action", "sell"))
    high_risk_action = _parse_action(signal_cfg.get("high_risk_action", "sell"))
    default_action = _parse_action(signal_cfg.get("default_action", "hold"))

    macro_state = feature_df["macro_state_macro"]
    sector_state = feature_df["sector_state_sector"]
    symbol_state = feature_df["symbol_state"]

    signals: list[ActionSignal] = []

    for i in range(len(feature_df)):
        m = _normalize_state_value(macro_state.iloc[i])
        s = _normalize_state_value(sector_state.iloc[i])
        sym = _normalize_state_value(symbol_state.iloc[i])

        # 1. Macro gating
        if enable_risk_filter and m == "risk_off":
            signals.append(ActionSignal.AVOID)
            continue

        # 2. Sector gating
        if enable_sector_filter and s == "weak":
            if sym in ["range_distribution", "risk_rising", "trend_late"]:
                signals.append(ActionSignal.REDUCE)
                continue

        # 3. Symbol mapping
        if sym == "trend_early":
            signals.append(ActionSignal.BUY if allow_trend_buy else default_action)

        elif sym == "trend_continuation":
            signals.append(ActionSignal.HOLD)

        elif sym == "trend_late":
            signals.append(ActionSignal.REDUCE)

        elif sym == "trend_exhaustion":
            signals.append(exhausted_action)

        elif sym == "pullback":
            signals.append(ActionSignal.BUY if allow_pullback_buy else default_action)

        elif sym == "breakout_setup":
            if allow_breakout_buy:
                if breakout_requires_non_weak_sector and s == "weak":
                    signals.append(ActionSignal.AVOID)
                else:
                    signals.append(ActionSignal.BUY)
            else:
                signals.append(default_action)

        elif sym == "breakout":
            if allow_breakout_buy:
                if breakout_requires_non_weak_sector and s == "weak":
                    signals.append(ActionSignal.AVOID)
                else:
                    signals.append(ActionSignal.BUY)
            else:
                signals.append(default_action)

        elif sym == "breakout_failed":
            signals.append(ActionSignal.SELL)

        elif sym == "range_accumulation":
            signals.append(ActionSignal.HOLD)

        elif sym == "range_neutral":
            signals.append(ActionSignal.HOLD)

        elif sym == "range_distribution":
            signals.append(ActionSignal.REDUCE)

        elif sym == "risk_rising":
            signals.append(ActionSignal.REDUCE)

        elif sym == "risk_high":
            signals.append(high_risk_action)

        elif sym == "breakdown_risk":
            signals.append(breakdown_action)

        else:
            signals.append(default_action)

    return pd.Series(signals, index=feature_df.index, name="action_signal")