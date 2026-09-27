export class ProviderError extends Error {
  constructor(message, { retryable = true, status } = {}) {
    super(message);
    this.name = 'ProviderError';
    this.retryable = retryable;
    this.status = status;
  }
}

function extractMessage(data, text) {
  if (data && typeof data === 'object') {
    const msg =
      data.description ?? data.error_description ?? data.error?.message ?? data.message ??
      data.detail ?? data.title ?? data.errors?.[0]?.message ?? data.error;
    if (msg) return typeof msg === 'string' ? msg : JSON.stringify(msg);
  }
  return String(text ?? '').slice(0, 300);
}

/**
 * fetch wrapper. Error messages expose only the host (never the path/query),
 * because several APIs (Telegram, Discord webhooks) embed secrets in the URL.
 */
export async function request(url, { method = 'POST', headers = {}, json, body, timeoutMs = 30_000 } = {}) {
  const finalHeaders = { Accept: 'application/json', ...headers };
  let payload = body;
  if (json !== undefined) {
    finalHeaders['Content-Type'] = 'application/json';
    payload = JSON.stringify(json);
  }

  const host = new URL(url).host;
  let res;
  try {
    res = await fetch(url, { method, headers: finalHeaders, body: payload, signal: AbortSignal.timeout(timeoutMs) });
  } catch (err) {
    throw new ProviderError(`${host}: ağ hatası (${err.cause?.code ?? err.name})`, { retryable: true });
  }

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok || (data && data.ok === false)) {
    throw new ProviderError(`${host} → HTTP ${res.status}: ${extractMessage(data, text)}`, {
      retryable: res.status === 429 || res.status >= 500,
      status: res.status,
    });
  }
  return { data, headers: res.headers, status: res.status };
}

export function mediaBlob(item) {
  return new Blob([item.buffer], { type: item.mime });
}

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function requireFields(credentials, keys) {
  const missing = keys.filter((k) => !String(credentials?.[k] ?? '').trim());
  if (missing.length) throw new ProviderError(`Eksik alan: ${missing.join(', ')}`, { retryable: false });
}

export const trimSlash = (url) => String(url).trim().replace(/\/+$/, '');
