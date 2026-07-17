from pathlib import Path

from scripts.check_env_example import discover_env_names, documented_env_names, missing_env_names

FIXTURES = Path(__file__).parent / "fixtures"


def test_discovers_getenv_and_environ_get():
    source = FIXTURES / "env_inventory_calls.txt"
    assert discover_env_names([source]) == {"ALPHA", "BETA"}


def test_missing_output_is_deterministic_and_allowlisted():
    source = FIXTURES / "env_inventory_order.txt"
    documented = documented_env_names("ALPHA=value\n")
    assert missing_env_names([source], documented, allowlist={"ZED"}) == []
    assert missing_env_names([source], set(), allowlist=set()) == ["ALPHA", "ZED"]
