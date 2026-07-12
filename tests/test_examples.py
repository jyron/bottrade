from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = [
    ROOT / "examples" / "plain-python" / "run_strategy.py",
    ROOT / "examples" / "openai-agents" / "run_agent.py",
    ROOT / "examples" / "langchain-langgraph" / "run_agent.py",
    ROOT / "examples" / "multi-provider" / "run_agent.py",
    ROOT / "examples" / "ai-hedge-fund" / "adapter.py",
]


def test_every_example_compiles_without_importing_provider_sdks() -> None:
    for path in EXAMPLES:
        compile(path.read_text(), str(path), "exec")


def test_every_runnable_example_makes_publication_explicit() -> None:
    for path in EXAMPLES:
        source = path.read_text()
        assert "--publish" in source, path
        assert "store_true" in source, path
