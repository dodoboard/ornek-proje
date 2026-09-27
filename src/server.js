import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { timingSafeEqual, createHash } from 'node:crypto';
import { ConflictError } from './repository.js';
import { describeProviders } from './providers/index.js';
import { isMediaName, MIME_BY_EXT } from './media.js';

const MAX_JSON_BYTES = 1024 * 1024;
const MAX_CONTENT_CHARS = 100_000;
const MAX_POST_MEDIA = 10;
const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]', '::1']);

const STATIC_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

class HttpError extends Error {
  constructor(status, message, details) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

const segmenter = new Intl.Segmenter();
export const graphemeLength = (text) => [...segmenter.segment(text)].length;

function send(res, status, body, headers = {}) {
  const payload = body === undefined ? '' : JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    ...headers,
  });
  res.end(payload);
}

async function readBody(req, limit) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw new HttpError(413, 'İstek gövdesi çok büyük');
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

async function readJson(req) {
  if (!String(req.headers['content-type'] ?? '').startsWith('application/json')) {
    throw new HttpError(415, 'Content-Type application/json olmalı');
  }
  try {
    return JSON.parse((await readBody(req, MAX_JSON_BYTES)).toString('utf8') || '{}');
  } catch (err) {
    if (err instanceof HttpError) throw err;
    throw new HttpError(400, 'Geçersiz JSON');
  }
}

const parseId = (value) => {
  const id = Number(value);
  if (!Number.isSafeInteger(id) || id <= 0) throw new HttpError(404, 'Bulunamadı');
  return id;
};

function parseTime(value) {
  const ms = typeof value === 'number' ? value : Date.parse(value);
  if (!Number.isFinite(ms)) throw new HttpError(422, 'Geçersiz tarih');
  return ms;
}

const safeEqual = (a, b) =>
  timingSafeEqual(createHash('sha256').update(a).digest(), createHash('sha256').update(b).digest());

export function createApp({ repo, providers, scheduler, media, config }) {
  const allowedHosts = config.allowedHosts?.length
    ? new Set(config.allowedHosts)
    : LOOPBACK_HOSTS.has(config.host) ? LOOPBACK_HOSTS : null;

  function validateCredentials(provider, input, existing = {}) {
    const credentials = {};
    for (const field of provider.fields) {
      const value = String(input?.[field.key] ?? '').trim();
      credentials[field.key] = value || existing[field.key] || '';
      if (field.required && !credentials[field.key]) {
        throw new HttpError(422, `"${field.label}" zorunlu`);
      }
    }
    return credentials;
  }

  async function validatePost(body) {
    const content = typeof body.content === 'string' ? body.content.replace(/\r\n/g, '\n') : '';
    const mediaNames = Array.isArray(body.media) ? body.media : [];
    const channelIds = [...new Set((Array.isArray(body.channelIds) ? body.channelIds : []).map(Number))];
    const draft = Boolean(body.draft);
    const scheduledAt = parseTime(body.scheduledAt ?? Date.now());

    if (!content.trim() && !mediaNames.length) throw new HttpError(422, 'İçerik veya görsel gerekli');
    if (content.length > MAX_CONTENT_CHARS) throw new HttpError(422, 'İçerik çok uzun');
    if (mediaNames.length > MAX_POST_MEDIA) throw new HttpError(422, `En fazla ${MAX_POST_MEDIA} görsel`);
    for (const name of mediaNames) {
      if (!isMediaName(name) || !(await media.exists(name))) throw new HttpError(422, `Görsel bulunamadı: ${name}`);
    }
    if (!draft && !channelIds.length) throw new HttpError(422, 'En az bir kanal seçin');

    const length = graphemeLength(content);
    const problems = [];
    for (const id of channelIds) {
      const channel = repo.channels.get(id);
      if (!channel) throw new HttpError(422, `Kanal bulunamadı: ${id}`);
      const provider = providers.get(channel.provider);
      if (!provider) throw new HttpError(422, `Desteklenmeyen platform: ${channel.provider}`);
      if (length > provider.maxLength) problems.push(`${channel.name}: ${length}/${provider.maxLength} karakter`);
      if (mediaNames.length > provider.maxMedia) {
        problems.push(`${channel.name}: en fazla ${provider.maxMedia} görsel`);
      }
    }
    if (problems.length && !draft) throw new HttpError(422, 'Platform sınırları aşıldı', problems);

    return { content, media: mediaNames, channelIds, draft, scheduledAt };
  }

  const routes = [
    ['GET', /^\/api\/providers$/, () => describeProviders(providers)],

    ['GET', /^\/api\/channels$/, () => repo.channels.list()],
    ['POST', /^\/api\/channels$/, async (req) => {
      const body = await readJson(req);
      const provider = providers.get(body.provider);
      if (!provider) throw new HttpError(422, 'Geçersiz platform');
      const name = String(body.name ?? '').trim() || provider.name;
      return [201, repo.channels.create({ provider: provider.id, name, credentials: validateCredentials(provider, body.credentials) })];
    }],
    ['PATCH', /^\/api\/channels\/(\d+)$/, async (req, [id]) => {
      const channel = repo.channels.get(parseId(id)) ?? notFound();
      const body = await readJson(req);
      const provider = providers.get(channel.provider);
      const credentials = body.credentials
        ? validateCredentials(provider, body.credentials, repo.channels.credentials(channel.id))
        : undefined;
      const name = body.name === undefined ? undefined : String(body.name).trim() || channel.name;
      const enabled = body.enabled === undefined ? undefined : Boolean(body.enabled);
      return repo.channels.update(channel.id, { name, credentials, enabled });
    }],
    ['DELETE', /^\/api\/channels\/(\d+)$/, (_req, [id]) => (repo.channels.remove(parseId(id)) ? [204] : notFound())],
    ['POST', /^\/api\/channels\/(\d+)\/verify$/, async (_req, [id]) => {
      const channel = repo.channels.get(parseId(id)) ?? notFound();
      try {
        return { ok: true, ...(await providers.get(channel.provider).verify(repo.channels.credentials(channel.id))) };
      } catch (err) {
        return { ok: false, error: err.message };
      }
    }],

    ['GET', /^\/api\/posts$/, (_req, _p, url) => {
      const from = parseTime(url.searchParams.get('from') ?? 0);
      const to = parseTime(url.searchParams.get('to') ?? 8.64e15);
      return repo.posts.range(from, to);
    }],
    ['GET', /^\/api\/posts\/(\d+)$/, (_req, [id]) => repo.posts.get(parseId(id)) ?? notFound()],
    ['POST', /^\/api\/posts$/, async (req) => {
      const post = repo.posts.create(await validatePost(await readJson(req)));
      scheduler.tick();
      return [201, post];
    }],
    ['PUT', /^\/api\/posts\/(\d+)$/, async (req, [id]) => {
      const post = repo.posts.update(parseId(id), await validatePost(await readJson(req))) ?? notFound();
      scheduler.tick();
      return post;
    }],
    ['DELETE', /^\/api\/posts\/(\d+)$/, (_req, [id]) => (repo.posts.remove(parseId(id)) ? [204] : notFound())],
    ['POST', /^\/api\/posts\/(\d+)\/publish$/, async (_req, [id]) => {
      const existing = repo.posts.get(parseId(id)) ?? notFound();
      if (!existing.targets.length) throw new HttpError(422, 'Gönderide kanal yok');
      const post = repo.posts.publishNow(existing.id);
      await scheduler.tick();
      return repo.posts.get(post.id);
    }],
    ['POST', /^\/api\/posts\/(\d+)\/retry$/, (_req, [id]) => {
      const post = repo.posts.retryFailed(parseId(id)) ?? notFound();
      scheduler.tick();
      return post;
    }],

    ['POST', /^\/api\/media$/, async (req) => {
      const mime = String(req.headers['content-type'] ?? '').split(';')[0].trim();
      const name = await media.save(await readBody(req, config.maxUploadBytes), mime);
      if (!name) throw new HttpError(415, 'Yalnızca PNG, JPEG, GIF veya WEBP');
      return [201, { name, url: `/media/${name}` }];
    }],
  ];

  function notFound() {
    throw new HttpError(404, 'Bulunamadı');
  }

  function guard(req) {
    if (allowedHosts) {
      // DNS-rebinding protection.
      const hostname = String(req.headers.host ?? '').toLowerCase().replace(/:\d+$/, '');
      if (!allowedHosts.has(hostname)) throw new HttpError(403, 'Geçersiz Host');
    }
    const origin = req.headers.origin;
    if (origin && origin !== 'null') {
      let originHost;
      try {
        originHost = new URL(origin).host;
      } catch {
        throw new HttpError(403, 'Geçersiz Origin');
      }
      if (originHost !== req.headers.host) throw new HttpError(403, 'Cross-origin istek reddedildi');
    } else if (origin === 'null' && req.method !== 'GET') {
      throw new HttpError(403, 'Cross-origin istek reddedildi');
    }
    if (config.appPassword) {
      const [scheme, encoded] = String(req.headers.authorization ?? '').split(' ');
      const password = scheme === 'Basic' ? Buffer.from(encoded ?? '', 'base64').toString().split(':').slice(1).join(':') : '';
      if (!safeEqual(password, config.appPassword)) {
        throw new HttpError(401, 'Kimlik doğrulama gerekli');
      }
    }
  }

  function serveFile(res, file, type) {
    fs.stat(file, (err, stat) => {
      if (err || !stat.isFile()) return send(res, 404, { error: 'Bulunamadı' });
      res.writeHead(200, {
        'Content-Type': type,
        'Content-Length': stat.size,
        'X-Content-Type-Options': 'nosniff',
        'Cache-Control': 'no-cache',
      });
      fs.createReadStream(file).pipe(res);
    });
  }

  function serveStatic(res, pathname) {
    if (pathname.startsWith('/media/')) {
      const name = pathname.slice('/media/'.length);
      if (!isMediaName(name)) return send(res, 404, { error: 'Bulunamadı' });
      return serveFile(res, media.resolve(name), MIME_BY_EXT[name.split('.').pop()]);
    }
    const rel = pathname === '/' ? 'index.html' : decodeURIComponent(pathname).replace(/^\/+/, '');
    const file = path.resolve(config.publicDir, rel);
    if (!file.startsWith(config.publicDir + path.sep)) return send(res, 404, { error: 'Bulunamadı' });
    serveFile(res, file, STATIC_TYPES[path.extname(file)] ?? 'application/octet-stream');
  }

  async function handle(req, res) {
    const url = new URL(req.url, 'http://localhost');
    try {
      guard(req);
      if (!url.pathname.startsWith('/api/')) {
        if (req.method !== 'GET' && req.method !== 'HEAD') throw new HttpError(405, 'İzin verilmeyen metot');
        return serveStatic(res, url.pathname);
      }
      for (const [method, pattern, handler] of routes) {
        const match = pattern.exec(url.pathname);
        if (!match || method !== req.method) continue;
        const result = await handler(req, match.slice(1), url);
        const [status, body] = Array.isArray(result) && typeof result[0] === 'number' ? result : [200, result];
        return send(res, status, body);
      }
      throw new HttpError(404, 'Bulunamadı');
    } catch (err) {
      if (err instanceof ConflictError) return send(res, 409, { error: err.message });
      if (err instanceof HttpError) {
        const headers = err.status === 401 ? { 'WWW-Authenticate': 'Basic realm="postbot"' } : {};
        return send(res, err.status, { error: err.message, details: err.details }, headers);
      }
      console.error('[http]', err);
      return send(res, 500, { error: 'Sunucu hatası' });
    }
  }

  return http.createServer((req, res) => {
    handle(req, res);
  });
}
