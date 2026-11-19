---
description: Re-run the .agents setup script to sync skills, context, prompts, and MCP config
---

Run `~/.agents/setup` to re-sync all harness configuration. If it fails because
the TOML parser is unavailable, check whether Python 3.11+ is already
available and rerun setup with it. Do not install Python packages; report the
missing dependency if no suitable interpreter is available.

Report what was linked, updated, or pruned.
