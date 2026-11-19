---
description: Re-run the .agents setup script to sync skills, context, prompts, and MCP config
---

Run the .agents setup script to re-sync all harness configuration. Prefer a
uv-managed Python 3.11+ when `uv` is available, so the script can use the
standard-library `tomllib` without requiring the `tomli` backport.

```bash
if command -v uv >/dev/null 2>&1; then
  uv run --no-project --python '>=3.11' python ~/.agents/setup
else
  ~/.agents/setup
fi
```

Report what was linked, updated, or pruned.
