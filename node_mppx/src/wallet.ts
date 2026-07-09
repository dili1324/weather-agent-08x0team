import { Expiry } from 'accounts'
import { Provider } from 'accounts/cli'
import { numberToHex, parseUnits } from 'viem'
import {
  ACCESS_KEY_DAILY_LIMIT_USDC,
  ACCESS_KEY_EXPIRY_DAYS,
  ACCESS_KEY_PERIOD_SECONDS,
  TEMPO_USDC_TOKEN,
} from './config.js'
import { log } from './log.js'

export type AccountsProvider = ReturnType<typeof Provider.create>

function createAccessKeyPolicy() {
  const limit = parseUnits(ACCESS_KEY_DAILY_LIMIT_USDC, 6)
  return {
    expiry: Expiry.days(ACCESS_KEY_EXPIRY_DAYS),
    limits: [
      {
        token: TEMPO_USDC_TOKEN,
        limit,
        period: ACCESS_KEY_PERIOD_SECONDS,
      },
    ],
  }
}

export function createProvider(): AccountsProvider {
  return Provider.create({
    accessKey: {
      authorize: createAccessKeyPolicy,
    },
    mpp: false,
  })
}

export async function connectWallet(provider: AccountsProvider): Promise<unknown> {
  log('connecting wallet')
  const result = await provider.request({ method: 'wallet_connect' })
  log('wallet connected')
  return result
}

export async function authorizeAccessKey(provider: AccountsProvider): Promise<{
  accountAddress?: string
  accessKeyAddress?: string
  accessKeyStatus?: Awaited<ReturnType<AccountsProvider['getAccessKeyStatus']>>
}> {
  const policy = createAccessKeyPolicy()
  const accessKey = {
    ...policy,
    limits: policy.limits.map((limit) => ({
      ...limit,
      limit: numberToHex(limit.limit),
    })),
  }

  log('authorizing access key', {
    expiryDays: ACCESS_KEY_EXPIRY_DAYS,
    dailyLimitUsdc: ACCESS_KEY_DAILY_LIMIT_USDC,
    token: TEMPO_USDC_TOKEN,
  })

  const result = await provider.request({
    method: 'wallet_connect',
    params: [{ capabilities: { authorizeAccessKey: accessKey } }],
  })

  const account = result?.accounts?.[0]
  const accessKeyAddress = account?.capabilities?.keyAuthorization?.address
  const accessKeyStatus = await provider.getAccessKeyStatus()

  if (!accessKeyAddress && accessKeyStatus === 'missing') {
    throw new Error('Access key was not authorized by the wallet provider')
  }

  log('access key authorization completed', {
    status: accessKeyStatus,
  })

  return {
    accountAddress: account?.address,
    ...(accessKeyAddress ? { accessKeyAddress } : {}),
    accessKeyStatus,
  }
}
