const $ = (sel) => document.querySelector(sel);

const STATUS_LABEL = {
  draft: 'Taslak', scheduled: 'Zamanlanmış', publishing: 'Yayınlanıyor', published: 'Yayınlandı',
  partial: 'Kısmi', failed: 'Başarısız', queued: 'Sırada',
};
const PROVIDER_ABBR = { x: '𝕏', bluesky: 'B', mastodon: 'M', linkedin: 'in', facebook: 'f', telegram: 'T', discord: 'D', console: '>' };
const DAY_MS = 86_400_000;
const segmenter = new Intl.Segmenter();
const graphemes = (s) => [...segmenter.segment(s)].length;

const state = {
  providers: new Map(),
  channels: [],
  posts: [],
  weekStart: startOfWeek(new Date()),
  editing: null,
  media: [],
  editingChannel: null,
};

/** Minimal DOM builder; strings are always inserted as text (XSS-safe). */
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className = v;
    else if (k in el && typeof v !== 'string') el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  el.append(...children.flat().filter((c) => c != null && c !== false));
  return el;
}

async function api(path, { method = 'GET', body, raw, contentType } = {}) {
  const headers = {};
  let payload;
  if (raw) {
    payload = raw;
    headers['Content-Type'] = contentType;
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(path, { method, headers, body: payload });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error([data.error ?? res.statusText, ...(data.details ?? [])].join('\n'));
    err.status = res.status;
    throw err;
  }
  return data;
}

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.hidden = true), 3000);
}

function startOfWeek(date) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); // Monday
  return d;
}
const addDays = (date, n) => new Date(date.getFullYear(), date.getMonth(), date.getDate() + n);
const sameDay = (a, b) => a.toDateString() === b.toDateString();
const fmtTime = (ms) => new Date(ms).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
const fmtDateTime = (ms) =>
  new Date(ms).toLocaleString('tr-TR', { dateStyle: 'medium', timeStyle: 'short' });

function toLocalInput(ms) {
  const d = new Date(ms);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

const badge = (provider) => h('span', { class: `badge p-${provider}`, title: provider }, PROVIDER_ABBR[provider] ?? '?');
const statusPill = (status) => h('span', { class: `status ${status}` }, STATUS_LABEL[status] ?? status);

/* ---------- Data ---------- */

async function loadChannels() {
  state.channels = await api('/api/channels');
  renderChannels();
}

async function loadPosts() {
  state.posts = await api('/api/posts');
  renderCalendar();
  renderList();
}

/* ---------- Sidebar ---------- */

function renderChannels() {
  const list = $('#channel-list');
  if (!state.channels.length) {
    list.replaceChildren(h('li', { class: 'empty' }, 'Henüz kanal yok. "+" ile ekleyin.'));
    return;
  }
  list.replaceChildren(
    ...state.channels.map((c) =>
      h('li', { class: c.enabled ? '' : 'disabled' },
        badge(c.provider),
        h('span', { class: 'name', title: c.name }, c.name),
        h('span', { class: 'menu' },
          h('button', { title: 'Bağlantıyı test et', onclick: () => verifyChannel(c) }, '✓'),
          h('button', { title: c.enabled ? 'Duraklat' : 'Etkinleştir', onclick: () => toggleChannel(c) }, c.enabled ? '⏸' : '▶'),
          h('button', { title: 'Düzenle', onclick: () => openChannelDialog(c) }, '✎'),
          h('button', { title: 'Sil', onclick: () => deleteChannel(c) }, '✕'),
        ),
      ),
    ),
  );
}

async function verifyChannel(channel) {
  toast(`${channel.name} test ediliyor…`);
  const res = await api(`/api/channels/${channel.id}/verify`, { method: 'POST' });
  toast(res.ok ? `✓ Bağlantı başarılı: ${res.account}` : `✕ ${res.error}`);
}

async function toggleChannel(channel) {
  await api(`/api/channels/${channel.id}`, { method: 'PATCH', body: { enabled: !channel.enabled } });
  await loadChannels();
}

async function deleteChannel(channel) {
  if (!confirm(`"${channel.name}" kanalı ve geçmişi silinsin mi?`)) return;
  await api(`/api/channels/${channel.id}`, { method: 'DELETE' });
  await Promise.all([loadChannels(), loadPosts()]);
}

/* ---------- Channel dialog ---------- */

function renderProviderFields() {
  const provider = state.providers.get($('#channel-provider').value);
  const editing = state.editingChannel;
  $('#provider-help').textContent = provider.help ?? '';
  $('#provider-fields').replaceChildren(
    ...provider.fields.map((f) =>
      h('label', { class: 'field' },
        h('span', {}, f.label + (f.required ? ' *' : '')),
        h('input', {
          name: f.key,
          type: f.secret ? 'password' : 'text',
          placeholder: editing ? '(değiştirmemek için boş bırakın)' : f.placeholder ?? '',
          autocomplete: 'off',
          required: f.required && !editing,
        }),
      ),
    ),
  );
}

function openChannelDialog(channel = null) {
  state.editingChannel = channel;
  const select = $('#channel-provider');
  select.disabled = Boolean(channel);
  select.value = channel?.provider ?? select.options[0].value;
  $('#channel-dialog-title').textContent = channel ? 'Kanalı düzenle' : 'Kanal ekle';
  $('#channel-name').value = channel?.name ?? '';
  $('#channel-error').hidden = true;
  renderProviderFields();
  $('#channel-dialog').showModal();
}

async function submitChannel(event) {
  event.preventDefault();
  const credentials = Object.fromEntries(
    [...$('#provider-fields').querySelectorAll('input')].map((i) => [i.name, i.value]),
  );
  const name = $('#channel-name').value;
  try {
    const channel = state.editingChannel
      ? await api(`/api/channels/${state.editingChannel.id}`, { method: 'PATCH', body: { name, credentials } })
      : await api('/api/channels', { method: 'POST', body: { provider: $('#channel-provider').value, name, credentials } });
    $('#channel-dialog').close();
    await loadChannels();
    verifyChannel(channel);
  } catch (err) {
    $('#channel-error').textContent = err.message;
    $('#channel-error').hidden = false;
  }
}

/* ---------- Calendar & list ---------- */

function postCard(post) {
  const time = fmtTime(post.scheduledAt);
  return h('button', { class: `card s-${post.status}`, onclick: () => openComposer(post) },
    h('span', { class: 'meta' }, time, ...post.targets.map((t) => badge(t.provider)), statusPill(post.status)),
    h('span', { class: 'text' }, post.content || '(yalnızca görsel)'),
  );
}

function renderCalendar() {
  const start = state.weekStart;
  const end = addDays(start, 7);
  const today = new Date();
  $('#week-label').textContent =
    `${start.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long' })} – ` +
    `${addDays(end, -1).toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })}`;

  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  $('#calendar').replaceChildren(
    ...days.map((day) => {
      const posts = state.posts.filter((p) => sameDay(new Date(p.scheduledAt), day));
      const isPast = day < addDays(today, 0) && !sameDay(day, today);
      return h('div', { class: `day${sameDay(day, today) ? ' today' : ''}${isPast ? ' past' : ''}` },
        h('div', { class: 'day-head' },
          h('span', {}, day.toLocaleDateString('tr-TR', { weekday: 'short' })),
          h('strong', {}, String(day.getDate())),
        ),
        ...posts.map(postCard),
        !isPast && h('button', { class: 'day-add', title: 'Bu güne gönderi ekle', onclick: () => openComposer(null, day) }, '+'),
      );
    }),
  );
}

function renderList() {
  const filter = $('#status-filter').value;
  const posts = state.posts.filter((p) => !filter || p.status === filter).sort((a, b) => b.scheduledAt - a.scheduledAt);
  $('#post-list').replaceChildren(
    ...(posts.length
      ? posts.map((p) => {
          const card = postCard(p);
          card.querySelector('.meta').prepend(fmtDateTime(p.scheduledAt).replace(fmtTime(p.scheduledAt), '').trim(), ' ');
          return card;
        })
      : [h('p', { class: 'empty' }, 'Gönderi yok.')]),
  );
}

/* ---------- Composer ---------- */

function selectedChannelIds() {
  return [...$('#composer-channels').querySelectorAll('input:checked')].map((i) => Number(i.value));
}

function renderCounters() {
  const length = graphemes($('#content').value);
  const ids = new Set(selectedChannelIds());
  $('#counters').replaceChildren(
    h('span', {}, `${length} karakter`),
    ...state.channels
      .filter((c) => ids.has(c.id))
      .map((c) => {
        const p = state.providers.get(c.provider);
        const over = length > p.maxLength || state.media.length > p.maxMedia;
        return h('span', { class: over ? 'over' : '' },
          `${c.name}: ${length}/${p.maxLength}`,
          state.media.length > p.maxMedia ? ` · en fazla ${p.maxMedia} görsel` : '',
        );
      }),
  );
}

function renderMedia() {
  const locked = composerLocked();
  $('#media-preview').replaceChildren(
    ...state.media.map((name) =>
      h('figure', {},
        h('img', { src: `/media/${name}`, alt: '' }),
        !locked && h('button', { type: 'button', title: 'Kaldır', onclick: () => {
          state.media = state.media.filter((m) => m !== name);
          renderMedia();
          renderCounters();
        } }, '×'),
      ),
    ),
  );
}

function renderTargetsStatus(post) {
  const box = $('#targets-status');
  if (!post || post.draft) return box.replaceChildren();
  box.replaceChildren(
    ...post.targets.map((t) =>
      h('div', {},
        h('div', { class: 'row' },
          badge(t.provider), h('span', {}, t.channelName), statusPill(t.status),
          t.externalUrl && h('a', { href: t.externalUrl, target: '_blank', rel: 'noopener noreferrer' }, 'Görüntüle ↗'),
          t.status === 'queued' && t.attempts > 0 && t.nextAttemptAt &&
            h('span', { class: 'empty' }, `tekrar: ${fmtTime(t.nextAttemptAt)}`),
        ),
        t.lastError && h('div', { class: 'err' }, t.lastError),
      ),
    ),
  );
}

const composerLocked = () =>
  Boolean(state.editing?.targets.some((t) => t.status === 'published' || t.status === 'publishing'));

function openComposer(post = null, day = null) {
  state.editing = post;
  state.media = [...(post?.media ?? [])];
  const locked = composerLocked();
  const selected = new Set(post?.targets.map((t) => t.channelId) ?? state.channels.filter((c) => c.enabled).map((c) => c.id));

  $('#composer-title').textContent = post ? (locked ? 'Gönderi' : 'Gönderiyi düzenle') : 'Yeni gönderi';
  $('#content').value = post?.content ?? '';
  $('#content').readOnly = locked;

  let when = post?.scheduledAt;
  if (!when) {
    const base = day && !sameDay(day, new Date()) ? new Date(day.getFullYear(), day.getMonth(), day.getDate(), 10) : new Date(Date.now() + 3_600_000);
    base.setMinutes(Math.ceil(base.getMinutes() / 15) * 15, 0, 0);
    when = base.getTime();
  }
  $('#scheduled-at').value = toLocalInput(when);
  $('#scheduled-at').disabled = locked;

  $('#composer-channels').replaceChildren(
    ...(state.channels.length
      ? state.channels.map((c) =>
          h('label', { class: 'chip', title: c.enabled ? c.name : `${c.name} (duraklatıldı)` },
            h('input', { type: 'checkbox', value: String(c.id), checked: selected.has(c.id), disabled: locked, onchange: renderCounters }),
            badge(c.provider), c.name,
          ),
        )
      : [h('span', { class: 'empty' }, 'Önce soldan bir kanal ekleyin.')]),
  );

  const failed = post?.targets.some((t) => t.status === 'failed');
  $('#delete-post').hidden = !post;
  $('#save-draft').hidden = locked;
  $('#schedule').hidden = locked;
  $('#publish-now').hidden = locked && !failed;
  $('#publish-now').textContent = locked ? 'Başarısızları tekrar dene' : 'Şimdi paylaş';
  $('#media-input').closest('label').hidden = locked;
  $('#composer-error').hidden = true;

  renderMedia();
  renderCounters();
  renderTargetsStatus(post);
  $('#composer').showModal();
  if (!locked) $('#content').focus();
}

function composerPayload(draft) {
  return {
    content: $('#content').value,
    media: state.media,
    channelIds: selectedChannelIds(),
    scheduledAt: new Date($('#scheduled-at').value).toISOString(),
    draft,
  };
}

async function withBusy(fn) {
  const buttons = [...$('#composer').querySelectorAll('button')];
  buttons.forEach((b) => (b.disabled = true));
  $('#composer-error').hidden = true;
  try {
    await fn();
  } catch (err) {
    $('#composer-error').textContent = err.message;
    $('#composer-error').hidden = false;
  } finally {
    buttons.forEach((b) => (b.disabled = false));
  }
}

async function savePost(draft) {
  const payload = composerPayload(draft);
  return state.editing
    ? api(`/api/posts/${state.editing.id}`, { method: 'PUT', body: payload })
    : api('/api/posts', { method: 'POST', body: payload });
}

const actions = {
  draft: () => withBusy(async () => {
    await savePost(true);
    $('#composer').close();
    toast('Taslak kaydedildi');
    await loadPosts();
  }),
  schedule: () => withBusy(async () => {
    const post = await savePost(false);
    $('#composer').close();
    toast(`Zamanlandı: ${fmtDateTime(post.scheduledAt)}`);
    await loadPosts();
  }),
  publishNow: () => withBusy(async () => {
    let post;
    if (composerLocked()) {
      post = await api(`/api/posts/${state.editing.id}/retry`, { method: 'POST' });
      post = await api(`/api/posts/${post.id}/publish`, { method: 'POST' });
    } else {
      post = await savePost(false);
      post = await api(`/api/posts/${post.id}/publish`, { method: 'POST' });
    }
    state.editing = post;
    await loadPosts();
    toast(STATUS_LABEL[post.status]);
    openComposer(post);
  }),
  remove: () => withBusy(async () => {
    if (!confirm('Gönderi silinsin mi? (Platformlardaki paylaşımlar silinmez)')) return;
    await api(`/api/posts/${state.editing.id}`, { method: 'DELETE' });
    $('#composer').close();
    await loadPosts();
  }),
};

async function uploadFiles(files) {
  for (const file of files) {
    try {
      const { name } = await api('/api/media', { method: 'POST', raw: file, contentType: file.type });
      state.media.push(name);
    } catch (err) {
      toast(`${file.name}: ${err.message}`);
    }
  }
  renderMedia();
  renderCounters();
}

/* ---------- Wiring ---------- */

function bind() {
  document.querySelectorAll('.tab').forEach((tab) =>
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t === tab));
      document.querySelectorAll('.view').forEach((v) => (v.hidden = v.id !== `view-${tab.dataset.view}`));
    }),
  );
  $('#prev-week').onclick = () => { state.weekStart = addDays(state.weekStart, -7); renderCalendar(); };
  $('#next-week').onclick = () => { state.weekStart = addDays(state.weekStart, 7); renderCalendar(); };
  $('#today').onclick = () => { state.weekStart = startOfWeek(new Date()); renderCalendar(); };
  $('#status-filter').onchange = renderList;

  $('#new-post').onclick = () => openComposer();
  $('#content').oninput = renderCounters;
  $('#media-input').onchange = (e) => {
    uploadFiles([...e.target.files]);
    e.target.value = '';
  };
  $('#composer-cancel').onclick = () => $('#composer').close();
  $('#save-draft').onclick = actions.draft;
  $('#schedule').onclick = actions.schedule;
  $('#publish-now').onclick = actions.publishNow;
  $('#delete-post').onclick = actions.remove;
  $('#composer-form').onsubmit = (e) => e.preventDefault();

  $('#add-channel').onclick = () => openChannelDialog();
  $('#channel-provider').onchange = renderProviderFields;
  $('#channel-cancel').onclick = () => $('#channel-dialog').close();
  $('#channel-form').onsubmit = submitChannel;
}

async function init() {
  bind();
  const providers = await api('/api/providers');
  state.providers = new Map(providers.map((p) => [p.id, p]));
  $('#channel-provider').replaceChildren(...providers.map((p) => h('option', { value: p.id }, p.name)));
  await Promise.all([loadChannels(), loadPosts()]);

  // Refresh statuses in the background unless a dialog is open.
  setInterval(() => {
    if (!document.querySelector('dialog[open]') && document.visibilityState === 'visible') loadPosts().catch(() => {});
  }, 20_000);
}

init().catch((err) => toast(err.message));
