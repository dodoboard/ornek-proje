/** Örnek davetli listesi (kurgusal isimler). */
(function (root) {
  'use strict';

  const p = (id, title, firstName, lastName, categoryId, extra = {}) => ({
    id, title, firstName, lastName, categoryId,
    side: 'home', relation: 'principal', partnerId: '', delegation: '', language: 'Türkçe',
    diet: '', notes: '', isHost: false, isCoHost: false, needsInterpreter: false, rankOverride: null,
    ...extra,
  });
  const spouse = (id, partnerId, firstName, lastName, extra = {}) =>
    p(id, '', firstName, lastName, 'sivil', { relation: 'spouse', partnerId, ...extra });
  const child = (id, partnerId, firstName, lastName, extra = {}) =>
    p(id, '', firstName, lastName, 'sivil', { relation: 'child', partnerId, diet: 'cocuk', ...extra });
  const foreign = { side: 'foreign', delegation: 'Azerbaycan', language: 'Azerbaycan Türkçesi' };

  const SAMPLE_GUESTS = [
    p('s01', 'Tümgeneral', 'Mehmet', 'Aksoy', 'garnizon_k', { isHost: true }),
    spouse('s02', 's01', 'Ayşe', 'Aksoy'),
    p('s03', '', 'Ahmet', 'Yılmaz', 'kaymakam'),
    spouse('s04', 's03', 'Zeynep', 'Yılmaz'),
    p('s05', '', 'Hasan', 'Demir', 'ilce_bel_bsk'),
    spouse('s06', 's05', 'Elif', 'Demir', { diet: 'vejetaryen' }),
    p('s07', '', 'Kemal', 'Arslan', 'adalet_kom_bsk'),
    p('s08', '', 'Murat', 'Şahin', 'bassavci'),
    spouse('s09', 's08', 'Fatma', 'Şahin'),
    p('s10', 'Albay', 'Serkan', 'Kaya', 'tugay_k'),
    spouse('s11', 's10', 'Derya', 'Kaya'),
    child('s12', 's10', 'Emir', 'Kaya'),
    p('s13', 'Yarbay', 'Okan', 'Çelik', 'ilce_jandarma_k'),
    p('s14', '', 'Selim', 'Öztürk', 'ilce_emniyet_md'),
    p('s15', '', 'Nur', 'Aydın', 'ilce_mudur'),
    p('s16', '', 'Ali', 'Koç', 'muhtar'),
    p('s17', '', 'Hüseyin', 'Polat', 'gazi_sehit'),
    p('s18', '', 'Burak', 'Tekin', 'stk', { notes: 'Fıstık alerjisi' }),

    p('f01', 'General-Mayor', 'Rauf', 'Aliyev', 'y_heyet_bsk', { ...foreign, needsInterpreter: true }),
    spouse('f02', 'f01', 'Leyla', 'Aliyeva', foreign),
    child('f03', 'f01', 'Nigar', 'Aliyeva', foreign),
    p('f04', 'Polkovnik', 'Elçin', 'Hüseynov', 'y_subay', foreign),
    p('f05', 'Polkovnik-Leytenant', 'Tural', 'Mammadov', 'y_subay', foreign),
    p('f06', '', 'Samir', 'Quliyev', 'y_sivil', { ...foreign, diet: 'glutensiz' }),
    p('f07', 'Albay', 'Kenan', 'Rzayev', 'y_atase', foreign),
    p('t01', '', 'Deniz', 'Ural', 'tercuman', { partnerId: 'f01', language: 'Türkçe / Azerbaycan Türkçesi' }),
  ];

  root.SampleData = { SAMPLE_GUESTS };
})(globalThis);
