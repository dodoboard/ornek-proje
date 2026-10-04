# Protokol Yemeği Planlayıcı

Askerî protokol yemekleri için davetli listesi, protokol sıralaması ve oturma düzeni aracı. Bağımlılıksız; tarayıcıda çalışır, veriler `localStorage`'da tutulur.

## Çalıştırma

```bash
# Doğrudan: index.html dosyasını tarayıcıda açın
# veya
npm start      # http://localhost:8080
npm test       # oturma algoritması birim testleri
```

## Özellikler

- **Davetli türleri:** mülki amir (vali, kaymakam), askerî (garnizon/tugay/alay komutanı, subay), yargı (adalet komisyonu başkanı, başsavcı, hâkim), yerel yönetim (belediye başkanı, muhtar), kamu personeli, sivil, **yabancı heyet** (heyet başkanı, komutan, ataşe, subay, sivil üye, tercüman).
- **Bağlı kişiler:** eş, çocuk ve refakatçi/tercüman bir asıl davetliye bağlanır; bağlı kişi asıl davetlinin protokol önceliğini devralır.
- **Protokol sıralaması:** kategori bazlı, düzenlenebilir öncelik değerleri; kişi bazında manuel öncelik.
- **Oturma düzeni:**
  - Yuvarlak veya dikdörtgen (karşılıklı) masa.
  - Ev sahibi çapada; ikinci ev sahibi ya da ev sahibinin eşi karşısında (Fransız usulü).
  - Onur konuğu ev sahibinin sağına, sonrakiler sağ/sol dönüşümlü.
  - Karma oturma: yerli ve yabancı heyet dönüşümlü.
  - Eşler yan yana veya kendi protokol sırasıyla; ayrı çocuk masası seçeneği.
  - Tercüman daima tercümanlık yaptığı kişinin yanında.
  - İki koltuğa tıklayarak elle yer değiştirme.
- **Çıktılar:** plan yazdırma, yer kartları, servis/mutfak özeti (menü, alerji), CSV (Excel uyumlu) ve JSON yedek.

## Yapı

| Dosya | Görev |
|---|---|
| `js/catalog.js` | Kategoriler ve varsayılan öncelikler |
| `js/seating.js` | Saf oturma algoritması (Node ve tarayıcı) |
| `js/store.js` | Kalıcı durum |
| `js/app.js` | Arayüz |
| `tests/` | `node:test` birim testleri |

> Varsayılan öncelik değerleri mahalli protokol uygulamaları esas alınarak hazırlanmıştır; kurumunuzun yönergesine göre **Protokol Sıralaması** sekmesinden güncelleyin.
