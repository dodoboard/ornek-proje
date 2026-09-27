import fs from 'node:fs';
import path from 'node:path';
import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto';

const IV_LEN = 12;
const TAG_LEN = 16;

/** AES-256-GCM sealing for channel credentials at rest. */
export function createVault(secret) {
  const key = createHash('sha256').update(secret).digest();
  return {
    seal(value) {
      const iv = randomBytes(IV_LEN);
      const cipher = createCipheriv('aes-256-gcm', key, iv);
      const data = Buffer.concat([cipher.update(JSON.stringify(value), 'utf8'), cipher.final()]);
      return Buffer.concat([iv, cipher.getAuthTag(), data]).toString('base64');
    },
    open(sealed) {
      const buf = Buffer.from(sealed, 'base64');
      const decipher = createDecipheriv('aes-256-gcm', key, buf.subarray(0, IV_LEN));
      decipher.setAuthTag(buf.subarray(IV_LEN, IV_LEN + TAG_LEN));
      const data = Buffer.concat([decipher.update(buf.subarray(IV_LEN + TAG_LEN)), decipher.final()]);
      return JSON.parse(data.toString('utf8'));
    },
  };
}

export function loadOrCreateSecret(dataDir, envSecret) {
  if (envSecret) return envSecret;
  const file = path.join(dataDir, 'secret.key');
  try {
    return fs.readFileSync(file, 'utf8').trim();
  } catch (err) {
    if (err.code !== 'ENOENT') throw err;
  }
  const secret = randomBytes(32).toString('hex');
  fs.writeFileSync(file, secret, { mode: 0o600, flag: 'wx' });
  return secret;
}
