from __future__ import annotations

from bottrade.cli import build_parser


def test_cli_requires_a_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(["badge", "run-123"])
    assert args.command == "badge"
    assert args.run_id == "run-123"


def test_backtest_command_exposes_custom_agent_flags() -> None:
    args = build_parser().parse_args(
        [
            "backtest",
            "my_agent:decide",
            "--scenario",
            "tech-2024-q2",
            "--lookback",
            "24",
            "--max-steps",
            "500",
            "--name",
            "scholarly replication",
            "--output",
            "result.json",
            "--publish",
        ]
    )

    assert args.command == "backtest"
    assert args.agent == "my_agent:decide"
    assert args.scenario == "tech-2024-q2"
    assert args.lookback == 24
    assert args.max_steps == 500
    assert args.publish is True


def test_discovery_commands_offer_machine_readable_output() -> None:
    assert build_parser().parse_args(["scenarios", "--json"]).json is True
    assert build_parser().parse_args(["public-run", "run-1", "--json"]).json is True
