import { createHmac, randomBytes } from 'node:crypto';
import { mediaBlob, request, requireFields } from './http.js';

const API = 'https://api.x.com/2';
const KEYS = ['apiKey', 'apiSecret', 'accessToken', 'accessTokenSecret'];

/** RFC 3986 percent-encoding as required by OAuth 1.0a. */
const pct = (s) =>
  encodeURIComponent(String(s)).replace(/[!'()*]/g, (ch) => `%${ch.charCodeAt(0).toString(16).toUpperCase()}`);

/**
 * OAuth 1.0a HMAC-SHA1 Authorization header. `params` = form-urlencoded body params
 * (JSON and multipart bodies are excluded from the signature per spec).
 */
export function oauthHeader(method, url, c, params = {}, { nonce, timestamp } = {}) {
  const u = new URL(url);
  const oauth = {
    oauth_consumer_key: c.apiKey,
    oauth_nonce: nonce ?? randomBytes(16).toString('hex'),
    oauth_signature_method: 'HMAC-SHA1',
    oauth_timestamp: timestamp ?? String(Math.floor(Date.now() / 1000)),
    oauth_token: c.accessToken,
    oauth_version: '1.0',
  };
  const paramString = [...Object.entries(oauth), ...u.searchParams, ...Object.entries(params)]
    .map(([k, v]) => [pct(k), pct(v)])
    .sort(([a, av], [b, bv]) => (a === b ? (av < bv ? -1 : 1) : a < b ? -1 : 1))
    .map(([k, v]) => `${k}=${v}`)
    .join('&');
  const base = [method.toUpperCase(), pct(`${u.origin}${u.pathname}`), pct(paramString)].join('&');
  const signature = createHmac('sha1', `${pct(c.apiSecret)}&${pct(c.accessTokenSecret)}`).update(base).digest('base64');
  return `OAuth ${Object.entries({ ...oauth, oauth_signature: signature })
    .map(([k, v]) => `${pct(k)}="${pct(v)}"`)
    .join(', ')}`;
}

const creds = (c) => Object.fromEntries(KEYS.map((k) => [k, String(c[k]).trim()]));

export default {
  id: 'x',
  name: 'X (Twitter)',
  maxLength: 280,
  maxMedia: 4,
  help: 'developer.x.com → Proje → App → "Read and write" izni verip API Key/Secret ve Access Token/Secret üretin.',
  fields: [
    { key: 'apiKey', label: 'API Key', required: true, secret: true },
    { key: 'apiSecret', label: 'API Key Secret', required: true, secret: true },
    { key: 'accessToken', label: 'Access Token', required: true, secret: true },
    { key: 'accessTokenSecret', label: 'Access Token Secret', required: true, secret: true },
  ],

  async verify(c) {
    requireFields(c, KEYS);
    const url = `${API}/users/me`;
    const { data } = await request(url, { method: 'GET', headers: { Authorization: oauthHeader('GET', url, creds(c)) } });
    return { account: `@${data.data.username}` };
  },

  async publish(c, { text, media }) {
    requireFields(c, KEYS);
    const k = creds(c);
    const mediaIds = [];
    for (const item of media) {
      const url = `${API}/media/upload`;
      const form = new FormData();
      form.append('media', mediaBlob(item), item.filename);
      form.append('media_category', 'tweet_image');
      const { data } = await request(url, { headers: { Authorization: oauthHeader('POST', url, k) }, body: form });
      mediaIds.push(String(data.data?.id ?? data.media_id_string));
    }

    const url = `${API}/tweets`;
    const { data } = await request(url, {
      headers: { Authorization: oauthHeader('POST', url, k) },
      json: { text, ...(mediaIds.length ? { media: { media_ids: mediaIds } } : {}) },
    });
    return { id: data.data.id, url: `https://x.com/i/web/status/${data.data.id}` };
  },
};
