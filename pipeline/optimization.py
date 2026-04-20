from __future__ import annotations

import argparse
import copy
import json
import logging
from pathlib import Path
from typing import Any

import optuna
import pandas as pd

from pipeline.backtest_signal import (
    DEFAULT_BASE_PATH,
    DEFAULT_CONFIG_DIR,
    DEFAULT_MACRO_FREQ,
    DEFAULT_SECTOR_FREQ,
    DEFAULT_SYMBOL_FREQ,
    _load_config_bundle,
    _log_df,
    _parse_bar_frequency,
    _resolve_macro_inputs,
    _resolve_sector_etf_df,
    setup_logging,
)

from quant.engine.feature_engine import build_feature_frame
from quant.engine.signal_engine import compute_action_signals
from quant.engine.signal_evaluator import evaluate_signal_sequence

from utils.parquet_loader import (
    load_macro_bars,
    load_sector_bars,
    load_symbol_bars,
)

logger = logging.getLogger(__name__)
OPTIMIZATION_DIR = Path(__file__).resolve().parent


def _deep_set(d: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cur = d
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _apply_candidate_params(
    base_config: dict[str, Any],
    candidate_params: dict[str, Any],
) -> dict[str, Any]:
    cfg = copy.deepcopy(base_config)
    for k, v in candidate_params.items():
        _deep_set(cfg, k, v)
    return cfg


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, tuple):
        return [_json_safe(x) for x in obj]
    if hasattr(obj, "value"):
        return obj.value
    try:
        import numpy as np
        if isinstance(obj, (np.floating, np.integer)):
            return obj.item()
    except Exception:
        pass
    return obj


def _suggest_candidate_params(trial: optuna.trial.Trial) -> dict[str, Any]:
    """
    第一轮：
    优先优化 symbol.state 中最影响 trend / range / risk 切换的关键阈值。
    """
    return { 

        # =========================
        # 趋势后期 / 失效 / 反转压力
        # =========================
     
        "symbol.state.failure_threshold": trial.suggest_float(
            "symbol.state.failure_threshold", 0.25, 0.55
        ),
        "symbol.state.breakout_failure_threshold": trial.suggest_float(
            "symbol.state.breakout_failure_threshold", 0.20, 0.50
        ),
        "symbol.state.reversal_pressure_threshold": trial.suggest_float(
            "symbol.state.reversal_pressure_threshold", 0.25, 0.60
        ),
        "symbol.state.strong_reversal_pressure_threshold": trial.suggest_float(
            "symbol.state.strong_reversal_pressure_threshold", 0.35, 0.75
        ), 
    }

def _load_inputs(
    *,
    symbol: str,
    sector: str,
    start_date: str,
    end_date: str,
    sector_etf: str | None,
    base_path: str | Path,
    config_dir: str | Path,
    symbol_freq: str,
    sector_freq: str,
    macro_freq: str,
    strict: bool,
) -> dict[str, Any]:
    logger.info("Loading optimization inputs...")

    config_bundle = _load_config_bundle(config_dir)

    symbol_target_freq = _parse_bar_frequency(symbol_freq)
    sector_target_freq = _parse_bar_frequency(sector_freq)
    macro_target_freq = _parse_bar_frequency(macro_freq)

    symbol_df = load_symbol_bars(
        base_path=base_path,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        target_freq=symbol_target_freq,
        strict=strict,
    )
    _log_df("symbol_df", symbol_df)

    sector_member_dfs = load_sector_bars(
        base_path=base_path,
        sector_name=sector,
        start_date=start_date,
        end_date=end_date,
        target_freq=sector_target_freq,
        strict=strict,
    )
    logger.info("sector_member_dfs loaded | symbols=%s", list(sector_member_dfs.keys()))

    sector_etf_df = _resolve_sector_etf_df(sector_member_dfs, sector_etf=sector_etf)
    _log_df("sector_etf_df", sector_etf_df)

    macro_data = load_macro_bars(
        base_path=base_path,
        start_date=start_date,
        end_date=end_date,
        target_freq=macro_target_freq,
        strict=strict,
    )
    logger.info("macro_data loaded | symbols=%s", list(macro_data.keys()))

    spy_df, vix_df, hy_oas_df = _resolve_macro_inputs(macro_data)
    _log_df("spy_df", spy_df)
    _log_df("vix_df", vix_df)
    _log_df("hy_oas_df", hy_oas_df)

    return {
        "symbol_df": symbol_df,
        "sector_etf_df": sector_etf_df,
        "sector_member_dfs": sector_member_dfs,
        "spy_df": spy_df,
        "vix_df": vix_df,
        "hy_oas_df": hy_oas_df,
        "base_config": config_bundle,
    }


def _evaluate_candidate(
    *,
    loaded_inputs: dict[str, Any],
    candidate_params: dict[str, Any],
    horizon: int,
) -> tuple[float, dict[str, Any]]:
    cfg = _apply_candidate_params(loaded_inputs["base_config"], candidate_params)

    feature_df = build_feature_frame(
        symbol_df=loaded_inputs["symbol_df"],
        sector_etf_df=loaded_inputs["sector_etf_df"],
        sector_member_dfs=loaded_inputs["sector_member_dfs"],
        spy_df=loaded_inputs["spy_df"],
        vix_df=loaded_inputs["vix_df"],
        hy_oas_df=loaded_inputs["hy_oas_df"],
        config_bundle=cfg,
    )

    action_signals = compute_action_signals(feature_df, cfg["signal"])

    # 关键修复：evaluator 需要真实价格列 close
    eval_df = loaded_inputs["symbol_df"].join(
        feature_df,
        how="left",
        rsuffix="_feature",
    )
    eval_df["action_signal"] = action_signals

    if "close" not in eval_df.columns:
        raise ValueError(
            f"eval_df missing close after join, columns={list(eval_df.columns)}"
        )

    score, details = evaluate_signal_sequence(
        bar_df=eval_df,
        signal_col="action_signal",
        close_col="close",
        horizon=horizon,
    )

    return score, details


def _build_default_output_prefix(
    symbol: str,
    start_date: str,
    end_date: str,
    study_name: str,
) -> Path:
    safe_start = start_date.replace("-", "")
    safe_end = end_date.replace("-", "")
    return OPTIMIZATION_DIR / f"{study_name}_{symbol}_{safe_start}_{safe_end}"


def run_signal_optimization(
    *,
    symbol: str,
    sector: str,
    start_date: str,
    end_date: str,
    sector_etf: str | None = None,
    base_path: str | Path = DEFAULT_BASE_PATH,
    config_dir: str | Path = DEFAULT_CONFIG_DIR,
    symbol_freq: str = DEFAULT_SYMBOL_FREQ,
    sector_freq: str = DEFAULT_SECTOR_FREQ,
    macro_freq: str = DEFAULT_MACRO_FREQ,
    strict: bool = False,
    horizon: int = 10,
    n_trials: int = 50,
    study_name: str = "signal_opt",
    out_prefix: str | Path | None = None,
) -> dict[str, Any]:
    logger.info("========== Start signal optimization ==========")

    loaded_inputs = _load_inputs(
        symbol=symbol,
        sector=sector,
        start_date=start_date,
        end_date=end_date,
        sector_etf=sector_etf,
        base_path=base_path,
        config_dir=config_dir,
        symbol_freq=symbol_freq,
        sector_freq=sector_freq,
        macro_freq=macro_freq,
        strict=strict,
    )

    trial_log: list[dict[str, Any]] = []

    def objective(trial: optuna.trial.Trial) -> float:
        candidate_params = _suggest_candidate_params(trial)

        try:
            score, details = _evaluate_candidate(
                loaded_inputs=loaded_inputs,
                candidate_params=candidate_params,
                horizon=horizon,
            )

            trial_record = {
                "trial_number": trial.number,
                "score": score,
                "params": candidate_params,
                "switch_rate": details.get("switch_rate"),
                "run_counts": details.get("run_counts"),
                "per_signal_avg_score": details.get("per_signal_avg_score"),
            }
            trial_log.append(_json_safe(trial_record))

            trial.set_user_attr("details", _json_safe(details))
            return float(score)

        except Exception as e:
            logger.exception("Trial %s failed", trial.number)

            trial_record = {
                "trial_number": trial.number,
                "score": None,
                "params": candidate_params,
                "error": str(e),
            }
            trial_log.append(_json_safe(trial_record))
            raise

    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
    )
    study.optimize(objective, n_trials=n_trials, catch=(Exception,))

    if study.best_trial is None:
        raise RuntimeError("Optimization finished but no successful trial was found.")

    best_params = study.best_trial.params
    best_score, best_details = _evaluate_candidate(
        loaded_inputs=loaded_inputs,
        candidate_params=best_params,
        horizon=horizon,
    )

    result = {
        "study_name": study_name,
        "symbol": symbol,
        "sector": sector,
        "sector_etf": sector_etf,
        "start_date": start_date,
        "end_date": end_date,
        "best_score": best_score,
        "best_params": _json_safe(best_params),
        "best_details": _json_safe(best_details),
        "n_trials": n_trials,
    }

    if out_prefix is None:
        out_prefix = _build_default_output_prefix(symbol, start_date, end_date, study_name)
    out_prefix = Path(out_prefix)

    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    with (out_prefix.parent / f"{out_prefix.name}_best.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(result), f, ensure_ascii=False, indent=2)

    with (out_prefix.parent / f"{out_prefix.name}_trials.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(trial_log), f, ensure_ascii=False, indent=2)

    with (out_prefix.parent / f"{out_prefix.name}_best_params.json").open("w", encoding="utf-8") as f:
        json.dump(_json_safe(best_params), f, ensure_ascii=False, indent=2)

    logger.info("========== Signal optimization finished ==========")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optimize signal-engine parameters")

    parser.add_argument("--symbol", required=True, help="Target symbol, e.g. UUUU")
    parser.add_argument("--sector", required=True, help="Sector name, e.g. rare_earth")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")

    parser.add_argument(
        "--sector-etf",
        required=False,
        help="Explicit sector ETF proxy, e.g. REMX",
    )

    parser.add_argument("--base-path", default=DEFAULT_BASE_PATH)
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)

    parser.add_argument(
        "--symbol-freq",
        default=DEFAULT_SYMBOL_FREQ,
        choices=["1min", "5min", "15min", "30min", "1h", "1d"],
    )
    parser.add_argument(
        "--sector-freq",
        default=DEFAULT_SECTOR_FREQ,
        choices=["1min", "5min", "15min", "30min", "1h", "1d"],
    )
    parser.add_argument(
        "--macro-freq",
        default=DEFAULT_MACRO_FREQ,
        choices=["1min", "5min", "15min", "30min", "1h", "1d"],
    )

    # 默认 False；优化阶段建议非 strict
    parser.add_argument("--strict", action="store_true", help="Enable strict parquet checking")

    parser.add_argument("--horizon", type=int, default=10, help="Forward bars used by signal evaluator")
    parser.add_argument("--n-trials", type=int, default=50, help="Number of optimization trials")
    parser.add_argument("--study-name", default="signal_opt")
    parser.add_argument("--out-prefix", required=False, help="Optional output prefix path")

    return parser


def main() -> None:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    result = run_signal_optimization(
        symbol=args.symbol,
        sector=args.sector,
        start_date=args.start_date,
        end_date=args.end_date,
        sector_etf=args.sector_etf,
        base_path=args.base_path,
        config_dir=args.config_dir,
        symbol_freq=args.symbol_freq,
        sector_freq=args.sector_freq,
        macro_freq=args.macro_freq,
        strict=args.strict,
        horizon=args.horizon,
        n_trials=args.n_trials,
        study_name=args.study_name,
        out_prefix=args.out_prefix,
    )

    print("\n=== OPTIMIZATION COMPLETE ===")
    print(f"best_score = {result['best_score']}")
    print("best_params =")
    print(json.dumps(result["best_params"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()