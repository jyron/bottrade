from __future__ import annotations

from bottrade.cli import build_parser


def test_cli_requires_a_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(["badge", "run-123"])
    assert args.command == "badge"
    assert args.run_id == "run-123"
