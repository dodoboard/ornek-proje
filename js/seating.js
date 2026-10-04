/**
 * Protokol oturma düzeni motoru (saf fonksiyonlar, DOM bağımsız).
 *
 * Kurallar:
 *  - Ev sahibi (isHost) onur masasının A çapasına oturur.
 *  - İkinci ev sahibi (isCoHost) yoksa ev sahibinin eşi karşısına (B çapası) oturur.
 *  - Onur konuğu ev sahibinin sağına, sonraki ikinci ev sahibinin sağına,
 *    ardından ev sahibinin soluna ... (Fransız usulü dönüşüm) yerleşir.
 *  - Karma oturma açıksa yabancı heyet ve yerli davetliler dönüşümlü sıralanır.
 *  - Bir kişiye bağlı refakatçi (ör. tercüman) daima o kişinin yanına oturur.
 */
(function (root) {
  'use strict';

  const DEFAULT_OPTIONS = Object.freeze({
    layout: 'round', // 'round' | 'rect'
    headSeats: 10,
    seatsPerTable: 10,
    spouseMode: 'together', // 'together' | 'byRank'
    childrenTable: true,
    mixDelegations: true,
  });

  const UNKNOWN_RANK = 999;
  const OFFSET = Object.freeze({ companion: 0.05, spouse: 0.1, child: 0.2 });

  const isSpouse = (g) => g.relation === 'spouse';
  const isChild = (g) => g.relation === 'child';
  const isCompanion = (g) => (!g.relation || g.relation === 'principal') && Boolean(g.partnerId);

  function indexById(guests) {
    const map = new Map();
    for (const g of guests) map.set(g.id, g);
    return map;
  }

  /** Bağlı kişilerde (eş/çocuk/refakatçi) ilgili asıl davetlinin önceliğini miras alır. */
  function effectiveRank(guest, byId, rankMap, depth = 0) {
    const partner = guest.partnerId ? byId.get(guest.partnerId) : null;
    if (partner && depth < 8) {
      const base = effectiveRank(partner, byId, rankMap, depth + 1);
      if (isSpouse(guest)) return base + OFFSET.spouse;
      if (isChild(guest)) return base + OFFSET.child;
      return base + OFFSET.companion;
    }
    if (Number.isFinite(guest.rankOverride)) return guest.rankOverride;
    const r = rankMap[guest.categoryId];
    return Number.isFinite(r) ? r : UNKNOWN_RANK;
  }

  function compareGuests(byId, rankMap) {
    const collator = new Intl.Collator('tr', { sensitivity: 'base' });
    return (a, b) =>
      effectiveRank(a, byId, rankMap) - effectiveRank(b, byId, rankMap) ||
      collator.compare(a.lastName || '', b.lastName || '') ||
      collator.compare(a.firstName || '', b.firstName || '') ||
      String(a.id).localeCompare(String(b.id));
  }

  /** Bir kişinin "kökü": bağlı olduğu en üst asıl davetli. Döngüye karşı korumalı. */
  function rootOf(guest, byId) {
    let cur = guest;
    const seen = new Set();
    while (cur.partnerId && byId.has(cur.partnerId) && !seen.has(cur.id)) {
      seen.add(cur.id);
      cur = byId.get(cur.partnerId);
    }
    return cur;
  }

  function interleave(a, b) {
    const out = [];
    const n = Math.max(a.length, b.length);
    for (let i = 0; i < n; i++) {
      if (i < a.length) out.push(a[i]);
      if (i < b.length) out.push(b[i]);
    }
    return out;
  }

  /** Davetlileri protokol sırasına göre oturma birimlerine (birlikte oturan gruplar) ayırır. */
  function buildUnits(guests, rankMap, options) {
    const byId = indexById(guests);
    const cmp = compareGuests(byId, rankMap);
    const host = guests.find((g) => g.isHost) || null;
    const explicitCoHost = guests.find((g) => g.isCoHost && g !== host) || null;
    const hostSpouse = host ? guests.find((g) => isSpouse(g) && g.partnerId === host.id) : null;
    const coHost = explicitCoHost || hostSpouse || null;

    const dependents = new Map(); // rootId -> Guest[]
    const roots = [];
    const childUnits = [];
    const extraUnits = [];

    for (const g of guests) {
      if (g === host || g === coHost) continue;
      const r = rootOf(g, byId);
      if (r === g) {
        roots.push(g);
        continue;
      }
      if (isChild(g) && options.childrenTable) {
        childUnits.push([g]);
        continue;
      }
      if (options.spouseMode === 'byRank' && (isSpouse(g) || isChild(g))) {
        extraUnits.push([g]);
        continue;
      }
      if (!dependents.has(r.id)) dependents.set(r.id, []);
      dependents.get(r.id).push(g);
    }

    // Birim içi sıra: asıl davetli, refakatçi, eş, çocuk.
    const memberOrder = (g) => (isCompanion(g) ? 0 : isSpouse(g) ? 1 : 2);
    const toUnit = (r) => {
      const deps = (dependents.get(r.id) || []).slice().sort((a, b) => memberOrder(a) - memberOrder(b) || cmp(a, b));
      return [r, ...deps];
    };

    const unitCmp = (u, v) => cmp(u[0], v[0]);
    let units = roots.filter((r) => r !== host).map(toUnit).concat(extraUnits).sort(unitCmp);

    if (options.mixDelegations) {
      const foreign = units.filter((u) => rootOf(u[0], byId).side === 'foreign');
      const home = units.filter((u) => rootOf(u[0], byId).side !== 'foreign');
      if (foreign.length && home.length) units = interleave(foreign, home);
    }

    // Ev sahibine bağlı kişiler (eş hariç — o karşı çapaya oturur).
    const hostUnit = host ? toUnit(host) : null;
    // İkinci ev sahibi (ör. eş) bağımlıları; kendisi B çapasında oturur.
    const coHostUnit = coHost ? [coHost, ...(dependents.get(coHost.id) || [])] : null;

    childUnits.sort(unitCmp);
    return { hostUnit, coHostUnit, units, childUnits, byId };
  }

  /* ---------- Masa geometrisi: çapalar ve kollar ---------- */

  function rangeSeq(from, to) {
    const out = [];
    const step = from <= to ? 1 : -1;
    for (let i = from; step > 0 ? i <= to : i >= to; i += step) out.push(i);
    return out;
  }

  /**
   * Yuvarlak masa: indeks 0 üstte (ev sahibi, aşağıya bakar). İndeks arttıkça ekranın
   * soluna doğru ilerler; bu, ev sahibinin SAĞ tarafıdır.
   */
  function roundArms(n, withCoHost) {
    if (n <= 1) return { anchorA: 0, anchorB: null, arms: [], leftArm: null, coLeftArm: null };
    if (!withCoHost) {
      const half = Math.ceil((n - 1) / 2);
      return {
        anchorA: 0,
        anchorB: null,
        arms: [rangeSeq(1, half), half + 1 <= n - 1 ? rangeSeq(n - 1, half + 1) : []],
        leftArm: 1,
        coLeftArm: null,
      };
    }
    const h = Math.floor(n / 2);
    const l1 = h - 1;
    const l2 = n - 1 - h;
    const hr = Math.ceil(l1 / 2);
    const cr = Math.ceil(l2 / 2);
    const hostRight = hr > 0 ? rangeSeq(1, hr) : [];
    const coLeft = l1 - hr > 0 ? rangeSeq(h - 1, hr + 1) : [];
    const coRight = cr > 0 ? rangeSeq(h + 1, h + cr) : [];
    const hostLeft = l2 - cr > 0 ? rangeSeq(n - 1, h + cr + 1) : [];
    return { anchorA: 0, anchorB: h, arms: [hostRight, coRight, hostLeft, coLeft], leftArm: 2, coLeftArm: 3 };
  }

  /**
   * Dikdörtgen masa: A kenarı (üst) 0..m-1 soldan sağa, B kenarı (alt) m..n-1 soldan sağa.
   * A kenarı aşağı baktığı için ev sahibinin sağı ekranın solu; B kenarında tersidir.
   */
  function rectGeometry(n) {
    const m = Math.ceil(n / 2);
    const nb = n - m;
    const ca = Math.floor((m - 1) / 2);
    const cb = nb > 0 ? Math.min(ca, nb - 1) : null;
    return { m, nb, ca, cb };
  }

  function rectArms(n, withCoHost) {
    const { m, nb, ca, cb } = rectGeometry(n);
    const aRight = ca - 1 >= 0 ? rangeSeq(ca - 1, 0) : [];
    const aLeft = ca + 1 <= m - 1 ? rangeSeq(ca + 1, m - 1) : [];
    if (cb === null) return { anchorA: ca, anchorB: null, arms: [aRight, aLeft], leftArm: 1, coLeftArm: null };
    const bRightCols = cb + 1 <= nb - 1 ? rangeSeq(cb + 1, nb - 1) : [];
    const bLeftCols = cb - 1 >= 0 ? rangeSeq(cb - 1, 0) : [];
    const bRight = bRightCols.map((c) => m + c);
    const bLeft = bLeftCols.map((c) => m + c);
    if (withCoHost) {
      return { anchorA: ca, anchorB: m + cb, arms: [aRight, bRight, aLeft, bLeft], leftArm: 2, coLeftArm: 3 };
    }
    // İkinci ev sahibi yoksa B merkezi, B-sağ kolunun ilk koltuğu olur.
    return { anchorA: ca, anchorB: null, arms: [aRight, aLeft, [m + cb, ...bRight], bLeft], leftArm: 1, coLeftArm: null };
  }

  function tableArms(layout, n, withCoHost) {
    return layout === 'rect' ? rectArms(n, withCoHost) : roundArms(n, withCoHost);
  }

  /* ---------- Yerleştirme ---------- */

  function fillTable(table, anchorUnit, coHostUnit, units) {
    const { anchorA, anchorB, arms, leftArm, coLeftArm } = tableArms(table.layout, table.capacity, Boolean(coHostUnit));
    const cursors = arms.map(() => 0);
    const remaining = (i) => arms[i].length - cursors[i];
    const put = (armIdx, guestId) => {
      table.seats[arms[armIdx][cursors[armIdx]++]] = guestId;
    };
    const freeArms = () => arms.map((_, i) => i).filter((i) => remaining(i) > 0);

    let turn = 0;
    const placeUnit = (unit) => {
      for (let k = 0; k < arms.length; k++) {
        const i = (turn + k) % arms.length;
        if (remaining(i) >= unit.length) {
          unit.forEach((g) => put(i, g.id));
          turn = i + 1;
          return;
        }
      }
      // Birim tek kola sığmıyorsa kollara bölünür.
      for (const g of unit) {
        const avail = freeArms();
        if (!avail.length) return;
        const i = avail.find((a) => a >= turn % arms.length) ?? avail[0];
        put(i, g.id);
      }
      turn += 1;
    };

    // Çapa biriminin artanları (refakatçi, eş) çapanın sol koluna yerleşir.
    const placeLeftovers = (rest, preferred) => {
      for (const g of rest) {
        const i = preferred !== null && remaining(preferred) > 0 ? preferred : freeArms()[0];
        if (i === undefined) return;
        put(i, g.id);
      }
    };

    if (anchorUnit && anchorUnit.length) {
      table.seats[anchorA] = anchorUnit[0].id;
      table.anchors.a = anchorA;
    }
    if (coHostUnit && anchorB !== null) {
      table.seats[anchorB] = coHostUnit[0].id;
      table.anchors.b = anchorB;
    }
    if (anchorUnit) placeLeftovers(anchorUnit.slice(1), leftArm);
    if (coHostUnit) placeLeftovers(coHostUnit.slice(1), coLeftArm);
    for (const u of units) placeUnit(u);
  }

  const unitSize = (u) => u.length;

  function chunk(unit, size) {
    const out = [];
    for (let i = 0; i < unit.length; i += size) out.push(unit.slice(i, i + size));
    return out;
  }

  /** Birimleri sırayı bozmadan masalara paketler. */
  function packTables(units, firstCapacity, capacity) {
    const groups = [];
    let cur = [];
    let free = firstCapacity;
    const flush = () => {
      if (cur.length) groups.push(cur);
      cur = [];
      free = capacity;
    };
    const add = (unit) => {
      if (unitSize(unit) > free) flush();
      cur.push(unit);
      free -= unitSize(unit);
    };
    for (const unit of units) {
      if (unitSize(unit) <= free || unitSize(unit) <= capacity) add(unit);
      else chunk(unit, capacity).forEach(add);
    }
    flush();
    return groups;
  }

  function newTable(id, name, layout, capacity, flags) {
    return {
      id,
      name,
      layout,
      capacity,
      seats: Array(capacity).fill(null),
      anchors: { a: null, b: null },
      isHead: false,
      isChildren: false,
      ...flags,
    };
  }

  function buildPlan(guests, rankMap, userOptions) {
    const options = { ...DEFAULT_OPTIONS, ...(userOptions || {}) };
    const headSeats = Math.max(2, Math.floor(options.headSeats));
    const seats = Math.max(2, Math.floor(options.seatsPerTable));
    const { hostUnit, coHostUnit, units, childUnits } = buildUnits(guests, rankMap, options);

    const tables = [];
    let queue = units.slice();
    let tableNo = 1;

    if (hostUnit || coHostUnit) {
      const reserved = (hostUnit ? hostUnit.length : 0) + (coHostUnit ? coHostUnit.length : 0);
      const capacity = Math.max(headSeats, reserved);
      const head = newTable(`t${tableNo}`, 'Onur Masası', options.layout, capacity, { isHead: true });
      let free = capacity - reserved;
      const seated = [];
      while (queue.length && unitSize(queue[0]) <= free) {
        free -= unitSize(queue[0]);
        seated.push(queue.shift());
      }
      const anchor = hostUnit || coHostUnit;
      fillTable(head, anchor, hostUnit ? coHostUnit : null, seated);
      tables.push(head);
      tableNo++;
    }

    const firstCap = tables.length ? seats : headSeats;
    for (const group of packTables(queue, firstCap, seats)) {
      const isHead = tables.length === 0;
      const name = isHead ? 'Onur Masası' : `Masa ${tableNo}`;
      const t = newTable(`t${tableNo}`, name, options.layout, isHead ? headSeats : seats, { isHead });
      fillTable(t, group[0], null, group.slice(1));
      tables.push(t);
      tableNo++;
    }

    let childNo = 1;
    for (const group of packTables(childUnits, seats, seats)) {
      const t = newTable(`c${childNo}`, `Çocuk Masası ${childNo}`, options.layout, seats, { isChildren: true });
      fillTable(t, group[0], null, group.slice(1));
      tables.push(t);
      childNo++;
    }

    return { tables, options, warnings: validate(guests), createdAt: new Date().toISOString() };
  }

  /** Veri tutarlılığı uyarıları. */
  function validate(guests) {
    const byId = indexById(guests);
    const warnings = [];
    const name = (g) => `${g.firstName || ''} ${g.lastName || ''}`.trim() || g.id;
    const hosts = guests.filter((g) => g.isHost);

    if (guests.length && !hosts.length) warnings.push('Ev sahibi işaretlenmedi; en kıdemli davetli onur masasına çapa olarak oturtulur.');
    if (hosts.length > 1) warnings.push(`Birden fazla ev sahibi işaretli (${hosts.map(name).join(', ')}); yalnızca ilki dikkate alınır.`);

    for (const g of guests) {
      if (g.partnerId && !byId.has(g.partnerId)) warnings.push(`${name(g)}: bağlı olduğu kişi listede yok.`);
      if ((isSpouse(g) || isChild(g)) && !g.partnerId) warnings.push(`${name(g)}: eş/çocuk kaydı bir davetliye bağlanmamış.`);
      if (g.categoryId === 'tercuman' && !g.partnerId) warnings.push(`${name(g)}: tercüman bir heyet üyesine atanmamış.`);
      if (g.partnerId === g.id) warnings.push(`${name(g)}: kendisine bağlanamaz.`);
      if (g.needsInterpreter) {
        const has = guests.some((x) => x.categoryId === 'tercuman' && x.partnerId === g.id);
        if (!has) warnings.push(`${name(g)}: tercüman ihtiyacı var ancak atanmış tercüman yok.`);
      }
    }
    return warnings;
  }

  const api = {
    DEFAULT_OPTIONS,
    effectiveRank,
    buildUnits,
    buildPlan,
    validate,
    roundArms,
    rectArms,
    rectGeometry,
    rootOf,
    indexById,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Seating = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
