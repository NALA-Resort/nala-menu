/* NALA key-card endpoints, served by the mews-sync Worker.
 *
 * The desk PC's encoder helper needs two things from TTLock's cloud before
 * it can write a card: hotelInfo (a credential string their servers mint,
 * valid ten minutes) and the villa -> lock table. Both require the TTLock
 * secrets, and the whole point of this file is that those secrets live in
 * the Cloudflare dashboard and NEVER on the desk PC: the helper holds one
 * key, HELPER_KEY, which unlocks only these two read-only relays. A stolen
 * desk PC then carries nothing durable.
 *
 *   GET /cardauth    -> { ok, hotelInfo, ttl }
 *   GET /cardlocks   -> { ok, locks: { "9": { mac, lockId, buildNo, floorNo } }, extras }
 *
 * Secrets to set in the Cloudflare dashboard, exactly these names:
 *   HELPER_KEY       any long random string, also typed into the helper once
 *   TT_CLIENT_ID     client_id from TTHotel Pro's Integration page
 *   TT_CLIENT_SECRET client_secret from the same page (View)
 *   TT_ACCOUNT       the Account there, h_<digits>
 *   TT_PASSWORD      the Password there. Plain: it is md5'd before sending,
 *                    because that is what TTLock's oauth wants. A 32-hex
 *                    value is taken as already hashed.
 *
 * The base URL is the manual's (euapi.ttlock.com); TT_BASE overrides it if
 * their region routing ever says otherwise.
 *
 * The lock-list field names below match their export file and cannot be
 * verified from the sandbox (egress blocked, HANDOVER.md); the reads are
 * written tolerantly and the first live call is the test.
 */

const TT_BASE_DEFAULT = "https://euapi.ttlock.com";

/* Workers' crypto.subtle has no MD5, and TTLock's oauth wants the password
   as one, so here is the algorithm itself. Public-domain construction; the
   suite pins it to the RFC 1321 vectors, which is the only review it needs. */
export function md5(str) {
  const rl = (n, c) => (n << c) | (n >>> (32 - c));
  const add = (a, b) => (a + b) | 0;
  const bytes = new TextEncoder().encode(str);
  const nblk = ((bytes.length + 8) >> 6) + 1;
  const blks = new Int32Array(nblk * 16);
  for (let i = 0; i < bytes.length; i++) blks[i >> 2] |= bytes[i] << ((i % 4) * 8);
  blks[bytes.length >> 2] |= 0x80 << ((bytes.length % 4) * 8);
  blks[nblk * 16 - 2] = bytes.length * 8;

  let a = 1732584193, b = -271733879, c = -1732584194, d = 271733878;
  const C = (q, a2, b2, x, s, t) => add(rl(add(add(a2, q), add(x, t)), s), b2);
  const FF = (a2, b2, c2, d2, x, s, t) => C((b2 & c2) | (~b2 & d2), a2, b2, x, s, t);
  const GG = (a2, b2, c2, d2, x, s, t) => C((b2 & d2) | (c2 & ~d2), a2, b2, x, s, t);
  const HH = (a2, b2, c2, d2, x, s, t) => C(b2 ^ c2 ^ d2, a2, b2, x, s, t);
  const II = (a2, b2, c2, d2, x, s, t) => C(c2 ^ (b2 | ~d2), a2, b2, x, s, t);

  for (let i = 0; i < blks.length; i += 16) {
    const oa = a, ob = b, oc = c, od = d, x = blks.subarray(i, i + 16);
    a = FF(a, b, c, d, x[0], 7, -680876936);   d = FF(d, a, b, c, x[1], 12, -389564586);
    c = FF(c, d, a, b, x[2], 17, 606105819);   b = FF(b, c, d, a, x[3], 22, -1044525330);
    a = FF(a, b, c, d, x[4], 7, -176418897);   d = FF(d, a, b, c, x[5], 12, 1200080426);
    c = FF(c, d, a, b, x[6], 17, -1473231341); b = FF(b, c, d, a, x[7], 22, -45705983);
    a = FF(a, b, c, d, x[8], 7, 1770035416);   d = FF(d, a, b, c, x[9], 12, -1958414417);
    c = FF(c, d, a, b, x[10], 17, -42063);     b = FF(b, c, d, a, x[11], 22, -1990404162);
    a = FF(a, b, c, d, x[12], 7, 1804603682);  d = FF(d, a, b, c, x[13], 12, -40341101);
    c = FF(c, d, a, b, x[14], 17, -1502002290);b = FF(b, c, d, a, x[15], 22, 1236535329);
    a = GG(a, b, c, d, x[1], 5, -165796510);   d = GG(d, a, b, c, x[6], 9, -1069501632);
    c = GG(c, d, a, b, x[11], 14, 643717713);  b = GG(b, c, d, a, x[0], 20, -373897302);
    a = GG(a, b, c, d, x[5], 5, -701558691);   d = GG(d, a, b, c, x[10], 9, 38016083);
    c = GG(c, d, a, b, x[15], 14, -660478335); b = GG(b, c, d, a, x[4], 20, -405537848);
    a = GG(a, b, c, d, x[9], 5, 568446438);    d = GG(d, a, b, c, x[14], 9, -1019803690);
    c = GG(c, d, a, b, x[3], 14, -187363961);  b = GG(b, c, d, a, x[8], 20, 1163531501);
    a = GG(a, b, c, d, x[13], 5, -1444681467); d = GG(d, a, b, c, x[2], 9, -51403784);
    c = GG(c, d, a, b, x[7], 14, 1735328473);  b = GG(b, c, d, a, x[12], 20, -1926607734);
    a = HH(a, b, c, d, x[5], 4, -378558);      d = HH(d, a, b, c, x[8], 11, -2022574463);
    c = HH(c, d, a, b, x[11], 16, 1839030562); b = HH(b, c, d, a, x[14], 23, -35309556);
    a = HH(a, b, c, d, x[1], 4, -1530992060);  d = HH(d, a, b, c, x[4], 11, 1272893353);
    c = HH(c, d, a, b, x[7], 16, -155497632);  b = HH(b, c, d, a, x[10], 23, -1094730640);
    a = HH(a, b, c, d, x[13], 4, 681279174);   d = HH(d, a, b, c, x[0], 11, -358537222);
    c = HH(c, d, a, b, x[3], 16, -722521979);  b = HH(b, c, d, a, x[6], 23, 76029189);
    a = HH(a, b, c, d, x[9], 4, -640364487);   d = HH(d, a, b, c, x[12], 11, -421815835);
    c = HH(c, d, a, b, x[15], 16, 530742520);  b = HH(b, c, d, a, x[2], 23, -995338651);
    a = II(a, b, c, d, x[0], 6, -198630844);   d = II(d, a, b, c, x[7], 10, 1126891415);
    c = II(c, d, a, b, x[14], 15, -1416354905);b = II(b, c, d, a, x[5], 21, -57434055);
    a = II(a, b, c, d, x[12], 6, 1700485571);  d = II(d, a, b, c, x[3], 10, -1894986606);
    c = II(c, d, a, b, x[10], 15, -1051523);   b = II(b, c, d, a, x[1], 21, -2054922799);
    a = II(a, b, c, d, x[8], 6, 1873313359);   d = II(d, a, b, c, x[15], 10, -30611744);
    c = II(c, d, a, b, x[6], 15, -1560198380); b = II(b, c, d, a, x[13], 21, 1309151649);
    a = II(a, b, c, d, x[4], 6, -145523070);   d = II(d, a, b, c, x[11], 10, -1120210379);
    c = II(c, d, a, b, x[2], 15, 718787259);   b = II(b, c, d, a, x[9], 21, -343485551);
    a = add(a, oa); b = add(b, ob); c = add(c, oc); d = add(d, od);
  }
  return [a, b, c, d].map(n =>
    Array.from({ length: 4 }, (_, i) =>
      ((n >> (i * 8)) & 255).toString(16).padStart(2, "0")).join("")
  ).join("");
}

const base = env => (env.TT_BASE || TT_BASE_DEFAULT).replace(/\/$/, "");

function json(status, body) {
  return new Response(JSON.stringify(body),
    { status, headers: { "Content-Type": "application/json" } });
}

/* The helper's key, checked the way the Zap secret is: trimmed both sides,
   refused with lengths only - they say missing, truncated or different, and
   cannot be used to reconstruct it. */
function helperAllowed(request, env) {
  const want = (env.HELPER_KEY || "").trim();
  const given = (request.headers.get("x-nala-helper") || "").trim();
  if (want && given === want) return null;
  return json(401, { error: "helper key rejected", configured: !!want,
                     configuredLength: want.length, receivedLength: given.length });
}

/* hotelInfo is valid for ten minutes (the manual's number), so eight of
   caching leaves a slow request room, the idToken pattern next door. */
let HINFO = null, HINFO_AT = 0;

export async function ttHotelInfo(env) {
  if (HINFO && Date.now() - HINFO_AT < 8 * 60 * 1000) return HINFO;
  const u = base(env) + "/v3/hotel/getInfo?clientId=" +
    encodeURIComponent((env.TT_CLIENT_ID || "").trim()) +
    "&clientSecret=" + encodeURIComponent((env.TT_CLIENT_SECRET || "").trim()) +
    "&date=" + Date.now();
  const r = await fetch(u);
  const j = await r.json().catch(() => ({}));
  if (!j.hotelInfo)
    throw new Error("getInfo refused: " + (j.errmsg || j.errcode || r.status));
  HINFO = j.hotelInfo; HINFO_AT = Date.now();
  return HINFO;
}

/* The access token opens the lock list. TTLock's oauth wants the password
   as an md5; a TT_PASSWORD already 32 hex chars is taken as pre-hashed so
   the plain text need not be stored anywhere at all. */
let TOKEN = null, TOKEN_AT = 0;

export async function ttAccessToken(env) {
  if (TOKEN && Date.now() - TOKEN_AT < 50 * 60 * 1000) return TOKEN;
  const pw = (env.TT_PASSWORD || "").trim();
  /* Either case: TTLock's own pages show md5s in both, and an uppercase
     one taken for plain text would be hashed a second time - the exact
     "oauth refused" the first live run nearly hit, 9 Sep. */
  const hashed = /^[0-9a-fA-F]{32}$/.test(pw) ? pw.toLowerCase() : md5(pw);
  const body = new URLSearchParams({
    client_id: (env.TT_CLIENT_ID || "").trim(),
    client_secret: (env.TT_CLIENT_SECRET || "").trim(),
    username: (env.TT_ACCOUNT || "").trim(),
    password: hashed,
    grant_type: "password"
  });
  const r = await fetch(base(env) + "/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString()
  });
  const j = await r.json().catch(() => ({}));
  const t = j.access_token || j.accessToken;
  if (!t) throw new Error("oauth refused: " + (j.errmsg || j.error || r.status));
  TOKEN = t; TOKEN_AT = Date.now();
  return TOKEN;
}

/* The villa -> lock table, straight from the cloud that owns it. Nothing
   here or in the repo restates it: a replaced lock is a change in TTHotel
   and nowhere else. Door names that are plain numbers are villas; the rest
   (Spare Room, store 2) ride along under extras so the helper can say what
   it saw without offering to card a storeroom. */
export async function ttLocks(env) {
  const token = await ttAccessToken(env);
  const u = base(env) + "/v3/lock/listByHotel?clientId=" +
    encodeURIComponent((env.TT_CLIENT_ID || "").trim()) +
    "&accessToken=" + encodeURIComponent(token) +
    "&type=1&pageNo=1&pageSize=200&date=" + Date.now();
  const r = await fetch(u);
  const j = await r.json().catch(() => ({}));
  const list = j.list || j.locks || [];
  if (!Array.isArray(list) || (!list.length && j.errcode))
    throw new Error("lock list refused: " + (j.errmsg || j.errcode || r.status));
  const locks = {}, extras = [];
  list.forEach(x => {
    const name = String(x.doorName != null ? x.doorName :
                        x.lockAlias != null ? x.lockAlias : x.name || "").trim();
    const rec = {
      mac: String(x.lockMac || x.mac || "").replace(/:/g, "").toUpperCase(),
      lockId: x.lockId != null ? x.lockId : x.id,
      buildNo: +(x.buildingNo != null ? x.buildingNo :
                 x.buildingNumber != null ? x.buildingNumber : 1) || 1,
      floorNo: +(x.floorNo != null ? x.floorNo :
                 x.floorNumber != null ? x.floorNumber : 1) || 1
    };
    if (/^[0-9]{1,2}$/.test(name)) locks[name] = rec;
    else extras.push(Object.assign({ name }, rec));
  });
  return { locks, extras };
}

/* The router half. Returns a Response for the card routes and null for
   everything else, so mews-sync's own handler stays exactly what it was. */
export async function handleCardRoute(request, env) {
  const path = new URL(request.url).pathname;
  if (path !== "/cardauth" && path !== "/cardlocks") return null;
  if (request.method !== "GET") return json(405, { error: "GET only" });
  const refused = helperAllowed(request, env);
  if (refused) return refused;
  try {
    if (path === "/cardauth")
      return json(200, { ok: true, hotelInfo: await ttHotelInfo(env), ttl: 480 });
    const got = await ttLocks(env);
    return json(200, { ok: true, locks: got.locks, extras: got.extras });
  } catch (e) {
    /* The message names which upstream refused and why; it carries no
       secret, and the helper shows it verbatim at the desk. */
    return json(502, { ok: false, error: String(e && e.message || e) });
  }
}

/* For the suite only: the caches outlive one test's env. */
export function _resetCardCaches() { HINFO = null; HINFO_AT = 0; TOKEN = null; TOKEN_AT = 0; }
