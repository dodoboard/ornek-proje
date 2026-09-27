import { mediaBlob, request, requireFields, ProviderError } from './http.js';

const WEBHOOK_RE = /^https:\/\/(?:canary\.|ptb\.)?discord(?:app)?\.com\/api\/webhooks\/\d+\/[\w-]+$/;

function webhookUrl(c) {
  requireFields(c, ['webhookUrl']);
  const url = c.webhookUrl.trim();
  if (!WEBHOOK_RE.test(url)) throw new ProviderError('Geçersiz Discord webhook adresi', { retryable: false });
  return url;
}

export default {
  id: 'discord',
  name: 'Discord',
  maxLength: 2000,
  maxMedia: 10,
  help: 'Kanal Ayarları → Entegrasyonlar → Webhook oluştur → URL kopyala.',
  fields: [{ key: 'webhookUrl', label: 'Webhook URL', required: true, secret: true }],

  async verify(c) {
    const { data } = await request(webhookUrl(c), { method: 'GET' });
    return { account: data.name };
  },

  async publish(c, { text, media }) {
    const url = `${webhookUrl(c)}?wait=true`;
    const payload = { content: text, allowed_mentions: { parse: [] } };
    let res;
    if (media.length) {
      const form = new FormData();
      form.append('payload_json', JSON.stringify(payload));
      media.forEach((item, i) => form.append(`files[${i}]`, mediaBlob(item), item.filename));
      res = await request(url, { body: form });
    } else {
      res = await request(url, { json: payload });
    }
    return { id: res.data.id, url: null };
  },
};
