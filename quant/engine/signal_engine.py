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


def compute_action_signals(
    feature_df: pd.DataFrame,
    config: dict,
) -> pd.Series:
    """
    Compute action signals from feature frame.

    Input:
        feature_df: output of feature_engine
        config: signal config dict
                expected shape:
                {
                    "signal": {...}
                }
                or directly:
                {
                    "enable_risk_filter": ...
                }

    Output:
        pd.Series[ActionSignal]
    """
    _validate_required_columns(feature_df)

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
        m = str(macro_state.iloc[i])
        s = str(sector_state.iloc[i])
        sym = str(symbol_state.iloc[i])

        # 1. Macro gating
        if enable_risk_filter and m == "risk_off":
            signals.append(ActionSignal.AVOID)
            continue

        # 2. Sector gating
        if enable_sector_filter and s == "weak":
            signals.append(ActionSignal.AVOID)
            continue

        # 3. Symbol mapping
        if sym == "trend":
            if allow_trend_buy:
                signals.append(ActionSignal.BUY)
            else:
                signals.append(default_action)

        elif sym == "pullback":
            if allow_pullback_buy:
                signals.append(ActionSignal.BUY)
            else:
                signals.append(default_action)

        elif sym == "breakout_setup":
            if allow_breakout_buy:
                if breakout_requires_non_weak_sector and s == "weak":
                    signals.append(ActionSignal.AVOID)
                else:
                    signals.append(ActionSignal.BUY)
            else:
                signals.append(default_action)

        elif sym == "exhausted":
            signals.append(exhausted_action)

        elif sym == "breakdown_risk":
            signals.append(breakdown_action)

        elif sym == "high_risk":
            signals.append(high_risk_action)

        else:
            signals.append(default_action)

    return pd.Series(signals, index=feature_df.index, name="action_signal")