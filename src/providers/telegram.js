import { mediaBlob, request, requireFields } from './http.js';

const CAPTION_LIMIT = 1024;

const api = (c, method) => `https://api.telegram.org/bot${c.botToken.trim()}/${method}`;

function messageUrl(chatId, messageId) {
  return chatId.startsWith('@') ? `https://t.me/${chatId.slice(1)}/${messageId}` : null;
}

export default {
  id: 'telegram',
  name: 'Telegram',
  maxLength: 4096,
  maxMedia: 10,
  help: '@BotFather ile bot oluşturun, botu kanala yönetici olarak ekleyin. Chat ID: @kanaladi veya -100… sayısal kimlik.',
  fields: [
    { key: 'botToken', label: 'Bot token', required: true, secret: true },
    { key: 'chatId', label: 'Chat ID', required: true, placeholder: '@kanalim' },
  ],

  async verify(c) {
    requireFields(c, ['botToken', 'chatId']);
    const { data } = await request(api(c, 'getChat'), { json: { chat_id: c.chatId.trim() } });
    return { account: data.result.title ?? data.result.username ?? String(data.result.id) };
  },

  async publish(c, { text, media }) {
    requireFields(c, ['botToken', 'chatId']);
    const chatId = c.chatId.trim();
    const captionFits = text.length <= CAPTION_LIMIT;
    let first;

    if (media.length === 1) {
      const form = new FormData();
      form.append('chat_id', chatId);
      form.append('photo', mediaBlob(media[0]), media[0].filename);
      if (captionFits && text) form.append('caption', text);
      first = (await request(api(c, 'sendPhoto'), { body: form })).data.result;
    } else if (media.length > 1) {
      const form = new FormData();
      form.append('chat_id', chatId);
      const items = media.map((item, i) => {
        form.append(`f${i}`, mediaBlob(item), item.filename);
        return { type: 'photo', media: `attach://f${i}`, ...(i === 0 && captionFits && text ? { caption: text } : {}) };
      });
      form.append('media', JSON.stringify(items));
      first = (await request(api(c, 'sendMediaGroup'), { body: form })).data.result[0];
    }

    if (!media.length || (!captionFits && text)) {
      const { data } = await request(api(c, 'sendMessage'), { json: { chat_id: chatId, text } });
      first ??= data.result;
    }
    return { id: first.message_id, url: messageUrl(chatId, first.message_id) };
  },
};
