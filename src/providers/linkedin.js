import { request, requireFields, ProviderError } from './http.js';

const URN_RE = /^urn:li:(person|organization):[\w-]+$/;

/** LinkedIn "little text" format: reserved chars must be escaped; hashtags use a template. */
export function toLittleText(text) {
  return text
    .split(/(#[\p{L}\p{N}_]+)/u)
    .map((part, i) =>
      i % 2 === 1
        ? `{hashtag|\\#|${part.slice(1)}}`
        : part.replace(/[\\|{}@[\]()<>#*_~]/g, '\\$&'),
    )
    .join('');
}

/** LinkedIn versions are monthly and supported ~1 year; default to two months back. */
function defaultVersion(now = new Date()) {
  const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 2, 1));
  return `${d.getUTCFullYear()}${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

export default {
  id: 'linkedin',
  name: 'LinkedIn',
  maxLength: 3000,
  maxMedia: 0,
  help: 'LinkedIn Developer uygulamasında "w_member_social" (veya "w_organization_social") izinli erişim jetonu alın.',
  fields: [
    { key: 'accessToken', label: 'Erişim jetonu', required: true, secret: true },
    { key: 'authorUrn', label: 'Yazar URN', required: true, placeholder: 'urn:li:person:abc123' },
    { key: 'apiVersion', label: 'API sürümü (YYYYMM)', placeholder: defaultVersion() },
  ],

  async verify(c) {
    requireFields(c, ['accessToken', 'authorUrn']);
    if (!URN_RE.test(c.authorUrn.trim())) throw new ProviderError('Geçersiz yazar URN', { retryable: false });
    try {
      const { data } = await request('https://api.linkedin.com/v2/userinfo', {
        method: 'GET',
        headers: { Authorization: `Bearer ${c.accessToken.trim()}` },
      });
      return { account: data.name ?? c.authorUrn };
    } catch (err) {
      if (err.status === 401) throw err;
      return { account: c.authorUrn.trim() }; // token lacks openid scope; still usable for posting
    }
  },

  async publish(c, { text }) {
    requireFields(c, ['accessToken', 'authorUrn']);
    const { headers } = await request('https://api.linkedin.com/rest/posts', {
      headers: {
        Authorization: `Bearer ${c.accessToken.trim()}`,
        'LinkedIn-Version': c.apiVersion?.trim() || defaultVersion(),
        'X-Restli-Protocol-Version': '2.0.0',
      },
      json: {
        author: c.authorUrn.trim(),
        commentary: toLittleText(text),
        visibility: 'PUBLIC',
        distribution: { feedDistribution: 'MAIN_FEED', targetEntities: [], thirdPartyDistributionChannels: [] },
        lifecycleState: 'PUBLISHED',
        isReshareDisabledByAuthor: false,
      },
    });
    const urn = headers.get('x-restli-id');
    return { id: urn, url: urn ? `https://www.linkedin.com/feed/update/${urn}` : null };
  },
};
