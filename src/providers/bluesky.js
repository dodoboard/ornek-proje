import { request, requireFields, trimSlash } from './http.js';

const DEFAULT_SERVICE = 'https://bsky.social';
const URL_RE = /https?:\/\/[^\s<>"]+/g;
const TAG_RE = /(^|\s)(#[\p{L}\p{N}_]+)/gu;

const encoder = new TextEncoder();
const byteLen = (s) => encoder.encode(s).length;

/** Builds AT Protocol rich-text facets (links + hashtags) using UTF-8 byte offsets. */
export function buildFacets(text) {
  const facets = [];
  for (const m of text.matchAll(URL_RE)) {
    const uri = m[0].replace(/[.,;:!?)\]]+$/, '');
    const byteStart = byteLen(text.slice(0, m.index));
    facets.push({
      index: { byteStart, byteEnd: byteStart + byteLen(uri) },
      features: [{ $type: 'app.bsky.richtext.facet#link', uri }],
    });
  }
  for (const m of text.matchAll(TAG_RE)) {
    const start = m.index + m[1].length;
    const byteStart = byteLen(text.slice(0, start));
    facets.push({
      index: { byteStart, byteEnd: byteStart + byteLen(m[2]) },
      features: [{ $type: 'app.bsky.richtext.facet#tag', tag: m[2].slice(1) }],
    });
  }
  return facets;
}

async function createSession(c) {
  requireFields(c, ['identifier', 'appPassword']);
  const service = trimSlash(c.service || DEFAULT_SERVICE);
  const { data } = await request(`${service}/xrpc/com.atproto.server.createSession`, {
    json: { identifier: c.identifier.trim(), password: c.appPassword },
  });
  return { service, auth: { Authorization: `Bearer ${data.accessJwt}` }, did: data.did, handle: data.handle };
}

export default {
  id: 'bluesky',
  name: 'Bluesky',
  maxLength: 300,
  maxMedia: 4,
  help: 'Ayarlar → Privacy and security → App Passwords üzerinden uygulama şifresi oluşturun.',
  fields: [
    { key: 'identifier', label: 'Kullanıcı adı (handle) veya e-posta', required: true, placeholder: 'ornek.bsky.social' },
    { key: 'appPassword', label: 'App Password', required: true, secret: true },
    { key: 'service', label: 'PDS adresi', placeholder: DEFAULT_SERVICE },
  ],

  async verify(c) {
    const s = await createSession(c);
    return { account: `@${s.handle}` };
  },

  async publish(c, { text, media }) {
    const s = await createSession(c);
    const record = { $type: 'app.bsky.feed.post', text, createdAt: new Date().toISOString() };
    const facets = buildFacets(text);
    if (facets.length) record.facets = facets;

    if (media.length) {
      const images = [];
      for (const item of media) {
        const { data } = await request(`${s.service}/xrpc/com.atproto.repo.uploadBlob`, {
          headers: { ...s.auth, 'Content-Type': item.mime },
          body: item.buffer,
        });
        images.push({ alt: '', image: data.blob });
      }
      record.embed = { $type: 'app.bsky.embed.images', images };
    }

    const { data } = await request(`${s.service}/xrpc/com.atproto.repo.createRecord`, {
      headers: s.auth,
      json: { repo: s.did, collection: 'app.bsky.feed.post', record },
    });
    const rkey = data.uri.split('/').pop();
    return { id: data.uri, url: `https://bsky.app/profile/${s.handle}/post/${rkey}` };
  },
};
