const BASE_BACKOFF_MS = 60_000;

/** 1m, 4m, 16m, ... capped at 1h. */
export const backoff = (attempt) => Math.min(BASE_BACKOFF_MS * 4 ** (attempt - 1), 3_600_000);

async function runPool(items, concurrency, worker) {
  const queue = [...items];
  const runners = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
    while (queue.length) await worker(queue.shift());
  });
  await Promise.all(runners);
}

export function createScheduler({
  repo,
  providers,
  media,
  pollIntervalMs = 15_000,
  maxAttempts = 3,
  concurrency = 4,
  logger = console,
  now = Date.now,
}) {
  let timer = null;
  let active = null;
  let rerun = false;

  async function publishTarget(target) {
    const provider = providers.get(target.provider);
    try {
      if (!provider) throw Object.assign(new Error(`Bilinmeyen platform: ${target.provider}`), { retryable: false });
      if (target.media.length > provider.maxMedia) {
        throw Object.assign(new Error(`${provider.name} en fazla ${provider.maxMedia} görsel destekler`), {
          retryable: false,
        });
      }
      const result = await provider.publish(target.credentials, {
        text: target.content,
        media: await media.load(target.media),
        idempotencyKey: `postbot-target-${target.id}`,
      });
      repo.queue.markPublished(target.id, result, now());
      logger.info?.(`[publish] target=${target.id} ${target.provider} ok ${result?.url ?? ''}`);
    } catch (err) {
      const message = String(err?.message ?? err).slice(0, 1000);
      if (err?.retryable !== false && target.attempts < maxAttempts) {
        repo.queue.markRetry(target.id, message, now() + backoff(target.attempts));
        logger.warn?.(`[publish] target=${target.id} ${target.provider} retry #${target.attempts}: ${message}`);
      } else {
        repo.queue.markFailed(target.id, message);
        logger.error?.(`[publish] target=${target.id} ${target.provider} failed: ${message}`);
      }
    }
  }

  async function drain() {
    do {
      rerun = false;
      const due = repo.queue.claimDue(now(), concurrency * 4);
      await runPool(due, concurrency, publishTarget);
      if (due.length === concurrency * 4) rerun = true;
    } while (rerun);
  }

  /** Coalesces concurrent calls: a tick during an active run schedules one more pass. */
  function tick() {
    if (active) {
      rerun = true;
      return active;
    }
    active = drain()
      .catch((err) => logger.error?.('[scheduler]', err))
      .finally(() => {
        active = null;
      });
    return active;
  }

  return {
    tick,
    start() {
      const recovered = repo.queue.recoverInterrupted();
      if (recovered) logger.warn?.(`[scheduler] ${recovered} yarım kalmış yayın 'failed' olarak işaretlendi`);
      timer = setInterval(tick, pollIntervalMs);
      return tick();
    },
    async stop() {
      clearInterval(timer);
      timer = null;
      await active;
    },
  };
}
