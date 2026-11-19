---
description: Re-run the .agents setup script to sync skills, context, prompts, and MCP config
---

Run the .agents setup script to re-sync all harness configuration. Prefer an
already-installed Python 3.11+ from any source. Check `python3` and versioned
`python3.X` executables available on `PATH`; choose the newest compatible
interpreter and invoke it directly so the script's shebang cannot select a
different Python.

```bash
python3.14 ~/.agents/setup  # replace with the selected Python 3.11+ interpreter
```

If no suitable Python is installed and `uv` is available, let uv provide one:

```bash
  uv run --no-project --python '>=3.11' python ~/.agents/setup
```

If neither option is available, run `~/.agents/setup` with the default Python.
If it fails because `tomli` is missing, report that Python below 3.11 needs the
backport and stop; do not install it automatically.

Report what was linked, updated, or pruned.
