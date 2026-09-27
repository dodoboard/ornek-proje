import { mediaBlob, request, requireFields } from './http.js';

const DEFAULT_VERSION = 'v23.0';
const graph = (c) => `https://graph.facebook.com/${c.graphVersion?.trim() || DEFAULT_VERSION}`;

export default {
  id: 'facebook',
  name: 'Facebook Sayfası',
  maxLength: 63206,
  maxMedia: 1,
  help: 'Meta Graph API Explorer ile "pages_manage_posts" izinli, süresiz Sayfa erişim jetonu alın.',
  fields: [
    { key: 'pageId', label: 'Sayfa ID', required: true },
    { key: 'pageAccessToken', label: 'Sayfa erişim jetonu', required: true, secret: true },
    { key: 'graphVersion', label: 'Graph API sürümü', placeholder: DEFAULT_VERSION },
  ],

  async verify(c) {
    requireFields(c, ['pageId', 'pageAccessToken']);
    const url = new URL(`${graph(c)}/${encodeURIComponent(c.pageId.trim())}`);
    url.searchParams.set('fields', 'name');
    const { data } = await request(url.href, {
      method: 'GET',
      headers: { Authorization: `Bearer ${c.pageAccessToken.trim()}` },
    });
    return { account: data.name };
  },

  async publish(c, { text, media }) {
    requireFields(c, ['pageId', 'pageAccessToken']);
    const page = `${graph(c)}/${encodeURIComponent(c.pageId.trim())}`;
    const headers = { Authorization: `Bearer ${c.pageAccessToken.trim()}` };

    if (media.length) {
      const form = new FormData();
      form.append('source', mediaBlob(media[0]), media[0].filename);
      if (text) form.append('caption', text);
      const { data } = await request(`${page}/photos`, { headers, body: form });
      const id = data.post_id ?? data.id;
      return { id, url: `https://www.facebook.com/${id}` };
    }

    const { data } = await request(`${page}/feed`, { headers, json: { message: text } });
    return { id: data.id, url: `https://www.facebook.com/${data.id}` };
  },
};
