# Codex MCP Setup

This workspace adopts a three-tier MCP stack for Codex:

- `context7`: enabled now
- `github`: configured now, requires a PAT in `GITHUB_PERSONAL_ACCESS_TOKEN`
- `chrome-devtools`: configured but disabled by default until Node.js is installed

## Quick start

1. Fill the env template at `docs/codex-mcp.env.example`.
2. Copy it to `.env.codex-mcp` and set `GITHUB_PERSONAL_ACCESS_TOKEN`.
3. Run `./scripts/bootstrap_codex_mcp.sh`.
4. Install Node.js later, then turn on `chrome-devtools`.

## Current global config

The active Codex user config lives at `~/.codex/config.toml` and currently contains:

```toml
[mcp_servers.context7]
url = "https://mcp.context7.com/mcp"

[mcp_servers.github]
url = "https://api.githubcopilot.com/mcp/"
bearer_token_env_var = "GITHUB_PERSONAL_ACCESS_TOKEN"

[mcp_servers.chrome-devtools]
enabled = false
command = "npx"
args = ["-y", "chrome-devtools-mcp@latest", "--no-usage-statistics"]
startup_timeout_ms = 20000
```

## What is usable now

- `context7` is ready immediately.
- `github` will start working after you export a PAT.
- `chrome-devtools` stays off until Node.js and `npx` are available.

## One-time setup

### 1. Enable GitHub MCP

Export a GitHub PAT before launching Codex:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=your_pat_here
```

If you want it to persist across shell sessions, add that export to your shell profile.

You can start from the local template:

```bash
cp docs/codex-mcp.env.example .env.codex-mcp
```

Then use the bootstrap script:

```bash
./scripts/bootstrap_codex_mcp.sh
```

### 2. Enable Chrome DevTools MCP

Install Node.js 20.19+ or a current LTS with `npx`, then flip the server on in `~/.codex/config.toml`:

```bash
python3 scripts/enable_chrome_devtools_mcp.py
```

## Verification

Use the Codex CLI to verify the configured servers:

```bash
/Applications/Codex.app/Contents/Resources/codex mcp list
```

Expected shape:

- `context7`: `enabled`
- `github`: `enabled`
- `chrome-devtools`: `disabled`

You can also run the local readiness check:

```bash
python3 scripts/check_codex_mcp.py
```

Or run the full local bootstrap:

```bash
./scripts/bootstrap_codex_mcp.sh
```
