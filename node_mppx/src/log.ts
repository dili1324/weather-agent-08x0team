const sensitiveKeys = new Set([
  'accesskey',
  'accesskeyaddress',
  'account',
  'accountaddress',
  'address',
  'bearer',
  'handle',
  'key',
  'privatekey',
  'secret',
  'seed',
  'seedphrase',
  'store',
  'token',
  'wallet',
  'walletaddress',
  'walletstore',
])

function normalizeKey(key: string): string {
  return key.toLowerCase().replace(/[^a-z0-9]/g, '')
}

function redact(value: unknown, key = ''): unknown {
  if (sensitiveKeys.has(normalizeKey(key))) {
    return '<redacted>'
  }
  if (typeof value === 'string') {
    return value
      .replace(/(api\.telegram\.org\/bot)[^/\s"]+/g, '$1<redacted>')
      .replace(/(code=)[^&\s"]+/g, '$1<redacted>')
      .replace(/bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'bearer <redacted>')
      .replace(
        /\b(access[_-]?key|private[_-]?key|secret|seed(?:[_-]?phrase)?|token|wallet[_-]?store)(["']?\s*[:=]\s*["']?)[^"'\s,}]+/gi,
        '$1$2<redacted>',
      )
      .replace(/0x[a-fA-F0-9]{40}/g, '<redacted-address>')
  }
  if (Array.isArray(value)) {
    return value.map((item) => redact(item))
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([itemKey, item]) => [itemKey, redact(item, itemKey)]),
    )
  }
  return value
}

export function log(message: string, fields: Record<string, unknown> = {}): void {
  const payload = Object.keys(fields).length === 0 ? '' : ` ${JSON.stringify(redact(fields))}`
  process.stderr.write(`[mppx-helper] ${message}${payload}\n`)
}

export function printJson(value: unknown): void {
  process.stdout.write(`${JSON.stringify(redact(value), null, 2)}\n`)
}
