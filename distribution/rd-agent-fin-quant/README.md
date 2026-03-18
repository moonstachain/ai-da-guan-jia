# RD-Agent Fin Quant Remote PoC Bundle

This bundle packages a reproducible, research-only deployment path for running
Microsoft RD-Agent on an Ubuntu x86_64 host for the `fin_quant` scenario.

It is intentionally scoped to:

- factor and model research
- backtest-style experimentation
- UI and environment verification

It is intentionally out of scope for v1:

- broker credentials
- live trading
- order routing
- portfolio risk controls
- production monitoring

## Why this bundle exists

The official RD-Agent docs recommend Docker-backed execution for `fin_quant`,
and the project notes that Apple Silicon is not the recommended path for the
Qlib workflow. This bundle makes the safer path the default:

- remote `Ubuntu 22.04/24.04`
- `x86_64`
- Docker enabled
- external LLM API backend

Official sources:

- https://github.com/microsoft/RD-Agent/
- https://rdagent.readthedocs.io/en/latest/install_and_configure.html
- https://rdagent.readthedocs.io/en/latest/quick_start.html
- https://github.com/microsoft/RD-Agent/blob/main/.env.example

## Included files

- `rdagent.env.example`
  - starter `.env` template pinned to `SCEN=fin_quant`
  - uses the official `rdagent.app.qlib_rd_loop_conf` settings module
  - defaults the execution environment to Docker for model-costeer flows
- `remote/bootstrap_rd_agent_fin_quant.sh`
  - runs on the Ubuntu host
  - installs system packages, Docker, Miniforge, the RD-Agent repo, and the
    Python environment
  - best-effort prepares Qlib CN data in the standard user path
  - prefers `python -m qlib.cli.data` and falls back to the community
    `qlib_bin.tar.gz` snapshot when the official endpoint is unavailable
- `remote/verify_rd_agent_fin_quant.sh`
  - runs on the Ubuntu host
  - checks OS/arch, Docker, Conda env, imports, `.env`, and prepared data
  - optionally runs UI, health-check, and smoke commands

Top-level launchers in this repo:

- `scripts/deploy_rdagent_fin_quant_remote.sh`
- `scripts/verify_rdagent_fin_quant_remote.sh`
- `scripts/deploy_black_satellite_rdagent.sh`

Black-satellite control-plane flow:

- `python3 work/ai-da-guan-jia/scripts/ai_da_guan_jia.py inspect-rdagent-fin-quant --alias 黑色`
- `python3 work/ai-da-guan-jia/scripts/ai_da_guan_jia.py bind-rdagent-runtime --alias 黑色 --runtime-host <ubuntu-host> --runtime-user ubuntu`
- `scripts/deploy_black_satellite_rdagent.sh --env-file /tmp/rdagent-fin-quant.env`

## Quick start

1. Create a private env file from the template and fill in your external model
   provider credentials.

```bash
cp distribution/rd-agent-fin-quant/rdagent.env.example /tmp/rdagent-fin-quant.env
```

2. Bootstrap the remote Ubuntu host.

```bash
RD_AGENT_HOST=your-ubuntu-host-or-ip
RD_AGENT_USER=ubuntu

scripts/deploy_rdagent_fin_quant_remote.sh \
  --host "$RD_AGENT_HOST" \
  --user "$RD_AGENT_USER" \
  --workspace-root '$HOME/rd-agent-fin-quant-poc' \
  --env-file /tmp/rdagent-fin-quant.env
```

3. Run remote verification after the first install.

```bash
scripts/verify_rdagent_fin_quant_remote.sh \
  --host "$RD_AGENT_HOST" \
  --user "$RD_AGENT_USER" \
  --workspace-root '$HOME/rd-agent-fin-quant-poc'
```

4. Once your `.env` is fully configured and your preferred RD-Agent CLI command
   is known for the checked-out version, add stricter checks:

```bash
scripts/verify_rdagent_fin_quant_remote.sh \
  --host "$RD_AGENT_HOST" \
  --user "$RD_AGENT_USER" \
  --workspace-root '$HOME/rd-agent-fin-quant-poc' \
  --health-command 'rdagent health_check' \
  --ui-command 'rdagent ui --host 127.0.0.1 --port 19899' \
  --ui-check-mode strict
```

Troubleshooting:

- Do not paste angle-bracket placeholders like `<ubuntu-host>` into `zsh`.
  The shell interprets them as redirection syntax before the script runs.
- Use real values or shell variables like `"$RD_AGENT_HOST"` instead.
- If `黑色卫星` itself is not `Ubuntu x86_64`, treat it as the control plane and
  bind a dedicated Linux runtime first; the `deploy_black_satellite_rdagent.sh`
  wrapper reuses that binding instead of trying to force `fin_quant` onto macOS.
- For remote path arguments like `--workspace-root`, keep `$HOME` inside single
  quotes so your local shell does not expand it before the value reaches the
  remote Ubuntu host.

## Remote layout

By default, the deployment script builds this layout on the remote host:

```text
$HOME/rd-agent-fin-quant-poc/
  RD-Agent/
    .env
    .env.example
  artifacts/
  logs/
  state/
```

Qlib CN data is prepared at:

```text
$HOME/.qlib/qlib_data/cn_data
```

## Notes

- The bundle leaves `.env` secrets out of the repo.
- The UI and smoke commands are override-able because RD-Agent command surfaces
  may change across versions.
- The deploy script is idempotent enough for repeated bring-up on the same
  research host.
- The verify script defaults to safe checks first and only runs optional checks
  when you explicitly provide the command surface you want to validate.
- Recent `pyqlib` versions expose Qlib data download via `python -m qlib.cli.data`.
  If the official data endpoint is temporarily disabled, the bootstrap script
  falls back to the community snapshot published at
  `https://github.com/chenditc/investment_data/releases/latest/download/qlib_bin.tar.gz`.
