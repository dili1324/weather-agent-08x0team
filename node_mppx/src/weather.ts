import { Mppx, tempo } from 'mppx/client'
import {
  DEFAULT_CITY_QUERY,
  DEFAULT_LANG,
  DEFAULT_UNITS,
  endpoint,
} from './config.js'
import { log, printJson } from './log.js'
import { createProvider } from './wallet.js'

type GeocodeResult = {
  name?: string
  lat: number
  lon: number
  country?: string
  state?: string
}

type WeatherResponse = {
  geocode: unknown
  currentWeather: unknown
}

function unwrapData(value: unknown): unknown {
  if (value && typeof value === 'object' && 'data' in value) {
    return (value as { data: unknown }).data
  }
  return value
}

function firstGeocodeResult(value: unknown): GeocodeResult {
  const data = unwrapData(value)
  const item = Array.isArray(data) ? data[0] : data

  if (!item || typeof item !== 'object') {
    throw new Error('No geocode result returned')
  }

  const maybeResult = item as Partial<GeocodeResult>
  if (typeof maybeResult.lat !== 'number' || typeof maybeResult.lon !== 'number') {
    throw new Error('Geocode result does not include numeric lat/lon')
  }

  return {
    name: maybeResult.name,
    lat: maybeResult.lat,
    lon: maybeResult.lon,
    country: maybeResult.country,
    state: maybeResult.state,
  }
}

async function postJson(mppx: ReturnType<typeof Mppx.create>, path: string, payload: unknown): Promise<unknown> {
  const url = endpoint(path)
  log('request start', { url })
  const response = await mppx.fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const text = await response.text()
  let body: unknown
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = text
  }

  if (!response.ok) {
    throw new Error(`MPP request failed status=${response.status} body=${JSON.stringify(body)}`)
  }

  log('request completed', { url, status: response.status })
  return body
}

async function createMppxClient(): Promise<ReturnType<typeof Mppx.create>> {
  const provider = createProvider()
  const accounts = await provider.request({ method: 'eth_accounts' })
  log('loaded wallet state', { accountCount: Array.isArray(accounts) ? accounts.length : 0 })

  if (!Array.isArray(accounts) || accounts.length === 0) {
    throw new Error('No local wallet account available. Run npm run connect first.')
  }
  const account = provider.getAccount()

  const mppx = Mppx.create({
    methods: [
      tempo({
        account,
        getClient: provider.getClient,
      }),
    ],
    paymentPreferences: { 'tempo/charge': 1, 'tempo/session': 0 },
    polyfill: false,
  })

  mppx.onChallengeReceived(({ challenge }: any) => {
    log('payment challenge received', {
      id: challenge.id,
      method: challenge.method,
      intent: challenge.intent,
    })
  })
  mppx.onCredentialCreated(({ challenge }: any) => {
    log('payment credential created', {
      id: challenge.id,
      method: challenge.method,
      intent: challenge.intent,
    })
  })
  mppx.onPaymentResponse(({ response }: any) => {
    log('payment retry response', { status: response.status })
  })
  mppx.onPaymentFailed(({ error }: any) => {
    log('payment failed', { error: error instanceof Error ? error.message : String(error) })
  })

  return mppx
}

async function geocode(mppx: ReturnType<typeof Mppx.create>): Promise<unknown> {
  return postJson(mppx, '/geocode', {
    q: DEFAULT_CITY_QUERY,
    limit: 1,
  })
}

async function currentWeather(
  mppx: ReturnType<typeof Mppx.create>,
  geocodeBody: unknown,
): Promise<unknown> {
  const location = firstGeocodeResult(geocodeBody)
  return postJson(mppx, '/current-weather', {
    lat: location.lat,
    lon: location.lon,
    units: DEFAULT_UNITS,
    lang: DEFAULT_LANG,
  })
}

async function weatherOnce(mppx?: ReturnType<typeof Mppx.create>): Promise<WeatherResponse> {
  mppx = mppx ?? (await createMppxClient())
  const geocodeBody = await geocode(mppx)
  const currentWeatherBody = await currentWeather(mppx, geocodeBody)
  return {
    geocode: geocodeBody,
    currentWeather: currentWeatherBody,
  }
}

async function main(): Promise<void> {
  const command = process.argv[2] ?? 'once'
  const mppx = command === 'once' || command === 'twice' ? undefined : await createMppxClient()

  if (command === 'geocode') {
    printJson({ ok: true, geocode: await geocode(mppx!) })
    return
  }

  if (command === 'current-weather') {
    const geocodeBody = await geocode(mppx!)
    printJson({ ok: true, currentWeather: await currentWeather(mppx!, geocodeBody) })
    return
  }

  if (command === 'once') {
    printJson({ ok: true, run: await weatherOnce() })
    return
  }

  if (command === 'twice') {
    const sharedMppx = await createMppxClient()
    log('weather twice run 1 starting')
    const first = await weatherOnce(sharedMppx)
    log('weather twice run 1 completed')
    log('weather twice run 2 starting')
    const second = await weatherOnce(sharedMppx)
    log('weather twice run 2 completed')
    printJson({ ok: true, runs: [first, second] })
    return
  }

  throw new Error(`Unknown command: ${command}`)
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error)
  printJson({ ok: false, error: message })
  process.exitCode = 1
})
