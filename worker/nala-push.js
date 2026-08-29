/* Web push, RFC 8291 (aes128gcm) and RFC 8292 (VAPID), on WebCrypto only.

   Written against WebCrypto rather than a library because a Cloudflare Worker
   pasted into the dashboard cannot npm install. The same code runs in Node 18
   and above, which is how the encryption is tested: a payload is encrypted
   here and decrypted by an independent implementation, so the one part that
   cannot be tested against a real phone is at least proved correct.        */

const b64uToBytes = (s) => {
  s = s.replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};

const bytesToB64u = (b) => {
  let s = '';
  const a = new Uint8Array(b);
  for (let i = 0; i < a.length; i++) s += String.fromCharCode(a[i]);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); };

const concat = (...arrs) => {
  const total = arrs.reduce((n, a) => n + a.length, 0);
  const out = new Uint8Array(total);
  let o = 0;
  for (const a of arrs) { out.set(a, o); o += a.length; }
  return out;
};

const utf8 = (s) => new TextEncoder().encode(s);

async function hkdf(salt, ikm, info, length) {
  const key = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'HKDF', hash: 'SHA-256', salt, info }, key, length * 8);
  return new Uint8Array(bits);
}

/* The server's own ephemeral key agrees a secret with the browser's public
   key. A fresh pair per message is required: reusing one would let anyone who
   captured two messages relate them.                                       */
async function encryptPayload(payload, p256dhB64, authB64) {
  const clientPub = b64uToBytes(p256dhB64);
  const authSecret = b64uToBytes(authB64);

  const serverKeys = await crypto.subtle.generateKey(
    { name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const serverPubRaw = new Uint8Array(
    await crypto.subtle.exportKey('raw', serverKeys.publicKey));

  const clientKey = await crypto.subtle.importKey(
    'raw', clientPub, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits(
    { name: 'ECDH', public: clientKey }, serverKeys.privateKey, 256));

  /* RFC 8291: the auth secret salts a first HKDF whose info binds both public
     keys, so a key agreed with one browser cannot be replayed at another. */
  const prkInfo = concat(utf8('WebPush: info\0'), clientPub, serverPubRaw);
  const ikm = await hkdf(authSecret, shared, prkInfo, 32);

  const salt = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(salt, ikm, utf8('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(salt, ikm, utf8('Content-Encoding: nonce\0'), 12);

  const key = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  /* 0x02 is the final-record delimiter. A single record is enough: these
     payloads are a line of text, far inside the 4096 byte limit.         */
  const plaintext = concat(utf8(payload), new Uint8Array([0x02]));
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce }, key, plaintext));

  const rs = new Uint8Array(4);
  new DataView(rs.buffer).setUint32(0, 4096);
  return concat(salt, rs, new Uint8Array([serverPubRaw.length]), serverPubRaw, ciphertext); }

/* VAPID: a JWT signed with the private key, proving the sender is the same
   party the browser subscribed to.                                        */
async function vapidHeader(endpoint, publicKeyB64, privateKeyB64, subject) {
  const url = new URL(endpoint);
  const header = { typ: 'JWT', alg: 'ES256' };
  const claims = {
    aud: url.origin,
    exp: Math.floor(Date.now() / 1000) + 12 * 60 * 60,
    sub: subject
  };
  const signingInput = bytesToB64u(utf8(JSON.stringify(header))) + '.' +
                       bytesToB64u(utf8(JSON.stringify(claims)));

  const pub = b64uToBytes(publicKeyB64);
  const jwk = {
    kty: 'EC', crv: 'P-256',
    x: bytesToB64u(pub.slice(1, 33)),
    y: bytesToB64u(pub.slice(33, 65)),
    d: privateKeyB64.replace(/-/g, '+').replace(/_/g, '/')
         .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''),
    ext: true
  };
  const key = await crypto.subtle.importKey(
    'jwk', jwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const sig = new Uint8Array(await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' }, key, utf8(signingInput)));

  return {
    Authorization: 'vapid t=' + signingInput + '.' + bytesToB64u(sig) +
                   ', k=' + publicKeyB64
  };
}


/* ── the worker ────────────────────────────────────────────────
   Called by the phone that made the mark. It does not hold any database
   credential: it passes the caller's own Firebase ID token to the database,
   so the rules decide what may be read. An invalid or expired token gets a
   401 from Firebase and nothing is sent, which is the authentication.

   Secrets, set in the Cloudflare dashboard, never in the repo:
     VAPID_PRIVATE   the private half of the key pair
     VAPID_PUBLIC    the public half
     VAPID_SUBJECT   mailto: address, required by the spec
     DB              https://<project>-default-rtdb.<region>.firebasedatabase.app
*/

const CORS = {
  'Access-Control-Allow-Origin': 'https://menu.nalaresort.com',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS'
};

const reply = (status, obj) =>
  new Response(JSON.stringify(obj), { status, headers: { ...CORS, 'Content-Type': 'application/json' } });

/* Quiet hours are read from the database so they can be changed without
   redeploying. Times are compared in the resort's own clock, not the
   caller's: a phone left on another timezone must not decide this.      */
function inQuietHours(hours, now) {
  if (!hours || !hours.from || !hours.to) return false;
  const local = new Date(now.getTime() + 10 * 3600 * 1000);   // +10:00
  const mins = local.getUTCHours() * 60 + local.getUTCMinutes();
  const [fh, fm] = hours.from.split(':').map(Number);
  const [th, tm] = hours.to.split(':').map(Number);
  const from = fh * 60 + fm, to = th * 60 + tm;
  return from <= to ? (mins < from || mins >= to)      /* daytime window */
                    : (mins < from && mins >= to);     /* window crossing midnight */
}

/* One sentence per event, one meaning per sentence - the colour law's rule,
   applied to words. Until 29 Aug only departed had a case here and every
   other event fell through to "possibly available", so a villa marked
   cleaned or serviced buzzed as a room coming free, over and over, which is
   the mismatch this table ends. The spa texts are HANDOVER.md item 11's,
   verbatim.

   An event not named here still routes - the settings grid can hold events
   added later - and wears its own name rather than borrowing another
   meaning's sentence.

   The title stays the app's name on purpose: sw.js promotes the body to the
   bold line whenever the title is only "Nala Villas", and that promotion is
   deployed and pinned by tests/sw_test.js, so the fact travels in the body. */
const EVENTS = {
  departed:     { text: 'Villa {v} - guest departed',      url: '/cleaners.html' },
  available:    { text: 'Villa {v} - possibly available',  url: '/cleaners.html' },
  cleaned:      { text: 'Villa {v} - cleaned',             url: '/cleaners.html' },
  serviced:     { text: 'Villa {v} - serviced',            url: '/cleaners.html' },
  arriving:     { text: 'Villa {v} - guest due soon, nobody on the clean',
                  url: '/cleaners.html' },
  menu:         { text: "Tonight's menu is published",     url: '/' },
  spaRequest:   { text: 'Villa {v} - new massage request', url: '/spa.html' },
  spaSuggested: { text: 'Villa {v} - masseuse suggested a time, put it to the guest',
                  url: '/spa.html' },
  spaBooked:    { text: 'Villa {v} - massage booked',      url: '/spa.html' },
  spaCancelled: { text: 'Villa {v} - massage declined or cancelled',
                  url: '/spa.html' },
  spaStay:      { text: 'Villa {v} - stay cancelled or moved under a massage',
                  url: '/spa.html' }
};

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return new Response(null, { headers: CORS });
    if (request.method !== 'POST') return reply(405, { error: 'POST only' });

    let body;
    try { body = await request.json(); } catch { return reply(400, { error: 'bad json' }); }
    const { idToken, event, villa, actor } = body || {};
    if (!idToken || !event) return reply(400, { error: 'idToken and event required' });

    const db = env.DB.replace(/\/$/, '');
    const auth = '?auth=' + encodeURIComponent(idToken);

    const [subsRes, notifyRes] = await Promise.all([
      fetch(db + '/pushsubs.json' + auth),
      fetch(db + '/notify.json' + auth)
    ]);
    /* The database rejecting the token IS the authentication. There is no
       second check here that could disagree with the rules.            */
    if (!subsRes.ok || !notifyRes.ok) return reply(401, { error: 'not authorised' });

    const subs = (await subsRes.json()) || {};
    const cfg  = (await notifyRes.json()) || {};

    if (cfg.on === false) return reply(200, { sent: 0, skipped: 'notifications off' });
    if (inQuietHours(cfg.hours, new Date())) return reply(200, { sent: 0, skipped: 'quiet hours' });

    const wanted = (cfg.events && cfg.events[event]) || {};
    const known = EVENTS[event] || { text: 'Villa {v} - ' + event, url: '/cleaners.html' };
    const text = known.text.replace('{v}', villa == null ? '?' : villa);
    const payload = JSON.stringify({
      title: 'Nala Villas', body: text,
      /* Per villa, so ten marks on one villa replace rather than stack; the
         menu has no villa and gets the event's own name.                 */
      tag: villa == null ? event : 'villa-' + villa,
      url: known.url
    });

    const jobs = [];
    for (const emailKey in subs) {
      const devices = subs[emailKey] || {};
      for (const id in devices) {
        const s = devices[id];
        if (!s || !s.endpoint || !s.keys) continue;
        if (!wanted[s.role]) continue;
        /* Never tell someone about their own tap. */
        if (actor && emailKey === actor) continue;
        jobs.push(send(s, payload, env).then(
          ok => ({ emailKey, id, ok }),
          () => ({ emailKey, id, ok: false })));
      }
    }

    const results = await Promise.all(jobs);
    const gone = results.filter(r => r.ok === 'gone');
    /* A phone that has uninstalled the app returns 404 or 410 forever. Left
       alone these pile up and every send gets slower, so they are removed. */
    await Promise.all(gone.map(r =>
      fetch(db + '/pushsubs/' + r.emailKey + '/' + r.id + '.json' + auth, { method: 'DELETE' })
        .catch(() => {})));

    return reply(200, {
      sent: results.filter(r => r.ok === true).length,
      removed: gone.length,
      failed: results.filter(r => r.ok === false).length
    });
  }
};

async function send(sub, payload, env) {
  const cipher = await encryptPayload(payload, sub.keys.p256dh, sub.keys.auth);
  const vapid = await vapidHeader(sub.endpoint, env.VAPID_PUBLIC, env.VAPID_PRIVATE, env.VAPID_SUBJECT);
  const res = await fetch(sub.endpoint, {
    method: 'POST',
    headers: {
      ...vapid,
      'Content-Encoding': 'aes128gcm',
      'Content-Type': 'application/octet-stream',
      'TTL': '900'                       /* a villa mark is worthless in an hour */
    },
    body: cipher
  });
  if (res.status === 404 || res.status === 410) return 'gone';
  return res.ok;
}
