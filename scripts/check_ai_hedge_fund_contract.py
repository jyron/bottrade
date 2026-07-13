#!/usr/bin/env python3
"""Statically verify the upstream interfaces used by the AI Hedge Fund adapter."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

RUNNER_PARAMETERS = {
    "tickers",
    "start_date",
    "end_date",
    "portfolio",
    "show_reasoning",
    "selected_analysts",
    "model_name",
    "model_provider",
}
TECHNICAL_FUNCTIONS = {
    "calculate_trend_signals",
    "calculate_mean_reversion_signals",
    "calculate_momentum_signals",
    "calculate_volatility_signals",
    "calculate_stat_arb_signals",
    "weighted_signal_combination",
}


def functions(path: Path) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(path.read_text(), filename=str(path))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path, help="Checked-out virattt/ai-hedge-fund root.")
    args = parser.parse_args()

    runner = functions(args.upstream / "src" / "main.py").get("run_hedge_fund")
    if runner is None:
        raise SystemExit("missing src.main.run_hedge_fund")
    parameter_names = {argument.arg for argument in [*runner.args.args, *runner.args.kwonlyargs]}
    missing_parameters = RUNNER_PARAMETERS - parameter_names
    if missing_parameters:
        missing = ", ".join(sorted(missing_parameters))
        raise SystemExit("run_hedge_fund parameters missing: " + missing)

    technicals = functions(args.upstream / "src" / "agents" / "technicals.py")
    missing_functions = TECHNICAL_FUNCTIONS - technicals.keys()
    if missing_functions:
        raise SystemExit("technical functions missing: " + ", ".join(sorted(missing_functions)))

    print("AI Hedge Fund adapter contract verified")
    print("  runner: src.main.run_hedge_fund")
    print(f"  runner parameters: {len(RUNNER_PARAMETERS)} required names present")
    print(f"  technical functions: {len(TECHNICAL_FUNCTIONS)} required names present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
