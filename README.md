# Postbot

Postiz benzeri, **yerelde çalışan** sosyal medya zamanlayıcı. Sıfır npm bağımlılığı (Node 22 yerleşik `node:sqlite`, `fetch`, `FormData`).

## Özellikler

- Haftalık takvim + liste görünümü, taslak / zamanla / şimdi paylaş
- Tek gönderiyi birden çok kanala yayınlama, platform bazlı karakter/görsel sınırı kontrolü
- Görsel yükleme (PNG/JPEG/GIF/WEBP, magic-byte doğrulamalı)
- Arka plan zamanlayıcı: üstel geri çekilmeli tekrar deneme (1m → 4m → 16m), 4xx hatalarında anında `failed`
- Çökme güvenliği: yayın ortasında kapanan hedefler tekrar gönderilmez, `failed` olarak işaretlenir (çift paylaşım yok)
- Kimlik bilgileri SQLite'ta AES-256-GCM ile şifreli
- Güvenlik: varsayılan `127.0.0.1`, DNS-rebinding/CSRF koruması, opsiyonel Basic Auth

| Platform | Kimlik doğrulama | Metin | Görsel |
|---|---|---|---|
| X (Twitter) | OAuth 1.0a (API Key/Secret + Access Token/Secret) | 280 | 4 |
| Bluesky | Handle + App Password | 300 | 4 |
| Mastodon | Sunucu URL + erişim jetonu | 500 | 4 |
| LinkedIn | Erişim jetonu + yazar URN | 3000 | – |
| Facebook Sayfası | Sayfa ID + sayfa jetonu | 63206 | 1 |
| Telegram | Bot token + chat ID | 4096 | 10 |
| Discord | Webhook URL | 2000 | 10 |
| Konsol (test) | – | – | 10 |

## Çalıştırma

```bash
node -v            # >= 22.13
cp .env.example .env
npm start          # http://127.0.0.1:3000
npm test
```

Docker:

```bash
docker compose up -d
```

## Mimari

```
src/
  index.js          bootstrap + graceful shutdown
  server.js         HTTP API + statik dosyalar + güvenlik korumaları
  scheduler.js      due hedefleri claim → publish → retry/backoff
  repository.js     SQLite şema + sorgular (channels, posts, post_targets)
  vault.js          AES-256-GCM kimlik bilgisi şifreleme
  media.js          görsel depolama
  providers/        platform adaptörleri: { verify(creds), publish(creds, {text, media}) }
public/             vanilla JS arayüz (build adımı yok)
```

Yeni platform: `src/providers/<ad>.js` içinde `{ id, name, maxLength, maxMedia, fields, verify, publish }` export edip `providers/index.js`'e kaydedin.

## API

| Metot | Yol | Açıklama |
|---|---|---|
| GET | `/api/providers` | Platformlar ve gerekli alanlar |
| GET/POST | `/api/channels` | Kanal listele / ekle |
| PATCH/DELETE | `/api/channels/:id` | Güncelle (ad, kimlik, `enabled`) / sil |
| POST | `/api/channels/:id/verify` | Bağlantı testi |
| GET | `/api/posts?from&to` | Gönderiler (ISO veya epoch ms) |
| POST | `/api/posts` | `{ content, media[], channelIds[], scheduledAt, draft }` |
| PUT/DELETE | `/api/posts/:id` | Düzenle / sil (yayınlanmışsa 409) |
| POST | `/api/posts/:id/publish` | Hemen yayınla |
| POST | `/api/posts/:id/retry` | Başarısız hedefleri yeniden kuyruğa al |
| POST | `/api/media` | Ham görsel gövdesi, `Content-Type: image/*` |

## Notlar

- Zamanlayıcı yalnızca uygulama çalışırken yayın yapar; kaçırılan gönderiler açılışta hemen gönderilir.
- `data/secret.key` (veya `APP_SECRET`) kaybolursa kayıtlı kimlik bilgileri çözülemez; yedekleyin.
- Instagram/Threads/TikTok herkese açık medya URL'si veya uygulama incelemesi gerektirdiğinden kapsam dışı.
