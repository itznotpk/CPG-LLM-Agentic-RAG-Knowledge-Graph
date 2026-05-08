"""Verify ICD-11 code scope via WHO ICD API using .env credentials."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path


ENV_PATH = Path(".env")


def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[key.strip()] = val.strip()
    return data


def get_token(env: dict[str, str]) -> str:
    payload = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": env["ICD11_CLIENT_ID"],
            "client_secret": env["ICD11_CLIENT_SECRET"],
            "scope": "icdapi_access",
        }
    ).encode("utf-8")

    req = urllib.request.Request(env["ICD11_TOKEN_URL"], data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        token_data = json.loads(resp.read().decode("utf-8"))

    token = token_data.get("access_token")
    if not token:
        raise RuntimeError("No access_token returned")
    return token


def lookup(env: dict[str, str], token: str, code: str) -> dict:
    url = f"{env['ICD11_API_BASE']}/lookup?code={urllib.parse.quote(code)}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    if not ENV_PATH.exists():
        raise SystemExit(".env not found")

    env = load_env(ENV_PATH)
    for key in ("ICD11_CLIENT_ID", "ICD11_CLIENT_SECRET", "ICD11_TOKEN_URL", "ICD11_API_BASE"):
        if key not in env:
            raise SystemExit(f"Missing {key} in .env")

    token = get_token(env)

    for code in ("2C60", "2C6Z"):
        data = lookup(env, token, code)
        title = data.get("title", "")
        parent = data.get("parent", None)
        print(f"{code}: {title}")
        if parent:
            if isinstance(parent, list):
                print(f"  parent: {parent[0]}")
            else:
                print(f"  parent: {parent}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
