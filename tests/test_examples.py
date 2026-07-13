from __future__ import annotations

import ast
import importlib.util
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


def test_every_long_flag_is_documented_in_its_example_readme() -> None:
    for path in EXAMPLES:
        tree = ast.parse(path.read_text())
        flags = {
            argument.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            for argument in node.args
            if isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
            and argument.value.startswith("--")
        }
        readme = (path.parent / "README.md").read_text()
        assert flags
        for flag in flags:
            assert f"`{flag}" in readme, f"{flag} is absent from {path.parent / 'README.md'}"


def test_multi_provider_accepts_plain_and_fenced_json() -> None:
    path = ROOT / "examples" / "multi-provider" / "run_agent.py"
    spec = importlib.util.spec_from_file_location("multi_provider_example", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.extract_json('{"rationale":"hold","trades":[]}')["trades"] == []
    assert module.extract_json('```json\n{"rationale":"hold","trades":[]}\n```')[
        "rationale"
    ] == "hold"
