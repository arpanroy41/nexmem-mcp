"""Interactive setup wizard for nexmem-mcp init."""

from __future__ import annotations

import getpass
import json
import sys

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[0;32m"
CYAN = "\033[0;36m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
NC = "\033[0m"

BACKENDS = [
    ("jsonl", "JSONL files", "zero dependencies"),
    ("sqlite", "SQLite", "lightweight local database"),
    ("mongodb", "MongoDB", "recommended for teams"),
    ("postgres", "PostgreSQL", "JSONB storage"),
    ("redis", "Redis", "fast, JSON module"),
]

BACKEND_URI_DEFAULTS = {
    "mongodb": ("NEXMEM_MONGODB_URI", "mongodb://localhost:27017/nexmem"),
    "postgres": ("NEXMEM_POSTGRES_URI", "postgresql://localhost:5432/nexmem"),
    "redis": ("NEXMEM_REDIS_URL", "redis://localhost:6379/0"),
}


def _prompt(message: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"   {message}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    return value or default


def _prompt_choice(message: str, max_val: int, default: int = 1) -> int:
    raw = _prompt(message, str(default))
    try:
        choice = int(raw)
        if 1 <= choice <= max_val:
            return choice
    except ValueError:
        pass
    print(f"{RED}   Invalid choice.{NC}", file=sys.stderr)
    sys.exit(1)


def run_init() -> None:
    """Run the interactive setup wizard and print the mcp.json config snippet."""
    print(f"\n{BOLD}{CYAN}NexMem MCP — Interactive Setup{NC}\n")

    # Step 1: Memory mode
    print(f"{BOLD}1. Memory Mode{NC}")
    print("   [1] Self  — personal memory, just for you")
    print("   [2] Team  — shared memory across your team")
    mode_choice = _prompt_choice("Choose (1/2)", max_val=2, default=1)

    team_name = ""
    if mode_choice == 2:
        nexmem_mode = "team"
        team_name = _prompt("Team name")
        if not team_name:
            print(f"{RED}   Error: Team name is required for team mode.{NC}", file=sys.stderr)
            sys.exit(1)
    else:
        nexmem_mode = "self"

    user_name = getpass.getuser()
    print()

    # Step 2: Storage backend
    print(f"{BOLD}2. Storage Backend{NC}")
    for i, (_, label, hint) in enumerate(BACKENDS, 1):
        print(f"   [{i}] {label:<16} {DIM}({hint}){NC}")
    backend_choice = _prompt_choice("Choose (1-5)", max_val=5, default=1)
    backend_key = BACKENDS[backend_choice - 1][0]

    uri_env_name = ""
    uri_value = ""
    if backend_key in BACKEND_URI_DEFAULTS:
        env_name, default_uri = BACKEND_URI_DEFAULTS[backend_key]
        uri_value = _prompt(f"{BACKENDS[backend_choice - 1][1]} URI", default_uri)
        uri_env_name = env_name
    print()

    # Step 3: pip install hint
    print(f"{BOLD}3. Install{NC}")
    if backend_key in ("jsonl", "sqlite"):
        pkg = "mcp-nexmem"
    else:
        pkg = f'"mcp-nexmem[{backend_key}]"'
    print(f"   Make sure the package is installed: {CYAN}pip install {pkg}{NC}")
    print()

    # Step 4: Generate config
    env_block: dict[str, str] = {
        "NEXMEM_MODE": nexmem_mode,
        "NEXMEM_BACKEND": backend_key,
        "NEXMEM_USER_NAME": user_name,
    }
    if team_name:
        env_block["NEXMEM_TEAM_NAME"] = team_name
    if uri_env_name:
        env_block[uri_env_name] = uri_value

    config = {
        "mcpServers": {
            "nexmem": {
                "command": "nexmem-mcp",
                "env": env_block,
            }
        }
    }

    print(f"{BOLD}4. MCP Configuration{NC}")
    print(f"{DIM}   Add this to your ~/.cursor/mcp.json (or equivalent):{NC}\n")
    print(f"{GREEN}{json.dumps(config, indent=2)}{NC}")
    print()
    print(f"{BOLD}{GREEN}Setup complete!{NC} Restart your IDE to activate NexMem memory.")

    if backend_key in ("mongodb", "postgres", "redis"):
        print(f"\n{DIM}Tip: Need a local {backend_key}? Run:{NC}")
        print(f"  docker compose --profile {backend_key} up -d")
    print()
