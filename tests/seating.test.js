'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { CATEGORIES } = require('../js/catalog.js');
const S = require('../js/seating.js');

const RANKS = Object.fromEntries(CATEGORIES.map((c) => [c.id, c.rank]));

let seq = 0;
const g = (categoryId, extra = {}) => ({
  id: extra.id || `g${++seq}`,
  firstName: extra.firstName || categoryId,
  lastName: extra.lastName || String(seq),
  categoryId,
  relation: 'principal',
  side: 'home',
  ...extra,
});

const seatOf = (plan, id) => {
  for (const t of plan.tables) {
    const i = t.seats.indexOf(id);
    if (i !== -1) return { table: t, index: i };
  }
  return null;
};

test('eş ve çocuk asıl davetlinin önceliğini miras alır', () => {
  const kay = g('kaymakam', { id: 'k' });
  const es = g('sivil', { id: 'e', relation: 'spouse', partnerId: 'k' });
  const cocuk = g('sivil', { id: 'c', relation: 'child', partnerId: 'k' });
  const byId = S.indexById([kay, es, cocuk]);
  assert.equal(S.effectiveRank(es, byId, RANKS), RANKS.kaymakam + 0.1);
  assert.equal(S.effectiveRank(cocuk, byId, RANKS), RANKS.kaymakam + 0.2);
});

test('rankOverride kategori önceliğini ezer', () => {
  const x = g('sivil', { rankOverride: 1 });
  assert.equal(S.effectiveRank(x, S.indexById([x]), RANKS), 1);
});

test('döngüsel bağlantı sonsuz döngüye girmez', () => {
  const a = g('sivil', { id: 'a', partnerId: 'b' });
  const b = g('sivil', { id: 'b', partnerId: 'a' });
  const plan = S.buildPlan([a, b], RANKS, {});
  const seated = plan.tables.flatMap((t) => t.seats).filter(Boolean);
  assert.equal(seated.length, 2);
});

test('yuvarlak masa: onur konuğu ev sahibinin sağına, ikinci kişi soluna', () => {
  const host = g('garnizon_k', { id: 'h', isHost: true });
  const vali = g('vali', { id: 'v' });
  const bel = g('bb_bsk', { id: 'b' });
  const plan = S.buildPlan([host, vali, bel], RANKS, { layout: 'round', headSeats: 8, mixDelegations: false });
  const t = plan.tables[0];
  assert.equal(t.seats[0], 'h');
  assert.equal(t.seats[1], 'v'); // sağ
  assert.equal(t.seats[7], 'b'); // sol
});

test('ev sahibinin eşi karşı çapaya oturur (Fransız usulü)', () => {
  const host = g('garnizon_k', { id: 'h', isHost: true });
  const es = g('sivil', { id: 'hs', relation: 'spouse', partnerId: 'h' });
  const others = ['vali', 'bb_bsk', 'kaymakam', 'bassavci'].map((c, i) => g(c, { id: `o${i}` }));
  const plan = S.buildPlan([host, es, ...others], RANKS, { layout: 'round', headSeats: 10, mixDelegations: false });
  const t = plan.tables[0];
  assert.equal(t.seats[0], 'h');
  assert.equal(t.seats[5], 'hs');
  assert.equal(t.seats[1], 'o0'); // ev sahibinin sağı
  assert.equal(t.seats[6], 'o1'); // ikinci ev sahibinin sağı
  assert.equal(t.seats[9], 'o2'); // ev sahibinin solu
  assert.equal(t.seats[4], 'o3'); // ikinci ev sahibinin solu
});

test('dikdörtgen masa: ev sahibi A ortasında, eşi B ortasında', () => {
  const host = g('garnizon_k', { id: 'h', isHost: true });
  const es = g('sivil', { id: 'hs', relation: 'spouse', partnerId: 'h' });
  const vali = g('vali', { id: 'v' });
  const plan = S.buildPlan([host, es, vali], RANKS, { layout: 'rect', headSeats: 10 });
  const t = plan.tables[0];
  const { m, ca, cb } = S.rectGeometry(10);
  assert.equal(t.seats[ca], 'h');
  assert.equal(t.seats[m + cb], 'hs');
  assert.equal(t.seats[ca - 1], 'v');
});

test('karma oturma: yabancı heyet başkanı onur konuğu olur', () => {
  const host = g('garnizon_k', { id: 'h', isHost: true });
  const vali = g('vali', { id: 'v' });
  const heyet = g('y_heyet_bsk', { id: 'y', side: 'foreign' });
  const plan = S.buildPlan([host, vali, heyet], RANKS, { layout: 'round', headSeats: 8, mixDelegations: true });
  assert.equal(plan.tables[0].seats[1], 'y');
});

test('tercüman bağlı olduğu kişinin hemen yanına oturur', () => {
  const host = g('garnizon_k', { id: 'h', isHost: true });
  const heyet = g('y_heyet_bsk', { id: 'y', side: 'foreign', needsInterpreter: true });
  const terc = g('tercuman', { id: 'tr', partnerId: 'y' });
  const plan = S.buildPlan([host, heyet, terc], RANKS, { layout: 'round', headSeats: 8 });
  const t = plan.tables[0];
  assert.equal(t.seats[1], 'y');
  assert.equal(t.seats[2], 'tr');
  assert.ok(!plan.warnings.some((w) => w.includes('tercüman ihtiyacı')));
});

test('çocuk masası seçeneği çocukları ayrı masaya alır', () => {
  const host = g('garnizon_k', { id: 'h', isHost: true });
  const c1 = g('sivil', { id: 'c1', relation: 'child', partnerId: 'h' });
  const plan = S.buildPlan([host, c1], RANKS, { childrenTable: true });
  const s = seatOf(plan, 'c1');
  assert.ok(s.table.isChildren);
  const plan2 = S.buildPlan([host, c1], RANKS, { childrenTable: false });
  assert.ok(!seatOf(plan2, 'c1').table.isChildren);
});

test('herkes tam bir kez oturtulur; kapasite aşılmaz', () => {
  const list = [g('garnizon_k', { id: 'h', isHost: true })];
  for (let i = 0; i < 37; i++) {
    const p = g(CATEGORIES[i % CATEGORIES.length].id, { side: i % 3 ? 'home' : 'foreign' });
    list.push(p);
    if (i % 2) list.push(g('sivil', { relation: 'spouse', partnerId: p.id }));
    if (i % 5 === 0) list.push(g('sivil', { relation: 'child', partnerId: p.id }));
  }
  for (const layout of ['round', 'rect']) {
    for (const spouseMode of ['together', 'byRank']) {
      for (const childrenTable of [true, false]) {
        const plan = S.buildPlan(list, RANKS, { layout, spouseMode, childrenTable, headSeats: 12, seatsPerTable: 8 });
        const ids = plan.tables.flatMap((t) => t.seats).filter(Boolean);
        assert.equal(ids.length, list.length, `${layout}/${spouseMode}/${childrenTable}`);
        assert.equal(new Set(ids).size, list.length);
        for (const t of plan.tables) assert.equal(t.seats.length, t.capacity);
      }
    }
  }
});

test('kol geometrisi tüm koltukları tam bir kez kapsar', () => {
  for (let n = 2; n <= 24; n++) {
    for (const co of [true, false]) {
      for (const fn of [S.roundArms, S.rectArms]) {
        const r = fn(n, co);
        const all = [r.anchorA, ...(r.anchorB === null ? [] : [r.anchorB]), ...r.arms.flat()];
        assert.equal(all.length, n, `${fn.name} n=${n} co=${co}`);
        assert.equal(new Set(all).size, n);
      }
    }
  }
});

test('doğrulama uyarıları', () => {
  const w = S.validate([g('tercuman'), g('sivil', { relation: 'spouse' }), g('sivil', { partnerId: 'yok' })]);
  assert.ok(w.some((x) => x.includes('Ev sahibi')));
  assert.ok(w.some((x) => x.includes('tercüman bir heyet')));
  assert.ok(w.some((x) => x.includes('bağlanmamış')));
  assert.ok(w.some((x) => x.includes('listede yok')));
});
