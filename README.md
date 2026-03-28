# HiveMind MCP

**Shared Agent Memory for Teams** — a plug-and-play MCP memory server with pluggable database backends.

HiveMind gives AI coding agents (Cursor, Claude Desktop, etc.) a persistent knowledge graph that the whole team shares. Agents learn as they work — discovering services, architecture patterns, and conventions — then recall that knowledge instantly in future sessions.

## Features

- **Self or Team memory** — personal graph or shared team graph, switchable via env var
- **5 storage backends** — JSONL (default), SQLite, MongoDB, PostgreSQL, Redis
- **Atomic operations** — no race conditions when multiple team members write simultaneously
- **Strong consistency** — reads always return the latest state
- **Wire-compatible** — same JSONL format as `@modelcontextprotocol/server-memory` for import/export
- **Guided autonomous** — built-in instructions tell the agent what to save (and what not to)
- **Extensible** — add custom backends by implementing the `StorageAdapter` ABC

## Quick Start

### 1. Install

```bash
pip install hivemind-mcp
```

Or with a database backend:

```bash
pip install "hivemind-mcp[mongodb]"   # MongoDB
pip install "hivemind-mcp[postgres]"  # PostgreSQL
pip install "hivemind-mcp[redis]"     # Redis
pip install "hivemind-mcp[all]"       # All backends
```

### 2. Configure

Add to your `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "hivemind": {
      "command": "hivemind-mcp",
      "env": {
        "HIVEMIND_MODE": "self"
      }
    }
  }
}
```

### 3. Restart your IDE

That's it. The agent now has persistent memory.

## Interactive Setup

For a guided setup that generates the config for you:

```bash
hivemind-mcp init
```

Or run the install script:

```bash
bash scripts/install.sh
```

## Configuration Reference

All configuration is via environment variables (prefix: `HIVEMIND_`):

| Variable | Default | Description |
|---|---|---|
| `HIVEMIND_MODE` | `self` | `self` for personal memory, `team` for shared |
| `HIVEMIND_USER_NAME` | OS username | Your identity |
| `HIVEMIND_TEAM_NAME` | *(required for team)* | Team identifier |
| `HIVEMIND_BACKEND` | `jsonl` | `jsonl` / `sqlite` / `mongodb` / `postgres` / `redis` |
| `HIVEMIND_READ_ONLY` | `false` | Disable write tools |
| `HIVEMIND_INSTRUCTIONS` | *(built-in)* | Custom instructions file path or inline text |

### Backend-specific variables

| Variable | Default |
|---|---|
| `HIVEMIND_JSONL_PATH` | `~/.hivemind/memory.jsonl` |
| `HIVEMIND_SQLITE_PATH` | `~/.hivemind/memory.db` |
| `HIVEMIND_MONGODB_URI` | `mongodb://localhost:27017/hivemind` |
| `HIVEMIND_POSTGRES_URI` | `postgresql://localhost:5432/hivemind` |
| `HIVEMIND_REDIS_URL` | `redis://localhost:6379/0` |

## Team Setup

### Step 1: Provision a shared database

Pick a database your team can all reach. For a quick local setup:

```bash
docker compose --profile mongodb up -d
```

### Step 2: Share the config

Each team member adds this to their `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "hivemind": {
      "command": "hivemind-mcp",
      "env": {
        "HIVEMIND_MODE": "team",
        "HIVEMIND_TEAM_NAME": "platform-eng",
        "HIVEMIND_BACKEND": "mongodb",
        "HIVEMIND_MONGODB_URI": "mongodb://shared-host:27017/hivemind"
      }
    }
  }
}
```

### Step 3: Work normally

Agents will proactively read from and write to the shared knowledge graph. When Alice's agent discovers that `PaymentService` uses gRPC, Bob's agent will know it too — immediately, with no manual sync.

## How It Works

### Data Model

HiveMind stores a knowledge graph with two types of records:

**Entities** — things the agent knows about (services, repos, APIs, etc.):

```json
{"type":"entity","name":"PaymentAPI","entityType":"service","observations":["Uses gRPC","Handles billing"]}
```

**Relations** — connections between entities:

```json
{"type":"relation","from":"PaymentAPI","to":"AuthService","relationType":"depends_on"}
```

### Tools

The server exposes 11 MCP tools:

| Tool | Description |
|---|---|
| `read_graph` | Read the entire knowledge graph |
| `search_nodes` | Search entities by name, type, or observations |
| `open_nodes` | Get specific entities by name |
| `create_entities` | Create new entities |
| `create_relations` | Create relations between entities |
| `add_observations` | Add observations to existing entities |
| `delete_entities` | Delete entities and their relations |
| `delete_observations` | Remove specific observations |
| `delete_relations` | Remove specific relations |
| `get_memory_status` | Show current config, mode, and health |
| `import_jsonl` | Import from upstream server-memory format |

### Agent Behavior

The server includes built-in instructions that guide the agent:

- **Reads automatically** — searches memory at the start of relevant tasks
- **Writes proactively** — saves useful discoveries (services, patterns, decisions) without being asked
- **Skips noise** — doesn't save trivial or temporary information

You can customize this behavior with `HIVEMIND_INSTRUCTIONS`.

### Conflict Safety

Unlike file-based approaches that load → modify → overwrite (causing race conditions), HiveMind uses **atomic database operations**:

- `create_entities` → `INSERT ... ON CONFLICT DO NOTHING`
- `add_observations` → atomic array append
- `delete_entities` → atomic delete by name

Two team members writing simultaneously both succeed without overwriting each other.

## Storage Backends

### JSONL (default)

Zero dependencies. Stores one `.jsonl` file per namespace in `~/.hivemind/`. Uses file locking for safety. Best for self mode.

### SQLite

Zero extra dependencies (uses stdlib). Stores a single `.db` file with proper tables and indexes. Uses WAL mode and transactions. Good for lightweight local use.

### MongoDB

Install: `pip install "hivemind-mcp[mongodb]"`

Recommended for teams. Document model fits naturally. Uses `insertMany(ordered=false)` for idempotent creates, `$push` for atomic observation appends.

### PostgreSQL

Install: `pip install "hivemind-mcp[postgres]"`

Uses JSONB columns for observations. `INSERT ... ON CONFLICT DO NOTHING` for safe concurrent writes. Connection pooling via asyncpg.

### Redis

Install: `pip install "hivemind-mcp[redis]"`

Stores entities as hash fields, relations as set members. Fast reads. `HSETNX` for atomic creates.

### Custom Adapters

Implement the `StorageAdapter` ABC and register it:

```python
from hivemind_mcp.adapters import register_adapter
from hivemind_mcp.adapters.base import StorageAdapter

@register_adapter("dynamodb")
class DynamoDBAdapter(StorageAdapter):
    ...
```

## Importing Existing Data

If you have JSONL files from `@modelcontextprotocol/server-memory` or `harbor-memory-mcp`, use the `import_jsonl` tool:

```
"Import this data into memory: <paste JSONL content>"
```

Or programmatically, the agent can call `import_jsonl(jsonl_content="...")`.

## Docker

### Database backends

```bash
docker compose --profile mongodb up -d    # MongoDB on :27017
docker compose --profile postgres up -d   # PostgreSQL on :5432
docker compose --profile redis up -d      # Redis on :6379
```

### Running the server in Docker

```bash
docker build --target all -t hivemind-mcp .
docker run -e HIVEMIND_MODE=team -e HIVEMIND_BACKEND=mongodb \
  -e HIVEMIND_MONGODB_URI=mongodb://host:27017/hivemind hivemind-mcp
```

## Development

```bash
git clone https://github.com/arpanroy41/hivemind-mcp.git
cd hivemind-mcp
pip install -e ".[dev]"
pytest
```

## License

MIT
