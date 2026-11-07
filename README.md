# .agents

Unified configuration for AI coding agents. One repo to manage context, skills, and MCP servers across [Claude Code](https://code.claude.com/docs), [Kiro](https://kiro.dev/cli/), and [OpenCode](https://github.com/opencode-ai/opencode).

Fork this repo, commit your own configuration, and run `setup` to wire everything into your local agent harnesses.

⚠️ **Your fork will contain personal context, conventions, and potentially sensitive configuration. Consider making it a private repository.**

## Installation

```bash
# Fork this repo on GitHub, then clone your fork
git clone git@github.com:YOUR_USER/.agents.git ~/.agents

# Run setup (installs symlinks and merges MCP config)
~/.agents/setup
```

`setup` will:
1. Create a `~/.agents` symlink if you cloned elsewhere
2. Symlink skills into each harness's skills directory
3. Symlink context files into each harness's rules/steering directory
4. Symlink prompts as slash commands into each harness's commands directory
5. Merge MCP server config (with secrets) into each harness's native format

Re-run `setup` after any change to this repo.

### Prerequisites

macOS or Linux. Windows is not supported.

Python 3 and at least one of these agents installed:
- [Claude Code](https://code.claude.com/docs) (`claude`)
- [Kiro CLI](https://kiro.dev/cli/) (`kiro-cli`)
- [OpenCode](https://github.com/opencode-ai/opencode) (`opencode`)
- [Antigravity](https://antigravity.google/) (`agy`) — Google Antigravity CLI, successor to Gemini CLI
- [Codex](https://github.com/openai/codex) (`codex`) — OpenAI Codex CLI

On Python < 3.11, Codex support requires the TOML parser backport:

```bash
pip install tomli
```

(Python 3.11+ has `tomllib` in the standard library and needs nothing extra.)

`setup` auto-detects which are installed and skips the rest. You can also target one:

```bash
~/.agents/setup claude
~/.agents/setup kiro
~/.agents/setup opencode
~/.agents/setup antigravity
~/.agents/setup codex
```

### The `--yolo` flag

```bash
~/.agents/setup --yolo
```

This persistently disables permission prompts in all harnesses (auto-approves tool use). It requires double confirmation. Use at your own risk.

For Codex, `~/.agents/setup --yolo codex` sets `approval_policy = "never"`
and `sandbox_mode = "danger-full-access"`, and sets each configured MCP
server's default and existing per-tool approval modes to `"approve"`,
including servers provided by configured plugins.
Ordinary setup runs preserve these MCP approval settings. Restart Codex
after applying the settings. Managed policies can still restrict access.

Run the Codex setup regression tests with `python3 -m unittest discover -s tests -v`.
They use temporary homes and placeholder credentials.

## Structure

```
~/.agents/
├── setup               — wires everything into each harness
├── context/            — shared context loaded every session
│   └── CONTEXT.md      — standing directives, conventions, project notes
├── skills/             — reusable skill definitions (SKILL.md per directory)
│   └── weather/        — example skill
├── prompts/            — slash command prompts distributed to each harness
│   └── *.md            — prompt files (linked as *.prompt.md for Kiro)
├── mcp/                — MCP server definitions and secrets
│   ├── servers.json    — canonical server definitions (committed)
│   ├── secrets.json    — API keys for servers (gitignored)
│   └── *.servers.json  — per-harness overrides
├── config/             — harness-specific config (--yolo settings, etc.)
└── harnesses/          — auto-generated symlinks to ~/.claude, ~/.kiro, ~/.config/opencode
```

## Usage

### Adding context

Drop `.md` files in `context/`. These are loaded into every agent session as standing instructions — use them for coding conventions, project architecture, team preferences, etc.

```bash
echo "Always use TypeScript strict mode." > ~/.agents/context/typescript.md
~/.agents/setup
```

### Adding skills

Create a directory under `skills/` with a `SKILL.md` file:

```bash
mkdir ~/.agents/skills/deploy
cat > ~/.agents/skills/deploy/SKILL.md << 'EOF'
---
name: deploy
description: Deploy services to production via CI/CD pipelines.
---

# Deploy

## How to Use
...
EOF

~/.agents/setup
```

Skills are agent-readable instructions that teach the agent how to perform specific tasks.

### Adding prompts

Drop `.md` files in `prompts/`. These become slash commands in each harness (e.g., `opsx-explore.md` → `/opsx-explore`).

Prompts use Kiro's native format — markdown with a `description` frontmatter field:

```markdown
---
description: Enter explore mode - think through ideas and investigate problems
---

Your prompt instructions here...
```

Files named `*.prompt.md` are also accepted (legacy Kiro convention). `setup` adapts the file name per harness:
- **Kiro**: plain `.md` files are linked as `.prompt.md`; `.prompt.md` files keep their name
- **Claude**: linked as `.md` (stripping `.prompt.md` to `.md` if needed)
- **OpenCode**: linked as `.md` (stripping `.prompt.md` to `.md` if needed)

### Adding MCP servers

Add server definitions to `mcp/servers.json`:

```json
{
  "my-server": {
    "command": "npx",
    "args": ["my-mcp-server@latest"],
    "env": {}
  }
}
```

If the server needs secrets, create `mcp/secrets.json` (gitignored):

```json
{
  "my-server": {
    "env": {
      "API_KEY": "sk-..."
    }
  }
}
```

Then run `~/.agents/setup` to merge into all harnesses.

### Adding MCP tool aliases (kiro only)

kiro flattens all MCP tool names into a single namespace, so two servers exposing a tool with the same name will collide. kiro supports `toolAliases` in its agent config to remap `server::tool` to a distinct name.

Declare aliases in `mcp/kiro.servers.json` under a top-level `@aliases` key:

```json
{
  "@aliases": {
    "corsair::crews": "corsair_crews",
    "corsair::launch": "corsair_launch",
    "corsair::dispatch": "corsair_dispatch"
  }
}
```

`setup` merges these into `toolAliases` in `~/.kiro/agents/general.json` on every run. The merge is non-destructive — aliases you declare overwrite matching keys, but any `toolAliases` entries not present in `kiro.servers.json` are left untouched.

This is kiro-specific. Claude Code, Codex, Antigravity, and OpenCode all prefix tool names with the server name natively and do not need aliases.

> **Note on stale aliases:** `setup` never removes aliases. If you delete an entry from `kiro.servers.json`, you must also manually remove it from `~/.kiro/agents/general.json`.

Then run `~/.agents/setup` to merge into all harnesses.

## MCP configuration

Server config is layered and merged in order:

1. `mcp/servers.json` — base definitions (committed)
2. `mcp/<harness>.servers.json` — per-harness overrides (committed)
3. `mcp/secrets.json` — secrets for all harnesses (gitignored)
4. `mcp/<harness>.secrets.json` — per-harness secrets (gitignored)

Later layers deep-merge into earlier ones, so overrides only need the fields they change.

### Enabling/disabling servers

New servers default to **disabled**. Each harness handles this differently:

| Harness | How to enable | State stored in |
|---------|---------------|-----------------|
| Claude | `/mcp` dialog in-session | `~/.claude.json` (per-workspace) |
| Kiro | Edit `~/.kiro/settings/mcp.json`, remove `disabled` key | `~/.kiro/settings/mcp.json` |
| OpenCode | Set `"disabled": false` in `mcp/opencode.servers.json`, re-run setup | `~/.config/opencode/opencode.json` |
| Antigravity | Remove `disabled` key from `~/.gemini/config/mcp_config.json` | `~/.gemini/config/mcp_config.json` |
| Codex | Set `enabled = true` under the server's `[mcp_servers.<name>]` entry in `~/.codex/config.toml`, re-run setup | `~/.codex/config.toml` |

`setup` preserves existing enable/disable state for Claude, Kiro, Antigravity, and Codex. For OpenCode, state is derived from config on every run.

## How it maps to each harness

| What | Claude | Kiro | OpenCode | Antigravity | Codex |
|------|--------|------|----------|-------------|-------|
| Context | `~/.claude/rules/*.md` | `~/.kiro/steering/*.md` | `~/.config/opencode/AGENTS.md` (generated; context files concatenated) | `~/.gemini/config/AGENTS.md` (single file; CONTEXT.md linked) | `~/.codex/AGENTS.md` (single file; CONTEXT.md linked) |
| Skills | `~/.claude/skills/*/` | `~/.kiro/skills/*/` | `config.skills` in `opencode.json` → `.agents/skills/` directory | `~/.gemini/config/skills/*/` | `skills.config` entries in `~/.codex/config.toml` (resolved paths) |
| Prompts | `~/.claude/commands/*.md` | `~/.kiro/prompts/*.prompt.md` | `~/.config/opencode/commands/*.md` | — (not supported) | `~/.codex/commands/*.md` |
| MCP | `~/.claude.json` → `mcpServers` | `~/.kiro/settings/mcp.json` → `mcpServers` | `~/.config/opencode/opencode.json` → `mcp.servers` | `~/.gemini/config/mcp_config.json` → `mcpServers` | `~/.codex/config.toml` → `mcp_servers` |

## Roadmap

Potential harness support:

- [ ] Other

## License

MIT
