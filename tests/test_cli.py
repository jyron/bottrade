from __future__ import annotations

from bottrade.cli import build_parser


def test_cli_requires_a_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(["badge", "run-123"])
    assert args.command == "badge"
    assert args.run_id == "run-123"


def test_complete_run_command_exposes_human_usable_flags() -> None:
    args = build_parser().parse_args(
        [
            "run",
            "--scenario",
            "tech-2024-q2",
            "--quantity",
            "2.5",
            "--max-bars",
            "500",
            "--bot-name",
            "scholarly replication",
            "--output",
            "result.json",
            "--publish",
        ]
    )

    assert args.command == "run"
    assert args.scenario == "tech-2024-q2"
    assert args.quantity == 2.5
    assert args.max_bars == 500
    assert args.publish is True


def test_discovery_commands_offer_machine_readable_output() -> None:
    assert build_parser().parse_args(["scenarios", "--json"]).json is True
    assert build_parser().parse_args(["public-run", "run-1", "--json"]).json is True
