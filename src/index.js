import fs from 'node:fs';
import path from 'node:path';
import { config } from './config.js';
import { createVault, loadOrCreateSecret } from './vault.js';
import { openRepository } from './repository.js';
import { createMediaStore } from './media.js';
import { providers } from './providers/index.js';
import { createScheduler } from './scheduler.js';
import { createApp } from './server.js';

const uploadsDir = path.join(config.dataDir, 'uploads');
fs.mkdirSync(uploadsDir, { recursive: true });

const vault = createVault(loadOrCreateSecret(config.dataDir, config.appSecret));
const repo = openRepository(path.join(config.dataDir, 'postbot.db'), vault);
const media = createMediaStore(uploadsDir);
const scheduler = createScheduler({
  repo,
  providers,
  media,
  pollIntervalMs: config.pollIntervalMs,
  maxAttempts: config.maxAttempts,
  concurrency: config.concurrency,
});
const server = createApp({ repo, providers, scheduler, media, config });

if (!['127.0.0.1', 'localhost', '::1'].includes(config.host) && !config.appPassword && !config.allowedHosts) {
  console.warn('[uyarı] Sunucu ağa açık ve APP_PASSWORD tanımlı değil!');
}

server.listen(config.port, config.host, () => {
  console.log(`postbot → http://${config.host.includes(':') ? `[${config.host}]` : config.host}:${config.port}`);
  scheduler.start();
});

let shuttingDown = false;
async function shutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`${signal} alındı, kapanıyor...`);
  server.close();
  await scheduler.stop();
  repo.close();
  process.exit(0);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
