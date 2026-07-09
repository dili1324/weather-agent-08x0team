# weather-agent-08x0team

weather-agent-08x0team is a small Python 3.12 application that sends the current weather in Hanoi to Telegram. The current priority is an MVP proof of concept: run locally on macOS, pay through a secondary/test Tempo Wallet, and confirm Telegram receives the weather report.

The original production path is:

GitHub Actions -> Python app -> Tempo CLI `tempo request` -> OpenWeather MPP -> optional OpenAI MPP summary -> Telegram Bot API.

The current local MVP v2 path is:

Python app -> Node `mppx` helper -> OpenWeather MPP -> Telegram Bot API.

No private key, seed phrase, wallet secret, Telegram token, or paid API key is committed to this repository.

## Current Implementation Status

Implemented:

- GitHub Actions scheduler at `50 23 * * *` UTC, which is 06:50 in Asia/Ho_Chi_Minh.
- Python 3.12 application under `src/weather_agent`.
- OpenWeather MPP integration through `https://openweather.mpp.paywithlocus.com/openweather`.
- Local OpenWeather MPP payment mode through `node_mppx` using `mppx` + `accounts/cli`.
- Optional GPT summary through OpenAI MPP at `https://openai.mpp.tempo.xyz/v1/chat/completions`.
- Telegram Bot notification.
- Unit tests for config, formatting, and weather client flow.
- Security defaults that read secrets only from environment variables or GitHub Secrets.

Known blocker:

- Tempo documentation confirms `tempo wallet login`, `tempo wallet login --no-browser`, access keys, `tempo request`, and `--max-spend`. It does not document a repository-safe, non-interactive GitHub Actions credential bootstrap flow. The scheduled job therefore requires you to provision a valid scoped Tempo Wallet access key/session on the GitHub runner by an officially supported method before it can spend automatically. The code intentionally does not ask for, store, or reconstruct a private key or seed phrase.

## Official References Used

- Tempo Wallet CLI: `tempo wallet login`, `tempo wallet whoami`, access keys, service discovery, and `tempo request`.
- MPP service catalog: OpenWeather and OpenAI service URLs, payment method `tempo`, and endpoint list.
- Locus OpenWeather MPP docs: request fields for `geocode` and `current-weather`.
- OpenWeather docs: weather data semantics.

## Repository Structure

```text
.github/workflows/
  ci.yml
  weather-agent.yml
docs/
src/weather_agent/
tests/
.env.example
.gitignore
README.md
requirements.txt
requirements-lock.txt
```

## Sharing a Clean ZIP

Do not zip or share local runtime folders and secrets such as `.venv/`, `node_modules/`, `node_mppx/node_modules/`, `.git/`, or `.env`.

Create a clean archive with:

```bash
scripts/make_clean_zip.sh
```

Or run the equivalent command manually:

```bash
zip -r weather-agent-08x0team-clean.zip . -x ".git/*" ".venv/*" "node_modules/*" "node_mppx/node_modules/*" "__MACOSX/*" "*/__MACOSX/*" "*.egg-info/*" "*/*.egg-info/*" "*.DS_Store" ".env"
```

## Configuration

Required secrets:

- `TELEGRAM_BOT_TOKEN`: token for `@weatheagent_bot`.
- `TELEGRAM_CHAT_ID`: destination chat/channel/user id.

Runtime variables:

- `TEMPO_BIN`: defaults to `tempo`.
- `MPP_MAX_SPEND_USD`: defaults to `0.05`.
- `WEATHER_CITY_QUERY`: defaults to `Hanoi,VN`.
- `WEATHER_UNITS`: defaults to `metric`.
- `WEATHER_LANG`: defaults to `vi`.
- `WEATHER_PAYMENT_MODE`: `cli` or `mppx`; defaults to `cli`.
- `MPPX_HELPER_DIR`: defaults to `node_mppx` under the repository root.
- `MPPX_COMMAND_TIMEOUT_SECONDS`: defaults to `120`.
- `ENABLE_GPT_SUMMARY`: defaults to `false`.
- `GPT_MODEL`: defaults to `gpt-4o`.

Copy `.env.example` locally and fill only your local environment. Do not commit `.env`.

## MVP Local Run

For the fastest proof of concept on a Mac mini/macOS, follow [docs/mvp-local-run.md](docs/mvp-local-run.md).

Short version:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-build-isolation -e .
cp .env.example .env
```

If you want to run commands as `python3 ...`, activate the virtualenv first:

```bash
source .venv/bin/activate
```

Fill `.env`, then load it:

```bash
set -a
source .env
set +a
```

Install and connect Tempo Wallet:

```bash
curl -fsSL https://tempo.xyz/install | bash
"$HOME/.tempo/bin/tempo" wallet login
"$HOME/.tempo/bin/tempo" wallet --format json whoami
```

Fund the secondary/test wallet with a small amount, such as 1-5 USD, if needed:

```bash
"$HOME/.tempo/bin/tempo" wallet fund
```

Run debug checks:

```bash
export TEMPO_BIN="$HOME/.tempo/bin/tempo"
.venv/bin/python scripts/debug_checks.py tempo
.venv/bin/python scripts/debug_checks.py telegram
.venv/bin/python scripts/debug_checks.py weather
```

With the virtualenv activated, the equivalent form is:

```bash
python3 scripts/debug_checks.py telegram
```

Run the agent:

```bash
export ENABLE_GPT_SUMMARY=false
export MPP_MAX_SPEND_USD=0.05
.venv/bin/python -m weather_agent
```

Local MVP v2 with mppx:

```bash
cd node_mppx
npm install
npm run connect
cd ..
export WEATHER_PAYMENT_MODE=mppx
export ENABLE_GPT_SUMMARY=false
.venv/bin/python -m weather_agent
```

If `tempo wallet --format json whoami` does not show "ready": true, `tempo request` is not ready to pay MPP services. See [docs/mvp-local-run.md](docs/mvp-local-run.md) for troubleshooting.

## Logging

The agent logs each production step with timing in milliseconds:

- Tempo Wallet readiness check.
- OpenWeather MPP geocode and current weather calls.
- Optional GPT summary through OpenAI MPP.
- Telegram notification send.
- Total runtime.

Telegram tokens are never logged, and Telegram chat ids are masked in logs.

## GitHub Actions Deployment

Production-grade non-interactive Tempo Wallet bootstrap remains blocked by missing official documentation.

Manual mppx experiment:

This repository includes `.github/workflows/weather-agent-mppx-experiment.yml`. It is manual-only (`workflow_dispatch`) and has no schedule. It restores the `accounts/cli` state from `TEMPO_ACCOUNTS_CLI_STORE_B64`, runs `npm run weather:twice`, then runs the Python app with `WEATHER_PAYMENT_MODE=mppx` and GPT disabled.

Required experiment secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TEMPO_ACCOUNTS_CLI_STORE_B64`

Create the store secret only from a secondary/test wallet with a small balance, short Access Key expiry, and low daily limit. See [docs/github-actions-mppx-research.md](docs/github-actions-mppx-research.md).

For an MVP-only experiment after local success, see [docs/github-actions-credential-experiment.md](docs/github-actions-credential-experiment.md). That document is intentionally marked experimental and should only be used with a secondary/test wallet and a small balance.

For local automated payment using Tempo's CLI-managed Access Key first, see [docs/access-key-local-run.md](docs/access-key-local-run.md). This stays local and does not add any Tempo credential to GitHub.

1. Add GitHub Secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
2. Add optional GitHub Variables:
   - `MPP_MAX_SPEND_USD`
   - `ENABLE_GPT_SUMMARY`
   - `GPT_MODEL`
3. Ensure the runner has an officially supported Tempo Wallet credential/session with scoped spending limits.
4. Use the `Weather Agent` workflow manually once with `workflow_dispatch`.
5. After verification, the scheduled workflow will run daily at 06:50 Asia/Ho_Chi_Minh.

## Tempo and MPP Integration

CLI fallback mode uses Tempo CLI:

```bash
tempo request -t --max-spend <amount> -X POST --json '<payload>' <mpp-url>
```

Local MVP v2 mode uses the Node helper in `node_mppx/`. It calls OpenWeather MPP through `mppx` and the `accounts/cli` provider after you authorize a local Access Key once with:

```bash
cd node_mppx
npm run connect
```

The application uses:

- `POST /openweather/geocode` with `q` and `limit`.
- `POST /openweather/current-weather` with `lat`, `lon`, `units`, and `lang`.
- Optional `POST /v1/chat/completions` on OpenAI MPP.

The wallet address is intentionally not published in this README. Never put a private key, seed phrase, wallet address, or wallet recovery material into this repo or GitHub Actions logs.

## Telegram Integration

The app sends one text message through:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/sendMessage
```

The bot token and chat id are read from environment variables only.

## Testing

Run:

```bash
python -m pytest -q
```

Tests do not spend MPP funds and do not call Telegram. MPP-dependent behavior is isolated behind `TempoRequestClient` and `MppxWeatherClient`; live payment tests should be run manually with a funded, scoped Tempo Wallet.

`requirements.txt` lists direct project dependencies. `requirements-lock.txt` pins the full test/runtime dependency set used by local setup and GitHub Actions.

## Security Review Checklist

- No secrets are committed.
- `.env` is ignored.
- `.venv` and local cache folders are ignored.
- Telegram token is never logged.
- Tempo private keys or seed phrases are never requested.
- MPP spend is capped with `--max-spend`.
- Scheduled production run fails closed if Tempo Wallet is not ready.
