import json
import urllib.parse
import urllib.request
from pathlib import Path
import re

ENV_PATH = Path(".env")

def load_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
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

def check_code_exists(token: str, code: str) -> bool:
    url = f"https://id.who.int/icd/release/11/2024-01/mms/codeinfo/{urllib.parse.quote(code)}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    req.add_header("API-Version", "v2")
    req.add_header("Accept-Language", "en")
    try:
        with urllib.request.urlopen(req) as resp:
            return True
    except urllib.error.HTTPError as e:
        return False
    except Exception as e:
        return False

def expand_range(token: str, code_range: str) -> list[str]:
    match = re.match(r"^([A-Z0-9]+)0-([A-Z0-9]+)Z$", code_range)
    if not match:
        match2 = re.match(r"^([A-Z0-9]+)([0-9])-([A-Z0-9]+)([0-9])$", code_range)
        if match2 and match2.group(1) == match2.group(3):
            prefix = match2.group(1)
            start = int(match2.group(2))
            end = int(match2.group(4))
            codes = []
            for i in range(start, end + 1):
                code = f"{prefix}{i}"
                if check_code_exists(token, code):
                    codes.append(code)
            return codes
        
        match3 = re.match(r"^([A-Z0-9]+\.[A-Z0-9]+)0-([A-Z0-9]+\.[A-Z0-9]+)Z$", code_range)
        if match3 and match3.group(1) == match3.group(2):
            prefix = match3.group(1)
            valid_chars = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
            codes = []
            for char in valid_chars:
                code = f"{prefix}{char}"
                if check_code_exists(token, code):
                    codes.append(code)
            return codes
            
        return [code_range]
    
    prefix = match.group(1)
    if prefix != match.group(2):
        return [code_range]
    
    valid_chars = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    codes = []
    for char in valid_chars:
        code = f"{prefix}{char}"
        if check_code_exists(token, code):
            codes.append(code)
    
    return codes

def main():
    env = load_env(ENV_PATH)
    token = get_token(env)
    
    md_path = Path("tasks/cpg_scope_review.md")
    content = md_path.read_text(encoding="utf-8")
    
    lines = content.splitlines()
    new_lines = []
    
    for line in lines:
        if line.startswith("- Proposed icd11_scope:"):
            scope_str = line.split(":", 1)[1].strip()
            if scope_str == "(none)":
                new_lines.append(line)
                continue
                
            parts = [p.strip().strip("`") for p in scope_str.split(",")]
            expanded_parts = []
            for part in parts:
                if "-" in part:
                    codes = expand_range(token, part)
                    if codes:
                        expanded_parts.extend(codes)
                    else:
                        expanded_parts.append(part)
                else:
                    expanded_parts.append(part)
            
            # verify every single code
            verified_codes = []
            for code in expanded_parts:
                # ignore code_ranges that failed to expand
                if "-" in code:
                    verified_codes.append(code)
                    continue
                
                if check_code_exists(token, code):
                    verified_codes.append(code)
                else:
                    print(f"WARNING: Invalid ICD-11 code detected and removed: {code}")
            
            # remove duplicates
            seen = set()
            unique_expanded = []
            for ep in verified_codes:
                if ep not in seen:
                    unique_expanded.append(ep)
                    seen.add(ep)
            
            new_scope_str = ", ".join(f"`{c}`" for c in unique_expanded)
            if not new_scope_str:
                new_scope_str = "(none)"
            new_lines.append(f"- Proposed icd11_scope: {new_scope_str}")
        else:
            new_lines.append(line)
            
    md_path.write_text("\n".join(new_lines), encoding="utf-8")
    print("Done verifying all codes in cpg_scope_review.md")

if __name__ == "__main__":
    main()
