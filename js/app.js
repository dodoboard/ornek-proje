(function () {
  'use strict';

  const { CATEGORIES, GROUPS, RELATION_LABELS } = window.Catalog;
  const Seating = window.Seating;
  const Store = window.Store;

  const CATEGORY_BY_ID = new Map(CATEGORIES.map((c) => [c.id, c]));
  const DIET_LABELS = {
    '': 'Standart', vejetaryen: 'Vejetaryen', vegan: 'Vegan', glutensiz: 'Glütensiz',
    diyabetik: 'Diyabetik', cocuk: 'Çocuk Menüsü', koser: 'Koşer', diger: 'Diğer',
  };

  let state = Store.load();
  let selectedSeat = null;

  /* ---------- Yardımcılar ---------- */

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));
  const esc = (v) =>
    String(v ?? '').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]);
  const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`);

  const rankMap = () => {
    const m = {};
    for (const c of CATEGORIES) {
      const o = state.rankOverrides[c.id];
      m[c.id] = Number.isFinite(o) ? o : c.rank;
    }
    return m;
  };

  const byId = () => Seating.indexById(state.guests);
  const fullName = (g) => [g.title, g.firstName, g.lastName].filter(Boolean).join(' ');
  const shortName = (g) => (g.lastName || g.firstName || '?').slice(0, 10);
  const categoryLabel = (g) => CATEGORY_BY_ID.get(g.categoryId)?.label || '—';
  const isInterpreter = (g) => g.categoryId === 'tercuman';

  function roleLabel(g, map = byId()) {
    const partner = g.partnerId ? map.get(g.partnerId) : null;
    if (g.relation === 'spouse') return partner ? `${fullName(partner)} eşi` : 'Eş';
    if (g.relation === 'child') return partner ? `${fullName(partner)} çocuğu` : 'Çocuk';
    if (partner) return `${categoryLabel(g)} · ${fullName(partner)}`;
    return categoryLabel(g);
  }

  function seatClass(g) {
    if (!g) return 'empty';
    if (g.isHost || g.isCoHost) return 'host';
    if (isInterpreter(g)) return 'interp';
    if (g.relation === 'child') return 'child';
    if (g.relation === 'spouse') return 'spouse';
    return g.side === 'foreign' ? 'foreign' : 'home';
  }

  function persist(markStale = false) {
    if (markStale && state.plan) state.planStale = true;
    if (!Store.save(state)) toast('Uyarı: veriler tarayıcıya kaydedilemedi.');
  }

  let toastTimer;
  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (el.hidden = true), 2600);
  }

  function download(name, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = Object.assign(document.createElement('a'), { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  /* ---------- Sekmeler ---------- */

  function showTab(name) {
    $$('.tabs [role=tab]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
    $$('.tab-panel').forEach((p) => (p.hidden = p.id !== `tab-${name}`));
    if (name === 'plan') renderPlan();
    if (name === 'ranks') renderRanks();
  }

  /* ---------- Davetli formu ---------- */

  function fillCategorySelect(select) {
    const groups = Object.values(GROUPS);
    select.innerHTML = groups
      .map((grp) => {
        const opts = CATEGORIES.filter((c) => c.group === grp)
          .map((c) => `<option value="${esc(c.id)}">${esc(c.label)}</option>`)
          .join('');
        return `<optgroup label="${esc(grp)}">${opts}</optgroup>`;
      })
      .join('');
  }

  function fillPartnerSelect(currentId) {
    const select = $('#guest-form [name=partnerId]');
    const prev = select.value;
    const map = byId();
    const ranks = rankMap();
    const candidates = state.guests
      .filter((g) => g.id !== currentId && !g.partnerId && (g.relation || 'principal') === 'principal')
      .sort((a, b) => Seating.effectiveRank(a, map, ranks) - Seating.effectiveRank(b, map, ranks));
    select.innerHTML =
      '<option value="">— Yok —</option>' +
      candidates.map((g) => `<option value="${esc(g.id)}">${esc(fullName(g))} (${esc(categoryLabel(g))})</option>`).join('');
    select.value = prev;
  }

  function syncFormVisibility() {
    const form = $('#guest-form');
    const foreign = form.side.value === 'foreign';
    $$('[data-foreign-only]', form).forEach((el) => (el.hidden = !foreign));
    const rel = form.relation.value;
    const interp = form.categoryId.value === 'tercuman';
    $('#partner-label').textContent =
      rel === 'spouse' ? 'Kimin Eşi' : rel === 'child' ? 'Kimin Çocuğu' : interp ? 'Tercümanlık Yaptığı Kişi' : 'Refakat Ettiği Kişi';
  }

  function resetForm() {
    const form = $('#guest-form');
    form.reset();
    form.guestId.value = '';
    $('#form-title').textContent = 'Davetli Ekle';
    fillPartnerSelect(null);
    syncFormVisibility();
  }

  function editGuest(id) {
    const g = state.guests.find((x) => x.id === id);
    if (!g) return;
    const form = $('#guest-form');
    fillPartnerSelect(g.id);
    const fields = { guestId: 'id', honorific: 'title' };
    for (const name of ['guestId', 'honorific', 'firstName', 'lastName', 'categoryId', 'side', 'delegation', 'relation',
      'partnerId', 'language', 'diet', 'notes']) {
      form.elements[name].value = g[fields[name] || name] ?? '';
    }
    form.rankOverride.value = Number.isFinite(g.rankOverride) ? g.rankOverride : '';
    form.isHost.checked = Boolean(g.isHost);
    form.isCoHost.checked = Boolean(g.isCoHost);
    form.needsInterpreter.checked = Boolean(g.needsInterpreter);
    $('#form-title').textContent = 'Davetli Düzenle';
    syncFormVisibility();
    form.firstName.focus();
  }

  /** partnerId zincirinin `id`'ye geri dönüp dönmediğini kontrol eder. */
  function createsCycle(id, partnerId) {
    const map = byId();
    let cur = partnerId;
    const seen = new Set();
    while (cur && !seen.has(cur)) {
      if (cur === id) return true;
      seen.add(cur);
      cur = map.get(cur)?.partnerId;
    }
    return false;
  }

  function onSubmitGuest(e) {
    e.preventDefault();
    const f = e.currentTarget;
    const id = f.guestId.value || uid();
    const rankOverride = f.rankOverride.value === '' ? null : Number(f.rankOverride.value);
    const guest = {
      id,
      title: f.honorific.value.trim(),
      firstName: f.firstName.value.trim(),
      lastName: f.lastName.value.trim(),
      categoryId: f.categoryId.value,
      side: f.side.value,
      delegation: f.side.value === 'foreign' ? f.delegation.value.trim() : '',
      relation: f.relation.value,
      partnerId: f.partnerId.value,
      language: f.language.value.trim(),
      diet: f.diet.value,
      notes: f.notes.value.trim(),
      isHost: f.isHost.checked,
      isCoHost: f.isCoHost.checked,
      needsInterpreter: f.needsInterpreter.checked,
      rankOverride: Number.isFinite(rankOverride) ? rankOverride : null,
    };

    if (!guest.firstName || !guest.lastName) return toast('Ad ve soyad zorunludur.');
    if (guest.relation !== 'principal' && !guest.partnerId) return toast('Eş/çocuk için bağlı olduğu kişiyi seçin.');
    if (guest.partnerId && createsCycle(id, guest.partnerId)) return toast('Döngüsel bağlantı oluşturulamaz.');
    if (guest.isHost && guest.isCoHost) return toast('Aynı kişi hem ev sahibi hem ikinci ev sahibi olamaz.');

    // Tekil roller.
    if (guest.isHost) state.guests.forEach((g) => (g.isHost = false));
    if (guest.isCoHost) state.guests.forEach((g) => (g.isCoHost = false));

    const idx = state.guests.findIndex((g) => g.id === id);
    if (idx === -1) state.guests.push(guest);
    else state.guests[idx] = guest;

    persist(true);
    toast(idx === -1 ? 'Davetli eklendi.' : 'Davetli güncellendi.');
    resetForm();
    renderGuests();
  }

  function deleteGuest(id) {
    const g = state.guests.find((x) => x.id === id);
    if (!g) return;
    const deps = state.guests.filter((x) => x.partnerId === id);
    const msg = deps.length
      ? `${fullName(g)} ve bağlı ${deps.length} kişi (${deps.map(fullName).join(', ')}) silinsin mi?`
      : `${fullName(g)} silinsin mi?`;
    if (!confirm(msg)) return;
    const remove = new Set([id, ...deps.map((d) => d.id)]);
    // Silinen bağımlıların bağımlıları bağlantısız kalır.
    state.guests = state.guests
      .filter((x) => !remove.has(x.id))
      .map((x) => (remove.has(x.partnerId) ? { ...x, partnerId: '' } : x));
    persist(true);
    resetForm();
    renderGuests();
  }

  /* ---------- Davetli listesi ---------- */

  function renderGuests() {
    const q = $('#guest-search').value.trim().toLocaleLowerCase('tr');
    const group = $('#guest-filter-group').value;
    const side = $('#guest-filter-side').value;
    const map = byId();
    const ranks = rankMap();

    const sorted = state.guests
      .slice()
      .sort((a, b) => Seating.effectiveRank(a, map, ranks) - Seating.effectiveRank(b, map, ranks) ||
        (a.lastName || '').localeCompare(b.lastName || '', 'tr'));

    const rows = sorted
      .map((g, i) => ({ g, order: i + 1 }))
      .filter(({ g }) => {
        if (side && (g.side || 'home') !== side) return false;
        if (group && CATEGORY_BY_ID.get(g.categoryId)?.group !== group) return false;
        if (!q) return true;
        const hay = [fullName(g), categoryLabel(g), g.delegation, g.notes, roleLabel(g, map)].join(' ').toLocaleLowerCase('tr');
        return hay.includes(q);
      });

    $('#guest-rows').innerHTML = rows
      .map(({ g, order }) => {
        const badges = [
          g.isHost ? '<span class="badge host">Ev sahibi</span>' : '',
          g.isCoHost ? '<span class="badge host">2. ev sahibi</span>' : '',
          g.needsInterpreter ? '<span class="badge">Tercüman</span>' : '',
        ].join('');
        const relation = g.relation && g.relation !== 'principal' ? RELATION_LABELS[g.relation] : isInterpreter(g) ? 'Tercüman' : 'Asıl';
        return `<tr class="${g.relation === 'principal' || !g.relation ? '' : 'dependent'}">
          <td class="num">${order}</td>
          <td><b>${esc(fullName(g))}</b> ${badges}${g.notes ? `<div class="muted">${esc(g.notes)}</div>` : ''}</td>
          <td>${esc(roleLabel(g, map))}</td>
          <td>${g.side === 'foreign' ? `<span class="pill foreign">${esc(g.delegation || 'Yabancı')}</span>` : '<span class="pill home">Yerli</span>'}</td>
          <td>${esc(relation)}</td>
          <td>${esc(DIET_LABELS[g.diet || ''] || g.diet)}</td>
          <td class="row-actions">
            <button type="button" data-edit="${esc(g.id)}" title="Düzenle">Düzenle</button>
            <button type="button" data-del="${esc(g.id)}" class="danger" title="Sil">Sil</button>
          </td>
        </tr>`;
      })
      .join('');

    $('#guest-empty').hidden = state.guests.length > 0;

    const count = (fn) => state.guests.filter(fn).length;
    $('#guest-stats').innerHTML = [
      ['Toplam', state.guests.length],
      ['Yerli', count((g) => g.side !== 'foreign')],
      ['Yabancı', count((g) => g.side === 'foreign')],
      ['Eş', count((g) => g.relation === 'spouse')],
      ['Çocuk', count((g) => g.relation === 'child')],
      ['Tercüman', count(isInterpreter)],
    ]
      .map(([k, v]) => `<span><b>${v}</b> ${k}</span>`)
      .join('');

    fillPartnerSelect($('#guest-form').guestId.value || null);
  }

  /* ---------- Oturma düzeni ---------- */

  function bindPlanOptions() {
    const f = $('#plan-options');
    const o = state.options;
    f.layout.value = o.layout;
    f.headSeats.value = o.headSeats;
    f.seatsPerTable.value = o.seatsPerTable;
    f.spouseMode.value = o.spouseMode;
    f.childrenTable.checked = o.childrenTable;
    f.mixDelegations.checked = o.mixDelegations;
    f.eventName.value = state.event.name;
    f.eventDate.value = state.event.date;
    f.eventPlace.value = state.event.place;
  }

  function readPlanOptions() {
    const f = $('#plan-options');
    const clamp = (v, d) => Math.min(40, Math.max(2, Math.floor(Number(v)) || d));
    state.options = {
      layout: f.layout.value,
      headSeats: clamp(f.headSeats.value, 10),
      seatsPerTable: clamp(f.seatsPerTable.value, 10),
      spouseMode: f.spouseMode.value,
      childrenTable: f.childrenTable.checked,
      mixDelegations: f.mixDelegations.checked,
    };
    state.event = { name: f.eventName.value.trim(), date: f.eventDate.value, place: f.eventPlace.value.trim() };
  }

  function generatePlan(e) {
    e.preventDefault();
    readPlanOptions();
    if (!state.guests.length) return toast('Önce davetli ekleyin.');
    state.plan = Seating.buildPlan(state.guests, rankMap(), state.options);
    state.planStale = false;
    selectedSeat = null;
    persist();
    renderPlan();
    toast(`${state.plan.tables.length} masa oluşturuldu.`);
  }

  /** Koltuk indeksinden "Sağ 1", "Sol 2" gibi protokol konumu üretir. */
  function seatPositions(table) {
    const withCo = table.anchors.b !== null && table.anchors.b !== undefined;
    const geo = table.layout === 'rect' ? Seating.rectArms(table.capacity, withCo) : Seating.roundArms(table.capacity, withCo);
    const anchorName = table.isHead ? 'Ev sahibi' : table.isChildren ? 'Masa başı' : 'Masa başkanı';
    const names = withCo
      ? ['Sağ', '2. ev sahibi sağı', 'Sol', '2. ev sahibi solu']
      : geo.arms.length === 4
        ? ['Sağ', 'Sol', 'Karşı sağ', 'Karşı sol']
        : ['Sağ', 'Sol'];
    const pos = {};
    pos[geo.anchorA] = anchorName;
    if (geo.anchorB !== null) pos[geo.anchorB] = '2. ev sahibi';
    geo.arms.forEach((arm, i) => arm.forEach((seat, k) => (pos[seat] = `${names[i]} ${k + 1}`)));
    return pos;
  }

  function seatCoords(table) {
    const n = table.capacity;
    if (table.layout === 'rect') {
      const { m, nb } = Seating.rectGeometry(n);
      const cols = Math.max(m, nb);
      const gap = 74;
      const width = cols * gap + 80;
      const coords = [];
      for (let i = 0; i < m; i++) coords.push({ x: 40 + gap / 2 + i * gap, y: 70, side: 'top' });
      for (let j = 0; j < nb; j++) coords.push({ x: 40 + gap / 2 + j * gap, y: 210, side: 'bottom' });
      return { coords, width, height: 280, shape: `<rect class="tbl" x="40" y="100" width="${cols * gap}" height="80" rx="8"/>` };
    }
    const R = Math.max(70, n * 9);
    const seatR = R + 32;
    const pad = 110;
    const size = (seatR + pad) * 2;
    const c = size / 2;
    const coords = [];
    for (let i = 0; i < n; i++) {
      // İndeks arttıkça ekranın soluna (ev sahibinin sağına) doğru.
      const a = -Math.PI / 2 - (i * 2 * Math.PI) / n;
      coords.push({ x: c + seatR * Math.cos(a), y: c + seatR * Math.sin(a), angle: a });
    }
    return { coords, width: size, height: size, shape: `<circle class="tbl" cx="${c}" cy="${c}" r="${R}"/>`, center: c };
  }

  function renderTable(table, map) {
    const { coords, width, height, shape, center } = seatCoords(table);
    const pos = seatPositions(table);
    const seats = table.seats
      .map((gid, i) => {
        const g = gid ? map.get(gid) : null;
        const { x, y } = coords[i];
        const sel = selectedSeat && selectedSeat.tableId === table.id && selectedSeat.index === i ? ' selected' : '';
        let label = '';
        if (g) {
          let lx = x;
          let ly = y;
          let anchor = 'middle';
          if (table.layout === 'rect') ly = coords[i].side === 'top' ? y - 28 : y + 36;
          else {
            const a = coords[i].angle;
            lx = x + Math.cos(a) * 26;
            ly = y + Math.sin(a) * 26 + 4;
            const dx = lx - center;
            anchor = Math.abs(dx) < 12 ? 'middle' : dx > 0 ? 'start' : 'end';
          }
          label = `<text class="seat-label" x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="${anchor}">${esc(shortName(g))}</text>`;
        }
        return `<g class="seat ${seatClass(g)}${sel}" data-table="${esc(table.id)}" data-seat="${i}" tabindex="0" role="button"
            aria-label="${esc(`${i + 1}. koltuk ${pos[i] || ''} ${g ? fullName(g) : 'boş'}`)}">
          <title>${esc(g ? `${fullName(g)} — ${roleLabel(g, map)}` : 'Boş koltuk')}</title>
          <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="17"/>
          <text class="seat-no" x="${x.toFixed(1)}" y="${(y + 4).toFixed(1)}" text-anchor="middle">${i + 1}</text>
          ${label}
        </g>`;
      })
      .join('');

    const list = table.seats
      .map((gid, i) => ({ g: gid ? map.get(gid) : null, i }))
      .sort((a, b) => protocolOrder(pos[a.i]) - protocolOrder(pos[b.i]))
      .map(({ g, i }) => {
        const sel = selectedSeat && selectedSeat.tableId === table.id && selectedSeat.index === i ? ' selected' : '';
        return `<li class="seat-row ${seatClass(g)}${sel}" data-table="${esc(table.id)}" data-seat="${i}">
          <span class="no">${i + 1}</span>
          <span class="pos">${esc(pos[i] || '')}</span>
          <span class="who">${g ? `<b>${esc(fullName(g))}</b><small>${esc(roleLabel(g, map))}${g.delegation ? ` · ${esc(g.delegation)}` : ''}${g.diet ? ` · ${esc(DIET_LABELS[g.diet] || g.diet)}` : ''}</small>` : '<i class="muted">Boş</i>'}</span>
        </li>`;
      })
      .join('');

    const filled = table.seats.filter(Boolean).length;
    return `<article class="card table-card${table.isHead ? ' head' : ''}">
      <h3>${esc(table.name)} <small>${filled}/${table.capacity} · ${table.layout === 'rect' ? 'Dikdörtgen' : 'Yuvarlak'}</small></h3>
      <svg viewBox="0 0 ${width} ${height}" class="table-svg" role="img" aria-label="${esc(table.name)} oturma şeması">${shape}${seats}</svg>
      <ol class="seat-list">${list}</ol>
    </article>`;
  }

  /** Listeyi protokol sırasında göstermek için konum etiketini sıralanabilir sayıya çevirir. */
  function protocolOrder(label = '') {
    if (/^(Ev sahibi|Masa)/.test(label)) return 0;
    if (label === '2. ev sahibi') return 0.5;
    const m = label.match(/(\d+)$/);
    const k = m ? Number(m[1]) : 99;
    const armRank = ['Sağ', '2. ev sahibi sağı', 'Sol', '2. ev sahibi solu', 'Karşı sağ', 'Karşı sol']
      .findIndex((p) => label.startsWith(`${p} `));
    return k * 10 + (armRank === -1 ? 9 : armRank);
  }

  function renderPlan() {
    bindPlanOptions();
    const plan = state.plan;
    const map = byId();
    $('#plan-stale').hidden = !(plan && state.planStale);
    const warnings = plan ? Seating.validate(state.guests) : [];
    const missing = plan ? state.guests.filter((g) => !plan.tables.some((t) => t.seats.includes(g.id))) : [];
    if (missing.length) warnings.unshift(`Yerleştirilmemiş davetli: ${missing.map(fullName).join(', ')}`);
    $('#plan-warnings').innerHTML = warnings.map((w) => `<li>${esc(w)}</li>`).join('');

    if (!plan) {
      $('#tables').innerHTML = '<p class="empty">Seçenekleri belirleyip <b>Düzeni Oluştur</b>’a basın.</p>';
      $('#kitchen').innerHTML = '';
      return;
    }
    $('#tables').innerHTML = plan.tables.map((t) => renderTable(t, map)).join('');
    renderKitchen(plan, map);

    const ev = state.event;
    $('#print-title').textContent = ev.name || 'Protokol Yemeği Oturma Planı';
    $('#print-sub').textContent = [ev.date && new Date(ev.date).toLocaleDateString('tr-TR'), ev.place].filter(Boolean).join(' · ');
  }

  function renderKitchen(plan, map) {
    const rows = plan.tables.map((t) => {
      const guests = t.seats.filter(Boolean).map((id) => map.get(id)).filter(Boolean);
      const diets = {};
      guests.forEach((g) => (diets[g.diet || ''] = (diets[g.diet || ''] || 0) + 1));
      const dietTxt = Object.entries(diets).map(([d, c]) => `${DIET_LABELS[d] || d}: ${c}`).join(', ');
      const notes = guests.filter((g) => g.notes).map((g) => `${fullName(g)}: ${g.notes}`);
      return `<tr><td>${esc(t.name)}</td><td class="num">${guests.length}</td><td>${esc(dietTxt)}</td><td>${notes.map(esc).join('<br>')}</td></tr>`;
    });
    $('#kitchen').innerHTML = `<h3>Servis / Mutfak Özeti</h3>
      <div class="table-wrap"><table class="data"><thead><tr><th>Masa</th><th>Kişi</th><th>Menü</th><th>Alerji / Not</th></tr></thead>
      <tbody>${rows.join('')}</tbody></table></div>`;
  }

  function onSeatClick(e) {
    const el = e.target.closest('[data-seat]');
    if (!el || !state.plan) return;
    const target = { tableId: el.dataset.table, index: Number(el.dataset.seat) };
    if (!selectedSeat) {
      selectedSeat = target;
    } else if (selectedSeat.tableId === target.tableId && selectedSeat.index === target.index) {
      selectedSeat = null;
    } else {
      const t1 = state.plan.tables.find((t) => t.id === selectedSeat.tableId);
      const t2 = state.plan.tables.find((t) => t.id === target.tableId);
      if (t1 && t2) {
        [t1.seats[selectedSeat.index], t2.seats[target.index]] = [t2.seats[target.index], t1.seats[selectedSeat.index]];
        persist();
        toast('Koltuklar değiştirildi.');
      }
      selectedSeat = null;
    }
    renderPlan();
  }

  function renderPlaceCards() {
    const map = byId();
    const cards = [];
    for (const t of state.plan?.tables || []) {
      for (const id of t.seats) {
        const g = id && map.get(id);
        if (!g) continue;
        cards.push(`<div class="place-card">
          <div class="pc-title">${esc(g.title || '')}</div>
          <div class="pc-name">${esc(`${g.firstName} ${g.lastName}`)}</div>
          <div class="pc-sub">${esc(g.relation === 'principal' || !g.relation ? categoryLabel(g) : '')}${g.delegation ? ` · ${esc(g.delegation)}` : ''}</div>
          <div class="pc-table">${esc(t.name)}</div>
        </div>`);
      }
    }
    $('#cards').innerHTML = cards.join('');
  }

  function print(mode) {
    if (!state.plan) return toast('Önce düzen oluşturun.');
    if (mode === 'cards') renderPlaceCards();
    document.body.dataset.print = mode;
    window.print();
  }

  /* ---------- Protokol sıralaması ---------- */

  function renderRanks() {
    const counts = {};
    state.guests.forEach((g) => (counts[g.categoryId] = (counts[g.categoryId] || 0) + 1));
    const ranks = rankMap();
    $('#rank-rows').innerHTML = CATEGORIES.slice()
      .sort((a, b) => ranks[a.id] - ranks[b.id])
      .map((c) => `<tr>
        <td>${esc(c.group)}</td>
        <td>${esc(c.label)}</td>
        <td><input type="number" step="0.1" data-rank="${esc(c.id)}" value="${ranks[c.id]}" class="${c.id in state.rankOverrides ? 'changed' : ''}" aria-label="${esc(c.label)} önceliği"></td>
        <td class="num">${counts[c.id] || ''}</td>
      </tr>`)
      .join('');
  }

  function onRankChange(e) {
    const input = e.target.closest('[data-rank]');
    if (!input) return;
    const id = input.dataset.rank;
    const v = Number(input.value);
    const def = CATEGORY_BY_ID.get(id).rank;
    if (input.value === '' || !Number.isFinite(v) || v === def) delete state.rankOverrides[id];
    else state.rankOverrides[id] = v;
    persist(true);
    renderRanks();
    renderGuests();
  }

  /* ---------- Veri ---------- */

  function exportJson() {
    const stamp = new Date().toISOString().slice(0, 10);
    download(`protokol-yemegi-${stamp}.json`, JSON.stringify(state, null, 2), 'application/json');
  }

  function importJson(e) {
    const file = e.target.files[0];
    e.target.value = '';
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = Store.normalize(JSON.parse(reader.result));
        if (state.guests.length && !confirm('Mevcut veriler içe aktarılan dosya ile değiştirilsin mi?')) return;
        state = data;
        persist();
        resetForm();
        renderAll();
        toast(`${state.guests.length} davetli içe aktarıldı.`);
      } catch {
        toast('Geçersiz JSON dosyası.');
      }
    };
    reader.readAsText(file);
  }

  function exportCsv() {
    if (!state.plan) return toast('Önce düzen oluşturun.');
    const map = byId();
    const cell = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const lines = [['Masa', 'Koltuk', 'Konum', 'Unvan', 'Ad', 'Soyad', 'Kategori/Rol', 'Taraf', 'Heyet', 'Menü', 'Not'].map(cell).join(';')];
    for (const t of state.plan.tables) {
      const pos = seatPositions(t);
      t.seats.forEach((id, i) => {
        const g = id && map.get(id);
        if (!g) return;
        lines.push([t.name, i + 1, pos[i], g.title, g.firstName, g.lastName, roleLabel(g, map),
          g.side === 'foreign' ? 'Yabancı' : 'Yerli', g.delegation, DIET_LABELS[g.diet || ''], g.notes].map(cell).join(';'));
      });
    }
    download('oturma-plani.csv', '﻿' + lines.join('\r\n'), 'text/csv;charset=utf-8');
  }

  function loadSample() {
    if (state.guests.length && !confirm('Mevcut davetli listesi örnek liste ile değiştirilsin mi?')) return;
    state.guests = structuredClone(window.SampleData.SAMPLE_GUESTS);
    state.event = { name: 'Azerbaycan Askerî Heyeti Onuruna Akşam Yemeği', date: '', place: 'Garnizon Orduevi' };
    state.plan = null;
    state.planStale = false;
    persist();
    resetForm();
    renderAll();
    toast('Örnek liste yüklendi.');
  }

  function clearAll() {
    if (!confirm('Tüm davetliler, ayarlar ve oturma planı silinecek. Emin misiniz?')) return;
    state = Store.defaultState();
    persist();
    resetForm();
    renderAll();
  }

  /* ---------- Başlatma ---------- */

  function renderAll() {
    renderGuests();
    renderRanks();
    renderPlan();
  }

  function init() {
    fillCategorySelect($('#guest-form [name=categoryId]'));
    $('#guest-filter-group').insertAdjacentHTML(
      'beforeend',
      Object.values(GROUPS).map((g) => `<option value="${esc(g)}">${esc(g)}</option>`).join(''),
    );

    $$('.tabs [role=tab]').forEach((b) => b.addEventListener('click', () => showTab(b.dataset.tab)));

    const form = $('#guest-form');
    form.addEventListener('submit', onSubmitGuest);
    form.addEventListener('change', (e) => {
      if (['side', 'relation', 'categoryId'].includes(e.target.name)) syncFormVisibility();
      // Yabancı heyet kategorisi seçilince taraf otomatik yabancı olur.
      if (e.target.name === 'categoryId' && CATEGORY_BY_ID.get(form.categoryId.value)?.group === GROUPS.YABANCI && form.categoryId.value !== 'tercuman') {
        form.side.value = 'foreign';
        syncFormVisibility();
      }
      // Eş/çocuk seçilen kişinin tarafını ve heyetini devralır.
      if (e.target.name === 'partnerId' && form.relation.value !== 'principal') {
        const p = state.guests.find((g) => g.id === form.partnerId.value);
        if (p) {
          form.side.value = p.side || 'home';
          form.delegation.value = p.delegation || '';
          syncFormVisibility();
        }
      }
    });
    $('#form-reset').addEventListener('click', resetForm);

    $('#guest-rows').addEventListener('click', (e) => {
      const edit = e.target.closest('[data-edit]');
      const del = e.target.closest('[data-del]');
      if (edit) editGuest(edit.dataset.edit);
      if (del) deleteGuest(del.dataset.del);
    });
    ['#guest-search', '#guest-filter-group', '#guest-filter-side'].forEach((s) => $(s).addEventListener('input', renderGuests));

    $('#plan-options').addEventListener('submit', generatePlan);
    $('#plan-options').addEventListener('change', () => {
      readPlanOptions();
      persist();
    });
    $('#tables').addEventListener('click', onSeatClick);
    $('#tables').addEventListener('keydown', (e) => {
      if ((e.key === 'Enter' || e.key === ' ') && e.target.closest('[data-seat]')) {
        e.preventDefault();
        onSeatClick(e);
      }
    });
    $('#print-plan').addEventListener('click', () => print('plan'));
    $('#print-cards').addEventListener('click', () => print('cards'));
    window.addEventListener('afterprint', () => delete document.body.dataset.print);

    $('#rank-rows').addEventListener('change', onRankChange);
    $('#ranks-reset').addEventListener('click', () => {
      if (!confirm('Tüm öncelik değerleri varsayılana dönsün mü?')) return;
      state.rankOverrides = {};
      persist(true);
      renderAll();
    });

    $('#export-json').addEventListener('click', exportJson);
    $('#import-json').addEventListener('change', importJson);
    $('#export-csv').addEventListener('click', exportCsv);
    $('#load-sample').addEventListener('click', loadSample);
    $('#clear-all').addEventListener('click', clearAll);

    resetForm();
    renderAll();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
