/** localStorage tabanlı kalıcı durum. Erişim engellenirse bellek içi çalışır. */
(function (root) {
  'use strict';

  const KEY = 'protokol-yemegi:v1';

  function defaultState() {
    return {
      version: 1,
      event: { name: '', date: '', place: '' },
      guests: [],
      rankOverrides: {},
      options: { ...root.Seating.DEFAULT_OPTIONS },
      plan: null,
      planStale: false,
    };
  }

  function load() {
    try {
      const raw = root.localStorage.getItem(KEY);
      if (!raw) return defaultState();
      return normalize(JSON.parse(raw));
    } catch {
      return defaultState();
    }
  }

  function save(state) {
    try {
      root.localStorage.setItem(KEY, JSON.stringify(state));
      return true;
    } catch {
      return false;
    }
  }

  /** Dışarıdan gelen veriyi beklenen şemaya oturtur. */
  function normalize(data) {
    const base = defaultState();
    if (!data || typeof data !== 'object') return base;
    const guests = Array.isArray(data.guests) ? data.guests.filter((g) => g && typeof g.id === 'string') : [];
    return {
      ...base,
      event: { ...base.event, ...(data.event || {}) },
      guests,
      rankOverrides: data.rankOverrides && typeof data.rankOverrides === 'object' ? data.rankOverrides : {},
      options: { ...base.options, ...(data.options || {}) },
      plan: data.plan && Array.isArray(data.plan.tables) ? data.plan : null,
      planStale: Boolean(data.planStale),
    };
  }

  root.Store = { load, save, normalize, defaultState };
})(globalThis);
