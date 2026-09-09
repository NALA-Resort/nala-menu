/* Card-relay suite. Run: node worker/cards-test.mjs
 *
 * TTLock's cloud is stubbed, exactly as Firebase is stubbed next door in
 * test.mjs, so this checks the relay's logic and says nothing about the
 * real service - the first live /cardlocks call is the test of their field
 * names, and the tolerant reads in cards.js say so.
 */
import worker from "./mews-sync.js";
import { md5, handleCardRoute, _resetCardCaches } from "./cards.js";

let P = 0, F = 0;
const ck = (name, ok) => { ok ? P++ : F++; console.log((ok ? "PASS " : "FAIL ") + name); };

const env = { HELPER_KEY: "helper-shh", TT_CLIENT_ID: "cid", TT_CLIENT_SECRET: "csec",
              TT_ACCOUNT: "h_1", TT_PASSWORD: "pw", ZAP_SECRET: "shh" };

let CALLS;
function install(overrides = {}) {
  CALLS = [];
  _resetCardCaches();
  globalThis.fetch = async (url, opt = {}) => {
    const u = String(url);
    CALLS.push({ u, body: opt.body || "" });
    if (u.includes("/v3/hotel/getInfo")) {
      if (overrides.infoFails)
        return new Response(JSON.stringify({ errcode: 10003, errmsg: "invalid client" }));
      return new Response(JSON.stringify({ hotelInfo: "HOTELINFO-1" }));
    }
    if (u.includes("/oauth2/token")) {
      if (overrides.oauthWants && !String(opt.body).includes("password=" + overrides.oauthWants))
        return new Response(JSON.stringify({ errmsg: "invalid account or invalid password" }));
      return new Response(JSON.stringify({ access_token: "AT-1" }));
    }
    if (u.includes("/v3/lock/listByHotel"))
      return new Response(JSON.stringify({ list: [
        { doorName: "9",  lockMac: "0E:95:1D:80:D3:EF", lockId: 27034828, buildingNo: 1, floorNo: 1 },
        { doorName: "17", lockMac: "94:F7:B6:C9:8F:91", lockId: 27041868, buildingNo: 1, floorNo: 1 },
        { doorName: "Spare Room", lockMac: "50:1D:9E:6F:B3:7F", lockId: 26664274 },
        { doorName: "store 2",    lockMac: "D1:8F:86:26:1A:61", lockId: 27703632 }
      ] }));
    return new Response("unexpected fetch " + u, { status: 500 });
  };
}
const req = (path, key, method = "GET") =>
  new Request("https://w.example" + path,
    { method, headers: key ? { "x-nala-helper": key } : {} });

/* ── md5, pinned to RFC 1321 ─────────────────────────────────── */
ck("md5 of nothing",  md5("") === "d41d8cd98f00b204e9800998ecf8427e");
ck("md5 of abc",      md5("abc") === "900150983cd24fb0d6963f7d28e17f72");
ck("md5 of the RFC's long vector",
   md5("message digest") === "f96b697d7cb7938d525a2f31aaf161d0");

/* ── the key on the door ─────────────────────────────────────── */
install();
{
  const r = await handleCardRoute(req("/cardauth", "wrong"), env);
  const j = await r.json();
  ck("a wrong helper key is refused with lengths only",
     r.status === 401 && j.receivedLength === 5 && !JSON.stringify(j).includes("helper-shh"));
  ck("and nothing was asked of TTLock", CALLS.length === 0);
}

/* ── /cardauth ───────────────────────────────────────────────── */
install();
{
  const r = await handleCardRoute(req("/cardauth", "helper-shh"), env);
  const j = await r.json();
  ck("hotelInfo is relayed", r.status === 200 && j.hotelInfo === "HOTELINFO-1");
  await handleCardRoute(req("/cardauth", "helper-shh"), env);
  ck("and cached inside its ten minutes: two asks, one upstream call",
     CALLS.filter(c => c.u.includes("getInfo")).length === 1);
}
install({ infoFails: true });
{
  const r = await handleCardRoute(req("/cardauth", "helper-shh"), env);
  const j = await r.json();
  ck("a refusal names the upstream and its reason",
     r.status === 502 && /getInfo/.test(j.error) && /invalid client/.test(j.error));
}

/* ── /cardlocks ──────────────────────────────────────────────── */
install();
{
  const r = await handleCardRoute(req("/cardlocks", "helper-shh"), env);
  const j = await r.json();
  ck("villas keyed by door number, macs stripped of colons",
     j.locks["9"] && j.locks["9"].mac === "0E951D80D3EF" &&
     j.locks["17"] && j.locks["17"].lockId === 27041868);
  ck("build and floor ride along for CE_WriteCard",
     j.locks["9"].buildNo === 1 && j.locks["9"].floorNo === 1);
  ck("the storeroom is an extra, not a villa",
     !j.locks["Spare Room"] && j.extras.some(e => e.name === "Spare Room") &&
     j.extras.some(e => e.name === "store 2"));
  const oauth = CALLS.find(c => c.u.includes("oauth2/token"));
  ck("the password crosses as its md5, never plain",
     oauth && String(oauth.body).includes(md5("pw")) &&
     !String(oauth.body).includes("password=pw&") && !String(oauth.body).endsWith("password=pw"));
}
install();
{
  const pre = Object.assign({}, env, { TT_PASSWORD: md5("pw") });
  await handleCardRoute(req("/cardlocks", "helper-shh"), pre);
  const oauth = CALLS.find(c => c.u.includes("oauth2/token"));
  ck("a pre-hashed password is sent as it is, not hashed twice",
     oauth && String(oauth.body).includes(md5("pw")));
}
install();
{
  const pre = Object.assign({}, env, { TT_PASSWORD: md5("pw").toUpperCase() });
  await handleCardRoute(req("/cardlocks", "helper-shh"), pre);
  const oauth = CALLS.find(c => c.u.includes("oauth2/token"));
  ck("an UPPERCASE pre-hash is recognised and lowered, not hashed twice",
     oauth && String(oauth.body).includes(md5("pw")));
}
/* TTHotel's Integration page hands out PLAIN passwords that look like
   md5s - found at the first live run, 9 Sep. The relay must not commit
   to one reading of a hex password: as-is first, hashed on refusal. */
install({ oauthWants: md5("2fac7bd2e23a2fac7bd2e23a2fac7bd2") });
{
  const hexplain = Object.assign({}, env,
    { TT_PASSWORD: "2fac7bd2e23a2fac7bd2e23a2fac7bd2" });
  const r = await handleCardRoute(req("/cardlocks", "helper-shh"), hexplain);
  const oauths = CALLS.filter(c => c.u.includes("oauth2/token"));
  ck("a hex password that is really plain text still gets a token",
     r.status === 200 && oauths.length === 2 &&
     String(oauths[1].body).includes(md5("2fac7bd2e23a2fac7bd2e23a2fac7bd2")));
}

/* ── the rest of the Worker is untouched ─────────────────────── */
install();
{
  const r = await worker.fetch(req("/", null), env);
  ck("a stray GET still gets mews-sync's own answer",
     r.status === 405 && (await r.text()) === "POST only");
  const r2 = await worker.fetch(req("/cardauth", "helper-shh"), env);
  ck("while /cardauth is answered before the POST-only door",
     r2.status === 200);
}

console.log("RESULT: %d passed, %d failed", P, F);
process.exit(F ? 1 : 0);
