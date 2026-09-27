import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createVault } from '../src/vault.js';
import { oauthHeader } from '../src/providers/x.js';
import { buildFacets } from '../src/providers/bluesky.js';
import { toLittleText } from '../src/providers/linkedin.js';
import { derivePostStatus } from '../src/repository.js';
import { backoff } from '../src/scheduler.js';

test('vault round-trips and rejects tampering', () => {
  const vault = createVault('secret');
  const sealed = vault.seal({ token: 'abc' });
  assert.deepEqual(vault.open(sealed), { token: 'abc' });
  assert.notEqual(vault.seal({ token: 'abc' }), sealed, 'IV must be random');

  const buf = Buffer.from(sealed, 'base64');
  buf[buf.length - 1] ^= 1;
  assert.throws(() => vault.open(buf.toString('base64')));
  assert.throws(() => createVault('other').open(sealed));
});

test('X OAuth 1.0a signature matches the reference vector', () => {
  // https://developer.x.com/en/docs/authentication/oauth-1-0a/creating-a-signature
  const header = oauthHeader(
    'POST',
    'https://api.twitter.com/1.1/statuses/update.json?include_entities=true',
    {
      apiKey: 'xvz1evFS4wEEPTGEFPHBog',
      apiSecret: 'kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw',
      accessToken: '370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb',
      accessTokenSecret: 'LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE',
    },
    { status: 'Hello Ladies + Gentlemen, a signed OAuth request!' },
    { nonce: 'kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg', timestamp: '1318622958' },
  );
  assert.match(header, /oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"/);
});

test('Bluesky facets use UTF-8 byte offsets', () => {
  const text = 'Çok güzel 🎉 https://örnek.com/a. #yazılım';
  const facets = buildFacets(text);
  const bytes = new TextEncoder().encode(text);
  const slice = ({ index }) => new TextDecoder().decode(bytes.slice(index.byteStart, index.byteEnd));

  assert.equal(facets.length, 2);
  assert.equal(slice(facets[0]), 'https://örnek.com/a');
  assert.equal(facets[0].features[0].uri, 'https://örnek.com/a');
  assert.equal(slice(facets[1]), '#yazılım');
  assert.equal(facets[1].features[0].tag, 'yazılım');
});

test('LinkedIn little text escapes reserved chars and templates hashtags', () => {
  assert.equal(toLittleText('Merhaba (dünya) @ali #yeni_ürün *x*'),
    'Merhaba \\(dünya\\) \\@ali {hashtag|\\#|yeni_ürün} \\*x\\*');
});

test('post status derivation', () => {
  const s = (...statuses) => derivePostStatus({ draft: false, targets: statuses.map((status) => ({ status })) });
  assert.equal(derivePostStatus({ draft: true, targets: [] }), 'draft');
  assert.equal(s('queued', 'queued'), 'scheduled');
  assert.equal(s('published', 'published'), 'published');
  assert.equal(s('published', 'failed'), 'partial');
  assert.equal(s('failed'), 'failed');
  assert.equal(s('publishing', 'queued'), 'publishing');
  assert.equal(s('published', 'queued'), 'partial');
});

test('backoff grows and caps', () => {
  assert.deepEqual([1, 2, 3].map(backoff), [60_000, 240_000, 960_000]);
  assert.equal(backoff(10), 3_600_000);
});
