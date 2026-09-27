import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { createVault } from '../src/vault.js';
import { openRepository } from '../src/repository.js';
import { createMediaStore } from '../src/media.js';
import { createScheduler } from '../src/scheduler.js';
import { createApp } from '../src/server.js';
import { ProviderError } from '../src/providers/http.js';

const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
);

let dir, repo, server, base, clock, published, behaviour;

const fake = {
  id: 'fake',
  name: 'Fake',
  maxLength: 20,
  maxMedia: 1,
  fields: [{ key: 'token', label: 'Token', required: true, secret: true }],
  async verify(c) {
    return { account: c.token };
  },
  async publish(c, payload) {
    const mode = behaviour.shift() ?? 'ok';
    if (mode === 'retry') throw new ProviderError('rate limited', { retryable: true });
    if (mode === 'fatal') throw new ProviderError('bad request', { retryable: false });
    published.push({ credentials: c, ...payload });
    return { id: `ext-${published.length}`, url: `https://example.test/${published.length}` };
  },
};

let scheduler;

before(async () => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'postbot-'));
  fs.mkdirSync(path.join(dir, 'uploads'));
  clock = { now: Date.parse('2030-01-01T10:00:00Z') };
  repo = openRepository(path.join(dir, 'test.db'), createVault('k'));
  const media = createMediaStore(path.join(dir, 'uploads'));
  scheduler = createScheduler({
    repo, media,
    providers: new Map([['fake', fake]]),
    maxAttempts: 3,
    logger: {},
    now: () => clock.now,
  });
  server = createApp({
    repo, media, scheduler,
    providers: new Map([['fake', fake]]),
    config: { host: '127.0.0.1', publicDir: path.join(import.meta.dirname, '..', 'public'), maxUploadBytes: 1e6 },
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(() => {
  server.close();
  repo.close();
  fs.rmSync(dir, { recursive: true, force: true });
});

async function call(method, url, body, headers = {}) {
  const res = await fetch(base + url, {
    method,
    headers: body instanceof Buffer ? headers : { 'Content-Type': 'application/json', ...headers },
    body: body instanceof Buffer ? body : body && JSON.stringify(body),
  });
  const text = await res.text();
  return { status: res.status, body: text ? JSON.parse(text) : null };
}

test('end-to-end: channel → scheduled post → publish with retry', async () => {
  published = [];
  behaviour = [];

  assert.equal((await call('POST', '/api/channels', { provider: 'fake', credentials: {} })).status, 422);
  const ch = await call('POST', '/api/channels', { provider: 'fake', name: 'Test', credentials: { token: 's3cr3t' } });
  assert.equal(ch.status, 201);
  assert.equal(ch.body.credentials, undefined, 'credentials must never be returned');

  const verify = await call('POST', `/api/channels/${ch.body.id}/verify`);
  assert.deepEqual(verify.body, { ok: true, account: 's3cr3t' });

  const tooLong = await call('POST', '/api/posts', {
    content: 'x'.repeat(21), channelIds: [ch.body.id], scheduledAt: clock.now,
  });
  assert.equal(tooLong.status, 422);

  const upload = await call('POST', '/api/media', PNG, { 'Content-Type': 'image/png' });
  assert.equal(upload.status, 201);
  const fakePng = await call('POST', '/api/media', Buffer.from('<svg/>'), { 'Content-Type': 'image/png' });
  assert.equal(fakePng.status, 415);

  const post = await call('POST', '/api/posts', {
    content: 'Merhaba 👋', media: [upload.body.name], channelIds: [ch.body.id],
    scheduledAt: new Date(clock.now + 60_000).toISOString(),
  });
  assert.equal(post.status, 201);
  assert.equal(post.body.status, 'scheduled');

  await scheduler.tick();
  assert.equal(published.length, 0, 'not due yet');

  clock.now += 60_000;
  behaviour = ['retry'];
  await scheduler.tick();
  let state = (await call('GET', `/api/posts/${post.body.id}`)).body;
  assert.equal(state.targets[0].status, 'queued');
  assert.equal(state.targets[0].attempts, 1);
  assert.equal(state.targets[0].lastError, 'rate limited');

  await scheduler.tick();
  assert.equal(published.length, 0, 'backoff respected');

  clock.now += 60_000;
  await scheduler.tick();
  state = (await call('GET', `/api/posts/${post.body.id}`)).body;
  assert.equal(state.status, 'published');
  assert.equal(state.targets[0].externalUrl, 'https://example.test/1');
  assert.equal(published[0].text, 'Merhaba 👋');
  assert.equal(published[0].credentials.token, 's3cr3t');
  assert.ok(published[0].media[0].buffer.equals(PNG));

  const edit = await call('PUT', `/api/posts/${post.body.id}`, {
    content: 'değişti', channelIds: [ch.body.id], scheduledAt: clock.now,
  });
  assert.equal(edit.status, 409, 'published posts are immutable');
});

test('non-retryable failure, manual retry and publish-now', async () => {
  published = [];
  behaviour = ['fatal'];
  const ch = (await call('POST', '/api/channels', { provider: 'fake', credentials: { token: 't' } })).body;
  const post = (await call('POST', '/api/posts', {
    content: 'yarın', channelIds: [ch.id], scheduledAt: clock.now + 86_400_000,
  })).body;

  let res = await call('POST', `/api/posts/${post.id}/publish`);
  assert.equal(res.body.status, 'failed');
  assert.equal(res.body.targets[0].attempts, 1);

  await call('POST', `/api/posts/${post.id}/retry`);
  res = await call('POST', `/api/posts/${post.id}/publish`);
  assert.equal(res.body.status, 'published');
  assert.equal(published.length, 1);
});

test('drafts are never published and paused channels are skipped', async () => {
  published = [];
  behaviour = [];
  const ch = (await call('POST', '/api/channels', { provider: 'fake', credentials: { token: 't' } })).body;
  await call('POST', '/api/posts', { content: 'taslak', channelIds: [ch.id], scheduledAt: clock.now, draft: true });
  await call('PATCH', `/api/channels/${ch.id}`, { enabled: false });
  const post = (await call('POST', '/api/posts', { content: 'bekle', channelIds: [ch.id], scheduledAt: clock.now })).body;

  await scheduler.tick();
  assert.equal(published.length, 0);

  await call('PATCH', `/api/channels/${ch.id}`, { enabled: true });
  await scheduler.tick();
  assert.equal(published.length, 1);
  assert.equal(published[0].text, 'bekle');
  assert.equal((await call('GET', `/api/posts/${post.id}`)).body.status, 'published');
});

test('interrupted publishes are not silently re-sent', () => {
  const ch = repo.channels.create({ provider: 'fake', name: 'x', credentials: { token: 't' } });
  const post = repo.posts.create({ content: 'c', media: [], scheduledAt: 0, draft: false, channelIds: [ch.id] });
  assert.equal(repo.queue.claimDue(clock.now, 10).length >= 1, true);
  repo.queue.recoverInterrupted();
  assert.equal(repo.posts.get(post.id).targets[0].status, 'failed');
});

test('security guards', async () => {
  const origin = await call('POST', '/api/channels', { provider: 'fake', credentials: { token: 't' } }, { Origin: 'https://evil.test' });
  assert.equal(origin.status, 403);

  const form = await fetch(`${base}/api/posts`, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: '{}' });
  assert.equal(form.status, 415, 'CORS-simple content types rejected');

  // fetch() drops a custom Host header, so use node:http directly.
  const rebindingStatus = await new Promise((resolve, reject) => {
    http.get(`${base}/api/channels`, { headers: { Host: 'evil.test' } }, (res) => {
      res.resume();
      resolve(res.statusCode);
    }).on('error', reject);
  });
  assert.equal(rebindingStatus, 403);

  assert.equal((await fetch(`${base}/..%2fpackage.json`)).status, 404);
  assert.equal((await fetch(`${base}/`)).status, 200);
});
