import bluesky from './bluesky.js';
import discord from './discord.js';
import facebook from './facebook.js';
import linkedin from './linkedin.js';
import mastodon from './mastodon.js';
import telegram from './telegram.js';
import x from './x.js';

/** Dry-run channel: logs instead of publishing. Useful for testing schedules locally. */
const consoleProvider = {
  id: 'console',
  name: 'Konsol (test)',
  maxLength: 10_000,
  maxMedia: 10,
  help: 'Gerçek paylaşım yapmaz; gönderiyi sunucu konsoluna yazar.',
  fields: [],
  async verify() {
    return { account: 'stdout' };
  },
  async publish(_c, { text, media }) {
    console.log(`[console] ${new Date().toISOString()} media=${media.length}\n${text}`);
    return { id: `console-${Date.now()}`, url: null };
  },
};

export const providers = new Map(
  [x, bluesky, mastodon, linkedin, facebook, telegram, discord, consoleProvider].map((p) => [p.id, p]),
);

export function describeProviders(registry = providers) {
  return [...registry.values()].map(({ id, name, maxLength, maxMedia, help, fields }) => ({
    id, name, maxLength, maxMedia, help, fields,
  }));
}
