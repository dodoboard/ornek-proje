import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const num = (value, fallback) => {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : fallback;
};

export const config = Object.freeze({
  host: process.env.HOST || '127.0.0.1',
  port: num(process.env.PORT, 3000),
  dataDir: path.resolve(process.env.DATA_DIR || path.join(root, 'data')),
  publicDir: path.join(root, 'public'),
  appSecret: process.env.APP_SECRET || null,
  appPassword: process.env.APP_PASSWORD || null,
  allowedHosts: process.env.ALLOWED_HOSTS
    ? process.env.ALLOWED_HOSTS.split(',').map((h) => h.trim().toLowerCase()).filter(Boolean)
    : null,
  pollIntervalMs: num(process.env.POLL_INTERVAL_MS, 15_000),
  maxAttempts: num(process.env.MAX_ATTEMPTS, 3),
  concurrency: num(process.env.PUBLISH_CONCURRENCY, 4),
  maxUploadBytes: num(process.env.MAX_UPLOAD_MB, 8) * 1024 * 1024,
});
