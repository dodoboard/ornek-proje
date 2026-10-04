/**
 * Protokol kategorileri ve varsayılan öncelik değerleri.
 * Düşük `rank` = yüksek protokol önceliği. Değerler Ayarlar sekmesinden düzenlenebilir.
 * Sıralama, mahalli (il/ilçe) protokol uygulamaları esas alınarak hazırlanmıştır;
 * kurum içi yönergeye göre güncellenmelidir.
 */
(function (root) {
  'use strict';

  const GROUPS = Object.freeze({
    MULKI: 'Mülki İdare',
    ASKERI: 'Askerî',
    YARGI: 'Yargı',
    YEREL: 'Yerel Yönetim',
    KAMU: 'Kamu Personeli',
    SIVIL: 'Sivil',
    YABANCI: 'Yabancı Heyet',
  });

  const CATEGORIES = Object.freeze([
    // Mülki idare
    { id: 'vali', label: 'Vali', group: GROUPS.MULKI, rank: 10 },
    { id: 'kaymakam', label: 'Kaymakam', group: GROUPS.MULKI, rank: 30 },
    { id: 'vali_yrd', label: 'Vali Yardımcısı', group: GROUPS.MULKI, rank: 50 },

    // Yasama
    { id: 'milletvekili', label: 'Milletvekili', group: GROUPS.MULKI, rank: 15 },

    // Askerî
    { id: 'garnizon_k', label: 'Garnizon Komutanı', group: GROUPS.ASKERI, rank: 20 },
    { id: 'kolordu_k', label: 'Kolordu / Tümen Komutanı', group: GROUPS.ASKERI, rank: 21 },
    { id: 'tugay_k', label: 'Tugay Komutanı', group: GROUPS.ASKERI, rank: 40 },
    { id: 'il_jandarma_k', label: 'İl Jandarma Komutanı', group: GROUPS.ASKERI, rank: 46 },
    { id: 'alay_k', label: 'Alay Komutanı', group: GROUPS.ASKERI, rank: 52 },
    { id: 'tabur_k', label: 'Tabur Komutanı', group: GROUPS.ASKERI, rank: 62 },
    { id: 'ilce_jandarma_k', label: 'İlçe Jandarma Komutanı', group: GROUPS.ASKERI, rank: 70 },
    { id: 'subay', label: 'Subay', group: GROUPS.ASKERI, rank: 80 },
    { id: 'astsubay', label: 'Astsubay / Uzman Personel', group: GROUPS.ASKERI, rank: 86 },

    // Yargı
    { id: 'adalet_kom_bsk', label: 'Adalet Komisyonu Başkanı', group: GROUPS.YARGI, rank: 35 },
    { id: 'bassavci', label: 'Cumhuriyet Başsavcısı', group: GROUPS.YARGI, rank: 36 },
    { id: 'agir_ceza_bsk', label: 'Ağır Ceza Mahkemesi Başkanı', group: GROUPS.YARGI, rank: 37 },
    { id: 'idare_mah_bsk', label: 'İdare Mahkemesi Başkanı', group: GROUPS.YARGI, rank: 38 },
    { id: 'hakim', label: 'Hâkim', group: GROUPS.YARGI, rank: 60 },
    { id: 'savci', label: 'Cumhuriyet Savcısı', group: GROUPS.YARGI, rank: 61 },
    { id: 'baro_bsk', label: 'Baro Başkanı', group: GROUPS.YARGI, rank: 66 },

    // Yerel yönetim
    { id: 'bb_bsk', label: 'Büyükşehir / İl Belediye Başkanı', group: GROUPS.YEREL, rank: 25 },
    { id: 'ilce_bel_bsk', label: 'İlçe Belediye Başkanı', group: GROUPS.YEREL, rank: 42 },
    { id: 'il_genel_mec', label: 'İl Genel Meclisi Başkanı', group: GROUPS.YEREL, rank: 55 },
    { id: 'muhtar', label: 'Muhtar', group: GROUPS.YEREL, rank: 90 },

    // Kamu
    { id: 'rektor', label: 'Rektör', group: GROUPS.KAMU, rank: 44 },
    { id: 'emniyet_md', label: 'İl Emniyet Müdürü', group: GROUPS.KAMU, rank: 47 },
    { id: 'il_mudur', label: 'İl Müdürü', group: GROUPS.KAMU, rank: 65 },
    { id: 'ilce_emniyet_md', label: 'İlçe Emniyet Müdürü', group: GROUPS.KAMU, rank: 71 },
    { id: 'ilce_mudur', label: 'İlçe Müdürü', group: GROUPS.KAMU, rank: 75 },
    { id: 'kamu_personeli', label: 'Kamu Personeli', group: GROUPS.KAMU, rank: 95 },

    // Sivil
    { id: 'stk', label: 'STK / Oda Başkanı', group: GROUPS.SIVIL, rank: 92 },
    { id: 'gazi_sehit', label: 'Gazi / Şehit Yakını', group: GROUPS.SIVIL, rank: 88 },
    { id: 'basin', label: 'Basın Mensubu', group: GROUPS.SIVIL, rank: 98 },
    { id: 'sivil', label: 'Sivil Davetli', group: GROUPS.SIVIL, rank: 100 },

    // Yabancı heyet
    { id: 'y_buyukelci', label: 'Büyükelçi / Başkonsolos', group: GROUPS.YABANCI, rank: 14 },
    { id: 'y_heyet_bsk', label: 'Yabancı Heyet Başkanı', group: GROUPS.YABANCI, rank: 18 },
    { id: 'y_komutan', label: 'Yabancı Komutan (General/Amiral)', group: GROUPS.YABANCI, rank: 22 },
    { id: 'y_atase', label: 'Askerî Ataşe', group: GROUPS.YABANCI, rank: 48 },
    { id: 'y_subay', label: 'Yabancı Subay', group: GROUPS.YABANCI, rank: 81 },
    { id: 'y_sivil', label: 'Yabancı Heyet Sivil Üyesi', group: GROUPS.YABANCI, rank: 82 },
    { id: 'tercuman', label: 'Tercüman', group: GROUPS.YABANCI, rank: 200 },
  ]);

  const RELATIONS = Object.freeze({
    PRINCIPAL: 'principal',
    SPOUSE: 'spouse',
    CHILD: 'child',
  });

  const RELATION_LABELS = Object.freeze({
    principal: 'Asıl Davetli',
    spouse: 'Eş',
    child: 'Çocuk',
  });

  const SIDES = Object.freeze({ HOME: 'home', FOREIGN: 'foreign' });

  const api = { GROUPS, CATEGORIES, RELATIONS, RELATION_LABELS, SIDES };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Catalog = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
