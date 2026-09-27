import fs from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

export const MIME_BY_EXT = { png: 'image/png', jpg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp' };
const EXT_BY_MIME = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp' };
const NAME_RE = /^[0-9a-f-]{36}\.(png|jpg|gif|webp)$/;

const SIGNATURES = {
  png: (b) => b.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])),
  jpg: (b) => b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff,
  gif: (b) => b.subarray(0, 4).toString('latin1') === 'GIF8',
  webp: (b) => b.subarray(0, 4).toString('latin1') === 'RIFF' && b.subarray(8, 12).toString('latin1') === 'WEBP',
};

export const isMediaName = (name) => typeof name === 'string' && NAME_RE.test(name);

export function createMediaStore(dir) {
  const resolve = (name) => {
    if (!isMediaName(name)) throw new Error(`Geçersiz medya: ${name}`);
    return path.join(dir, name);
  };

  return {
    dir,
    resolve,
    /** Returns null when the payload is not a supported image. */
    async save(buffer, mime) {
      const ext = EXT_BY_MIME[mime];
      if (!ext || !SIGNATURES[ext](buffer)) return null;
      const name = `${randomUUID()}.${ext}`;
      await fs.writeFile(path.join(dir, name), buffer, { flag: 'wx' });
      return name;
    },
    async exists(name) {
      try {
        await fs.access(resolve(name));
        return true;
      } catch {
        return false;
      }
    },
    async load(names) {
      return Promise.all(
        names.map(async (name) => ({
          filename: name,
          mime: MIME_BY_EXT[name.split('.').pop()],
          buffer: await fs.readFile(resolve(name)),
        })),
      );
    },
  };
}
