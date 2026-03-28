# NexMem MCP

**Shared Agent Memory for Teams** — a plug-and-play MCP memory server with pluggable database backends.

NexMem gives AI coding agents (Cursor, Claude Desktop, etc.) a persistent knowledge graph that the whole team shares. Agents learn as they work — discovering services, architecture patterns, and conventions — then recall that knowledge instantly in future sessions.

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
pip install mcp-nexmem
```

Or with a database backend:

```bash
pip install "mcp-nexmem[mongodb]"   # MongoDB
pip install "mcp-nexmem[postgres]"  # PostgreSQL
pip install "mcp-nexmem[redis]"     # Redis
pip install "mcp-nexmem[all]"       # All backends
```

### 2. Configure

Add to your `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "nexmem": {
      "command": "nexmem-mcp",
      "env": {
        "NEXMEM_MODE": "self"
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
nexmem-mcp init
```

Or run the install script:

```bash
bash scripts/install.sh
```

## Configuration Reference

All configuration is via environment variables (prefix: `NEXMEM_`):

| Variable | Default | Description |
|---|---|---|
| `NEXMEM_MODE` | `self` | `self` for personal memory, `team` for shared |
| `NEXMEM_USER_NAME` | OS username | Your identity |
| `NEXMEM_TEAM_NAME` | *(required for team)* | Team identifier |
| `NEXMEM_BACKEND` | `jsonl` | `jsonl` / `sqlite` / `mongodb` / `postgres` / `redis` |
| `NEXMEM_READ_ONLY` | `false` | Disable write tools |
| `NEXMEM_INSTRUCTIONS` | *(built-in)* | Custom instructions file path or inline text |

### Backend-specific variables

| Variable | Default |
|---|---|
| `NEXMEM_JSONL_PATH` | `~/.nexmem/memory.jsonl` |
| `NEXMEM_SQLITE_PATH` | `~/.nexmem/memory.db` |
| `NEXMEM_MONGODB_URI` | `mongodb://localhost:27017/nexmem` |
| `NEXMEM_POSTGRES_URI` | `postgresql://localhost:5432/nexmem` |
| `NEXMEM_REDIS_URL` | `redis://localhost:6379/0` |

## Namespaces: How Data Isolation Works

`NEXMEM_TEAM_NAME` and `NEXMEM_USER_NAME` control which **namespace** your data is stored under. Namespaces provide complete data isolation within the same database.

| Config | Namespace | Who sees the data |
|---|---|---|
| `MODE=self, USER_NAME=alice` | `self:alice` | Only Alice |
| `MODE=self, USER_NAME=bob` | `self:bob` | Only Bob |
| `MODE=team, TEAM_NAME=platform-eng` | `team:platform-eng` | Everyone with same team name |
| `MODE=team, TEAM_NAME=frontend` | `team:frontend` | Different team, separate graph |

Every entity and relation is tagged with the namespace in the database:

```json
{ "namespace": "team:platform-eng", "name": "AuthService", "entity_type": "service", ... }
```

- **In team mode**, `NEXMEM_TEAM_NAME` determines the namespace. All team members who set the same team name share one knowledge graph.
- **In self mode**, `NEXMEM_USER_NAME` determines the namespace. Each user has a private graph.
- Multiple teams can share the same database — their data is isolated by namespace.
- Switching modes doesn't delete data. Both `self:alice` and `team:platform-eng` can coexist.

## Team Setup

### Step 1: Provision a shared database

Pick a database your team can all reach.

**Option A: MongoDB Atlas (recommended, free tier available)**

1. Sign up at [mongodb.com/atlas](https://www.mongodb.com/atlas) and create a Free M0 cluster
2. Create a database user and set Network Access to `0.0.0.0/0` (allow all IPs)
3. Click Connect > Drivers > copy the connection string
4. Use it as `NEXMEM_MONGODB_URI` (append `/nexmem` as the database name)

**Option B: Local Docker (for testing)**

```bash
docker compose --profile mongodb up -d
```

### Step 2: Share the config

Each team member adds this to their `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "nexmem": {
      "command": "nexmem-mcp",
      "env": {
        "NEXMEM_MODE": "team",
        "NEXMEM_TEAM_NAME": "platform-eng",
        "NEXMEM_BACKEND": "mongodb",
        "NEXMEM_MONGODB_URI": "mongodb://shared-host:27017/nexmem"
      }
    }
  }
}
```

### Step 3: Work normally

Agents will proactively read from and write to the shared knowledge graph. When Alice's agent discovers that `PaymentService` uses gRPC, Bob's agent will know it too — immediately, with no manual sync.

## How It Works

### Data Model

NexMem stores a knowledge graph with two types of records:

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

You can customize this behavior with `NEXMEM_INSTRUCTIONS`.

### Conflict Safety

Unlike file-based approaches that load → modify → overwrite (causing race conditions), NexMem uses **atomic database operations**:

- `create_entities` → `INSERT ... ON CONFLICT DO NOTHING`
- `add_observations` → atomic array append
- `delete_entities` → atomic delete by name

Two team members writing simultaneously both succeed without overwriting each other.

## Storage Backends

### JSONL (default)

Zero dependencies. Stores one `.jsonl` file per namespace in `~/.nexmem/`. Uses file locking for safety. Best for self mode.

### SQLite

Zero extra dependencies (uses stdlib). Stores a single `.db` file with proper tables and indexes. Uses WAL mode and transactions. Good for lightweight local use.

### MongoDB

Install: `pip install "mcp-nexmem[mongodb]"`

Recommended for teams. Document model fits naturally. Uses `insertMany(ordered=false)` for idempotent creates, `$push` for atomic observation appends.

### PostgreSQL

Install: `pip install "mcp-nexmem[postgres]"`

Uses JSONB columns for observations. `INSERT ... ON CONFLICT DO NOTHING` for safe concurrent writes. Connection pooling via asyncpg.

### Redis

Install: `pip install "mcp-nexmem[redis]"`

Stores entities as hash fields, relations as set members. Fast reads. `HSETNX` for atomic creates.

### Custom Adapters

Implement the `StorageAdapter` ABC and register it:

```python
from nexmem_mcp.adapters import register_adapter
from nexmem_mcp.adapters.base import StorageAdapter

@register_adapter("dynamodb")
class DynamoDBAdapter(StorageAdapter):
    ...
```

## Importing Existing Data

If you have JSONL files from `@modelcontextprotocol/server-memory` or other MCP memory servers, use the `import_jsonl` tool:

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
docker build --target all -t nexmem-mcp .
docker run -e NEXMEM_MODE=team -e NEXMEM_BACKEND=mongodb \
  -e NEXMEM_MONGODB_URI=mongodb://host:27017/nexmem nexmem-mcp
```

## Development

```bash
git clone https://github.com/arpanroy41/nexmem-mcp.git
cd nexmem-mcp
pip install -e ".[dev]"
pytest
```

## License

MIT
