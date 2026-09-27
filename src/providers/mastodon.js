import { mediaBlob, request, requireFields, sleep, trimSlash, ProviderError } from './http.js';

const auth = (c) => ({ Authorization: `Bearer ${c.accessToken.trim()}` });

async function uploadMedia(base, c, item) {
  const form = new FormData();
  form.append('file', mediaBlob(item), item.filename);
  const { data, status } = await request(`${base}/api/v2/media`, { headers: auth(c), body: form });
  if (status !== 202) return data.id;

  // 202 = still processing; statuses referencing it would be rejected with 422.
  for (let i = 0; i < 15; i++) {
    await sleep(1000);
    const { data: m } = await request(`${base}/api/v1/media/${data.id}`, { method: 'GET', headers: auth(c) });
    if (m.url) return m.id;
  }
  throw new ProviderError('Mastodon medya işleme zaman aşımı', { retryable: true });
}

export default {
  id: 'mastodon',
  name: 'Mastodon',
  maxLength: 500,
  maxMedia: 4,
  help: 'Tercihler → Geliştirme → Yeni uygulama; "write:statuses write:media read:accounts" izinleriyle erişim jetonu alın.',
  fields: [
    { key: 'instanceUrl', label: 'Sunucu adresi', required: true, placeholder: 'https://mastodon.social' },
    { key: 'accessToken', label: 'Erişim jetonu', required: true, secret: true },
    { key: 'visibility', label: 'Görünürlük (public/unlisted/private)', placeholder: 'public' },
  ],

  async verify(c) {
    requireFields(c, ['instanceUrl', 'accessToken']);
    const { data } = await request(`${trimSlash(c.instanceUrl)}/api/v1/accounts/verify_credentials`, {
      method: 'GET',
      headers: auth(c),
    });
    return { account: `@${data.acct}` };
  },

  async publish(c, { text, media, idempotencyKey }) {
    requireFields(c, ['instanceUrl', 'accessToken']);
    const base = trimSlash(c.instanceUrl);
    const mediaIds = [];
    for (const item of media) mediaIds.push(await uploadMedia(base, c, item));

    const { data } = await request(`${base}/api/v1/statuses`, {
      headers: { ...auth(c), 'Idempotency-Key': idempotencyKey },
      json: { status: text, media_ids: mediaIds, visibility: c.visibility?.trim() || 'public' },
    });
    return { id: data.id, url: data.url };
  },
};
