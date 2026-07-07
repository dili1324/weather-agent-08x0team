# Local MPPX SDK Research

This note is for local MVP v2 only. It does not change the current Python + `tempo request` CLI fallback and does not cover GitHub Actions.

## Goal

Find an official path for a local Mac agent to:

- use a test Tempo Wallet or test access key,
- call OpenWeather MPP,
- avoid browser/passkey approval for every paid request,
- keep the existing Python orchestration and Telegram delivery if possible.

## Current CLI Finding

The current implementation uses `tempo request`. Local testing shows the wallet can be ready and OpenWeather MPP can succeed, but each paid request may still open browser/passkey payment approval.

The official CLI docs and `tempo request --help` confirm useful controls such as `--dry-run` and `--max-spend`, but do not document an auto-approve, assume-yes, trusted-service, or pre-approved-spend mode for `tempo request`.

Conclusion: the blocker is not wallet login. It is per-request payment approval in the CLI flow.

## Official SDK Findings

### Python MPP Client

Official MPP docs confirm a Python client exists. It wraps `httpx`, intercepts HTTP `402`, parses the Challenge, signs a stablecoin transfer, retries with a Credential, and exposes common methods such as `get`, `post`, and `request`.

The documented Tempo example uses:

```python
from mpp.client import Client
from mpp.methods.tempo import tempo, TempoAccount, ChargeIntent

account = TempoAccount.from_key("0x...")

async with Client(methods=[tempo(account=account, intents={"charge": ChargeIntent()})]) as client:
    response = await client.get("https://api.example.com/resource")
```

This proves Python has an official MPP client. It does not prove Python can reuse a Tempo Wallet passkey session or a wallet-provider-authorized Access Key without exposing raw private-key material. The docs reviewed do not show a Python equivalent of the Accounts SDK provider path.

Local MVP impact:

- Python-only SDK migration is not ready for this project unless we deliberately use a raw private key account.
- That would be a different wallet/security model from the current Tempo Wallet/passkey flow.
- Do not implement the Python SDK path yet for this passkey wallet MVP.

### TypeScript `mppx` Client

Official MPP docs confirm `mppx/client` creates a payment-aware `fetch` client. It handles paid resources by intercepting `402`, creating a Credential, and retrying the request.

The official TypeScript client supports two relevant account sources:

- Accounts SDK provider:

```ts
import { Mppx, tempo } from 'mppx/client'
import { Provider } from 'accounts'

const provider = Provider.create({ mpp: false })
await provider.request({ method: 'wallet_connect' })

const mppx = Mppx.create({
  methods: [tempo({
    account: provider.getAccount({ signable: true }),
    getClient: provider.getClient,
  })],
  polyfill: false,
})
```

- Raw private key via `viem`:

```ts
import { Mppx, tempo } from 'mppx/client'
import { privateKeyToAccount } from 'viem/accounts'

const account = privateKeyToAccount('0x...')

const mppx = Mppx.create({
  methods: [tempo({ account })],
  polyfill: false,
})
```

For this project, the Accounts SDK provider path is the right research target because it matches Tempo Wallet/passkey better than storing a raw wallet private key.

### Access Key Spend Management

Official MPP "Managing agent spend" docs state that Tempo Access Keys are delegated signing keys authorized by a wallet and can be constrained by:

- token spending limits,
- contract/function limitations,
- recipient restrictions,
- future-dated expiry.

The docs show the wallet provider authorizing an Access Key:

```ts
import { Expiry, Provider } from 'accounts'

export const provider = Provider.create()

const accessKey = {
  expiry: Expiry.days(7),
}

const { accounts } = await provider.request({
  method: 'wallet_connect',
  params: [{ capabilities: { authorizeAccessKey: accessKey } }],
})

const [account] = accounts
export const accessKeyAddress = account?.capabilities.keyAuthorization?.address
```

They also show optional spending limits and scopes:

```ts
import { Expiry } from 'accounts'
import { numberToHex, parseUnits } from 'viem'
import { Scopes } from 'viem/tempo'

const usdc = '0x20C000000000000000000000b9537d11c60E8b50'
const recipientAddress = '0x0000000000000000000000000000000000000001'

const accessKey = {
  expiry: Expiry.days(7),
  limits: [
    {
      token: usdc,
      limit: numberToHex(parseUnits('10', 6)),
      period: 86_400,
    },
  ],
  scopes: [
    Scopes.tip20(usdc).transfer({
      recipients: [recipientAddress],
    }),
  ],
}
```

Then `mppx` can use that provider and optionally pin the specific Access Key:

```ts
import { Mppx, tempo } from 'mppx/client'
import { accessKeyAddress, provider } from './wallet.js'

Mppx.create({
  methods: [
    tempo({
      account: provider.getAccount(),
      ...provider.getMppxParameters({ accessKey: accessKeyAddress }),
    }),
  ],
})
```

The same docs state that `mppx` only pays when a server returns a payment challenge, and the wallet signs with the requested Access Key when it can satisfy the challenge.

## Feasibility Conclusion

Local unattended spend appears feasible through the official TypeScript `mppx` + Accounts SDK + Tempo Access Key path, after a one-time local wallet/passkey authorization for the Access Key.

It is not confirmed through the current `tempo request` CLI flow.

It is not yet confirmed as a pure Python passkey-wallet flow because the Python docs reviewed only show `TempoAccount.from_key("0x...")`.

## Recommended MVP v2 Architecture

Keep the current architecture as much as possible:

1. Python remains the orchestrator.
2. Python keeps Telegram, formatter, config, logging, and debug checks.
3. Python keeps the current Tempo CLI weather client as fallback.
4. Add a small Node/TypeScript helper only for paid MPP HTTP requests.
5. The helper uses:
   - `accounts`
   - `mppx`
   - `viem`
6. Python calls the helper for:
   - OpenWeather `/geocode`
   - OpenWeather `/current-weather`
   - GPT MPP later, only if enabled.
7. The helper returns raw JSON to stdout so existing Python parsing can remain mostly unchanged.

Suggested backend switch for a later implementation:

```text
MPP_BACKEND=tempo_cli   # current default fallback
MPP_BACKEND=mppx_node   # local MVP v2 experiment
```

The first implementation should target OpenWeather only. GPT can follow after OpenWeather proves no per-request browser/passkey prompt appears.

## Local Setup Plan for MVP v2 Spike

The helper now lives in `node_mppx/`. It is intentionally separate from the Python app.

The installed package version currently exposes the local Node provider through `accounts/cli`, not through the browser-style root `accounts` provider used in the public docs examples. The helper therefore imports `Provider` from `accounts/cli` and keeps `Expiry` from `accounts`.

1. Install Node.js 20+ on the Mac mini.
2. Install helper dependencies:

```bash
cd node_mppx
npm install
```

The helper `package.json` already declares the official SDK dependencies (`accounts`, `mppx`, `viem`) plus TypeScript tooling.

3. Authorize one small Access Key:

```bash
export MPPX_ACCESS_KEY_DAILY_LIMIT_USDC=0.25
export MPPX_ACCESS_KEY_EXPIRY_DAYS=1
npm run connect
```

The wallet/provider may open browser/passkey once. That is acceptable for this spike.

4. Run one paid weather request:

```bash
npm run weather:once
```

5. Run two paid weather requests in the same process:

```bash
npm run weather:twice
```

Success means:

- `weather:twice` returns `"ok": true`,
- request 2 does not open browser/passkey approval,
- stderr includes payment challenge, credential, and retry-response logs,
- stdout remains parseable JSON.

Failure means:

- if request 2 still opens browser/passkey approval, the new blocker is not `tempo request`; it is that the Accounts SDK / wallet provider did not reuse the authorized Access Key for unattended MPP payments in this local CLI runtime.
- `getMppxParameters({ accessKey })` is not present on the installed `accounts@0.14.11` provider type. The helper uses the package's current typed API instead: `accounts/cli` provider storage plus `provider.getClient` and a JSON-RPC account.

6. Only after `weather:twice` succeeds should Python be wired to call the Node helper.

Useful helper commands:

```bash
cd node_mppx
npm run connect
npm run geocode
npm run current-weather
npm run weather:once
npm run weather:twice
npm run typecheck
```

Verified local result:

- `npm run typecheck` passes.
- For this clone, authorize the Access Key with wallet `0x4315A89ddEAD8F6B059b4952aC219640bFe2f0c4`.
- `npm run weather:once` completed `/geocode` and `/current-weather` through `mppx`.
- `npm run weather:twice` completed two full OpenWeather flows in one process.
- All four paid requests in `weather:twice` received payment challenges, created credentials, retried, and returned HTTP 200.
- No additional browser/passkey approval prompt appeared in the command output during `weather:twice`.

## Remaining Gaps Before Code

The Node helper has been added and the first local verification passed. Remaining follow-up points:

- Watch whether `accessKeyStatus: "pending"` later becomes `"published"` in provider status checks. The current successful weather run proves the pending local authorization can still create credentials.
- Confirm how much of this local provider storage can or should be made portable. This is not needed for local MVP v2 and is still not a GitHub Actions task.
- Keep the first Python integration behind an explicit backend switch so `tempo request` remains available as fallback.

## Official Sources

- MPP managing agent spend: https://mpp.dev/guides/managing-agent-spend
- MPP Python client: https://mpp.dev/sdk/python/client
- MPP TypeScript client `tempo`: https://mpp.dev/sdk/typescript/client/Method.tempo
- MPP TypeScript `Mppx.create`: https://mpp.dev/sdk/typescript/client/Mppx.create
- MPP client quickstart: https://mpp.dev/quickstart/client
- MPP agent quickstart: https://mpp.dev/quickstart/agent
- MPP CLI reference: https://mpp.dev/sdk/typescript/cli
