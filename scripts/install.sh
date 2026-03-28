#!/usr/bin/env bash
set -euo pipefail

# ── NexMem MCP Interactive Installer ──────────────────────────────────
#
# Generates the mcp.json snippet for Cursor, Claude Desktop, or other
# MCP clients. Run: bash scripts/install.sh

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo -e "${BOLD}${CYAN}NexMem MCP — Interactive Setup${NC}\n"

# ── Step 1: Memory mode ─────────────────────────────────────────────────
echo -e "${BOLD}1. Memory Mode${NC}"
echo "   [1] Self  — personal memory, just for you"
echo "   [2] Team  — shared memory across your team"
read -rp "   Choose (1/2) [1]: " mode_choice
mode_choice=${mode_choice:-1}

if [[ "$mode_choice" == "2" ]]; then
    NEXMEM_MODE="team"
    read -rp "   Team name: " NEXMEM_TEAM_NAME
    if [[ -z "$NEXMEM_TEAM_NAME" ]]; then
        echo "Error: Team name is required for team mode." >&2
        exit 1
    fi
else
    NEXMEM_MODE="self"
    NEXMEM_TEAM_NAME=""
fi

NEXMEM_USER_NAME="${USER:-$(whoami)}"
echo ""

# ── Step 2: Storage backend ─────────────────────────────────────────────
echo -e "${BOLD}2. Storage Backend${NC}"
echo "   [1] JSONL files   ${DIM}(default, zero dependencies)${NC}"
echo "   [2] SQLite        ${DIM}(lightweight local database)${NC}"
echo "   [3] MongoDB       ${DIM}(recommended for teams)${NC}"
echo "   [4] PostgreSQL    ${DIM}(JSONB storage)${NC}"
echo "   [5] Redis         ${DIM}(fast, JSON module)${NC}"
read -rp "   Choose (1-5) [1]: " backend_choice
backend_choice=${backend_choice:-1}

case "$backend_choice" in
    1) NEXMEM_BACKEND="jsonl"; EXTRA_ENV="" ;;
    2) NEXMEM_BACKEND="sqlite"; EXTRA_ENV="" ;;
    3)
        NEXMEM_BACKEND="mongodb"
        read -rp "   MongoDB URI [mongodb://localhost:27017/nexmem]: " uri
        EXTRA_ENV="\"NEXMEM_MONGODB_URI\": \"${uri:-mongodb://localhost:27017/nexmem}\""
        ;;
    4)
        NEXMEM_BACKEND="postgres"
        read -rp "   PostgreSQL URI [postgresql://localhost:5432/nexmem]: " uri
        EXTRA_ENV="\"NEXMEM_POSTGRES_URI\": \"${uri:-postgresql://localhost:5432/nexmem}\""
        ;;
    5)
        NEXMEM_BACKEND="redis"
        read -rp "   Redis URL [redis://localhost:6379/0]: " uri
        EXTRA_ENV="\"NEXMEM_REDIS_URL\": \"${uri:-redis://localhost:6379/0}\""
        ;;
    *)
        echo "Invalid choice." >&2
        exit 1
        ;;
esac
echo ""

# ── Step 3: Install package ─────────────────────────────────────────────
echo -e "${BOLD}3. Installing mcp-nexmem...${NC}"
if [[ "$NEXMEM_BACKEND" == "jsonl" || "$NEXMEM_BACKEND" == "sqlite" ]]; then
    pip install mcp-nexmem 2>/dev/null || echo -e "${YELLOW}   (Install manually: pip install mcp-nexmem)${NC}"
else
    pip install "mcp-nexmem[$NEXMEM_BACKEND]" 2>/dev/null || echo -e "${YELLOW}   (Install manually: pip install 'mcp-nexmem[$NEXMEM_BACKEND]')${NC}"
fi
echo ""

# ── Step 4: Generate config ─────────────────────────────────────────────
echo -e "${BOLD}4. MCP Configuration${NC}"
echo -e "${DIM}   Add this to your ~/.cursor/mcp.json (or equivalent):${NC}\n"

ENV_BLOCK="\"NEXMEM_MODE\": \"$NEXMEM_MODE\",
        \"NEXMEM_BACKEND\": \"$NEXMEM_BACKEND\",
        \"NEXMEM_USER_NAME\": \"$NEXMEM_USER_NAME\""

if [[ -n "$NEXMEM_TEAM_NAME" ]]; then
    ENV_BLOCK="$ENV_BLOCK,
        \"NEXMEM_TEAM_NAME\": \"$NEXMEM_TEAM_NAME\""
fi

if [[ -n "$EXTRA_ENV" ]]; then
    ENV_BLOCK="$ENV_BLOCK,
        $EXTRA_ENV"
fi

echo -e "${GREEN}"
cat <<EOF
{
  "mcpServers": {
    "nexmem": {
      "command": "nexmem-mcp",
      "env": {
        $ENV_BLOCK
      }
    }
  }
}
EOF
echo -e "${NC}"

echo -e "${BOLD}${GREEN}✓ Setup complete!${NC} Restart your IDE to activate NexMem memory."

# ── Docker hint for team backends ────────────────────────────────────────
if [[ "$NEXMEM_BACKEND" == "mongodb" || "$NEXMEM_BACKEND" == "postgres" || "$NEXMEM_BACKEND" == "redis" ]]; then
    echo -e "\n${DIM}Tip: Need a local ${NEXMEM_BACKEND}? Run:${NC}"
    echo -e "  docker compose --profile ${NEXMEM_BACKEND} up -d"
fi
