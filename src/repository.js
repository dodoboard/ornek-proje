import { DatabaseSync } from 'node:sqlite';

const SCHEMA = `
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS channels (
  id          INTEGER PRIMARY KEY,
  provider    TEXT    NOT NULL,
  name        TEXT    NOT NULL,
  credentials TEXT    NOT NULL,
  enabled     INTEGER NOT NULL DEFAULT 1,
  created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
  id           INTEGER PRIMARY KEY,
  content      TEXT    NOT NULL,
  media        TEXT    NOT NULL DEFAULT '[]',
  scheduled_at INTEGER NOT NULL,
  draft        INTEGER NOT NULL DEFAULT 0,
  created_at   INTEGER NOT NULL,
  updated_at   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS post_targets (
  id              INTEGER PRIMARY KEY,
  post_id         INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
  channel_id      INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
  status          TEXT    NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued', 'publishing', 'published', 'failed')),
  attempts        INTEGER NOT NULL DEFAULT 0,
  next_attempt_at INTEGER NOT NULL DEFAULT 0,
  last_error      TEXT,
  external_id     TEXT,
  external_url    TEXT,
  published_at    INTEGER,
  UNIQUE (post_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_scheduled ON posts (scheduled_at);
CREATE INDEX IF NOT EXISTS idx_targets_due ON post_targets (status, next_attempt_at);
`;

const LOCKED_STATUSES = new Set(['publishing', 'published']);

export class ConflictError extends Error {}

function toChannel(row) {
  return {
    id: row.id,
    provider: row.provider,
    name: row.name,
    enabled: row.enabled === 1,
    createdAt: row.created_at,
  };
}

function toTarget(row) {
  return {
    id: row.id,
    channelId: row.channel_id,
    channelName: row.channel_name,
    provider: row.provider,
    status: row.status,
    attempts: row.attempts,
    nextAttemptAt: row.next_attempt_at || null,
    lastError: row.last_error,
    externalId: row.external_id,
    externalUrl: row.external_url,
    publishedAt: row.published_at,
  };
}

export function derivePostStatus(post) {
  if (post.draft) return 'draft';
  const counts = { queued: 0, publishing: 0, published: 0, failed: 0 };
  for (const t of post.targets) counts[t.status]++;
  if (counts.publishing) return 'publishing';
  if (counts.queued) return counts.published || counts.failed ? 'partial' : 'scheduled';
  if (counts.failed) return counts.published ? 'partial' : 'failed';
  return 'published';
}

export function openRepository(file, vault) {
  const db = new DatabaseSync(file);
  db.exec(SCHEMA);

  const transaction = (fn) => {
    db.exec('BEGIN IMMEDIATE');
    try {
      const result = fn();
      db.exec('COMMIT');
      return result;
    } catch (err) {
      db.exec('ROLLBACK');
      throw err;
    }
  };

  const stmt = {
    channelList: db.prepare('SELECT * FROM channels ORDER BY id'),
    channelGet: db.prepare('SELECT * FROM channels WHERE id = ?'),
    channelInsert: db.prepare(
      'INSERT INTO channels (provider, name, credentials, enabled, created_at) VALUES (?, ?, ?, 1, ?)',
    ),
    channelUpdate: db.prepare('UPDATE channels SET name = ?, credentials = ?, enabled = ? WHERE id = ?'),
    channelDelete: db.prepare('DELETE FROM channels WHERE id = ?'),

    postGet: db.prepare('SELECT * FROM posts WHERE id = ?'),
    postRange: db.prepare(
      'SELECT * FROM posts WHERE scheduled_at >= ? AND scheduled_at < ? ORDER BY scheduled_at, id',
    ),
    postInsert: db.prepare(
      'INSERT INTO posts (content, media, scheduled_at, draft, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
    ),
    postUpdate: db.prepare(
      'UPDATE posts SET content = ?, media = ?, scheduled_at = ?, draft = ?, updated_at = ? WHERE id = ?',
    ),
    postDelete: db.prepare('DELETE FROM posts WHERE id = ?'),
    postPublishNow: db.prepare('UPDATE posts SET scheduled_at = ?, draft = 0, updated_at = ? WHERE id = ?'),

    targetsForPost: db.prepare(`
      SELECT t.*, c.name AS channel_name, c.provider
      FROM post_targets t JOIN channels c ON c.id = t.channel_id
      WHERE t.post_id = ? ORDER BY t.id`),
    targetInsert: db.prepare('INSERT INTO post_targets (post_id, channel_id) VALUES (?, ?)'),
    targetsDelete: db.prepare('DELETE FROM post_targets WHERE post_id = ?'),
    targetsResetQueued: db.prepare(
      "UPDATE post_targets SET next_attempt_at = 0 WHERE post_id = ? AND status = 'queued'",
    ),
    targetsRetryFailed: db.prepare(`
      UPDATE post_targets SET status = 'queued', attempts = 0, next_attempt_at = 0, last_error = NULL
      WHERE post_id = ? AND status = 'failed'`),

    due: db.prepare(`
      SELECT t.id, t.attempts, p.id AS post_id, p.content, p.media, c.provider, c.credentials
      FROM post_targets t
      JOIN posts p    ON p.id = t.post_id
      JOIN channels c ON c.id = t.channel_id
      WHERE t.status = 'queued' AND p.draft = 0 AND c.enabled = 1
        AND p.scheduled_at <= ? AND t.next_attempt_at <= ?
      ORDER BY p.scheduled_at, t.id
      LIMIT ?`),
    claim: db.prepare(
      "UPDATE post_targets SET status = 'publishing', attempts = attempts + 1 WHERE id = ? AND status = 'queued'",
    ),
    markPublished: db.prepare(`
      UPDATE post_targets
      SET status = 'published', external_id = ?, external_url = ?, published_at = ?, last_error = NULL
      WHERE id = ?`),
    markRetry: db.prepare(
      "UPDATE post_targets SET status = 'queued', last_error = ?, next_attempt_at = ? WHERE id = ?",
    ),
    markFailed: db.prepare("UPDATE post_targets SET status = 'failed', last_error = ? WHERE id = ?"),
    recoverInterrupted: db.prepare(`
      UPDATE post_targets SET status = 'failed',
        last_error = 'Yayın sırasında uygulama durdu. Platformda kontrol edip gerekirse tekrar deneyin.'
      WHERE status = 'publishing'`),
  };

  const hydratePost = (row) => {
    const post = {
      id: row.id,
      content: row.content,
      media: JSON.parse(row.media),
      scheduledAt: row.scheduled_at,
      draft: row.draft === 1,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      targets: stmt.targetsForPost.all(row.id).map(toTarget),
    };
    post.status = derivePostStatus(post);
    return post;
  };

  const assertEditable = (postId) => {
    const targets = stmt.targetsForPost.all(postId);
    if (targets.some((t) => LOCKED_STATUSES.has(t.status))) {
      throw new ConflictError('Yayınlanmış veya yayınlanmakta olan gönderi değiştirilemez.');
    }
  };

  return {
    close: () => db.close(),

    channels: {
      list: () => stmt.channelList.all().map(toChannel),
      get(id) {
        const row = stmt.channelGet.get(id);
        return row ? toChannel(row) : null;
      },
      credentials(id) {
        const row = stmt.channelGet.get(id);
        return row ? vault.open(row.credentials) : null;
      },
      create({ provider, name, credentials }, now = Date.now()) {
        const { lastInsertRowid } = stmt.channelInsert.run(provider, name, vault.seal(credentials), now);
        return this.get(Number(lastInsertRowid));
      },
      update(id, { name, credentials, enabled }) {
        const row = stmt.channelGet.get(id);
        if (!row) return null;
        const sealed = credentials ? vault.seal(credentials) : row.credentials;
        stmt.channelUpdate.run(name ?? row.name, sealed, enabled === undefined ? row.enabled : Number(enabled), id);
        return this.get(id);
      },
      remove: (id) => stmt.channelDelete.run(id).changes > 0,
    },

    posts: {
      get(id) {
        const row = stmt.postGet.get(id);
        return row ? hydratePost(row) : null;
      },
      range: (from, to) => stmt.postRange.all(from, to).map(hydratePost),
      create({ content, media, scheduledAt, draft, channelIds }, now = Date.now()) {
        const id = transaction(() => {
          const { lastInsertRowid } = stmt.postInsert.run(
            content, JSON.stringify(media), scheduledAt, Number(draft), now, now,
          );
          for (const channelId of channelIds) stmt.targetInsert.run(lastInsertRowid, channelId);
          return Number(lastInsertRowid);
        });
        return this.get(id);
      },
      update(id, { content, media, scheduledAt, draft, channelIds }, now = Date.now()) {
        const found = transaction(() => {
          if (!stmt.postGet.get(id)) return false;
          assertEditable(id);
          stmt.postUpdate.run(content, JSON.stringify(media), scheduledAt, Number(draft), now, id);
          stmt.targetsDelete.run(id);
          for (const channelId of channelIds) stmt.targetInsert.run(id, channelId);
          return true;
        });
        return found ? this.get(id) : null;
      },
      remove(id) {
        return transaction(() => {
          const targets = stmt.targetsForPost.all(id);
          if (targets.some((t) => t.status === 'publishing')) {
            throw new ConflictError('Yayınlanmakta olan gönderi silinemez.');
          }
          return stmt.postDelete.run(id).changes > 0;
        });
      },
      publishNow(id, now = Date.now()) {
        const found = transaction(() => {
          if (!stmt.postGet.get(id)) return false;
          stmt.postPublishNow.run(now, now, id);
          stmt.targetsResetQueued.run(id);
          return true;
        });
        return found ? this.get(id) : null;
      },
      retryFailed(id) {
        if (!stmt.postGet.get(id)) return null;
        stmt.targetsRetryFailed.run(id);
        return this.get(id);
      },
    },

    queue: {
      /** Atomically moves due targets to `publishing` and returns them with decrypted credentials. */
      claimDue(now, limit) {
        return transaction(() =>
          stmt.due
            .all(now, now, limit)
            .filter((row) => stmt.claim.run(row.id).changes === 1)
            .map((row) => ({
              id: row.id,
              postId: row.post_id,
              attempts: row.attempts + 1,
              content: row.content,
              media: JSON.parse(row.media),
              provider: row.provider,
              credentials: vault.open(row.credentials),
            })),
        );
      },
      markPublished(id, { id: externalId = null, url = null } = {}, now = Date.now()) {
        stmt.markPublished.run(externalId === null ? null : String(externalId), url, now, id);
      },
      markRetry: (id, error, nextAttemptAt) => stmt.markRetry.run(error, nextAttemptAt, id),
      markFailed: (id, error) => stmt.markFailed.run(error, id),
      recoverInterrupted: () => stmt.recoverInterrupted.run().changes,
    },
  };
}
