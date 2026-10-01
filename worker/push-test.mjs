/* Push Worker suite. Run: node worker/push-test.mjs
 *
 * worker/nala-push.js is driven through its own fetch handler. The
 * database and the phones' push services are stubbed; each phone has a
 * real P-256 key pair and auth secret, and every push it is sent is
 * decrypted here by an independent RFC 8291 implementation on node:crypto,
 * so what a phone would show is read, not assumed. Nothing here reaches
 * Cloudflare, Firebase or a phone.
 */
import worker, { previewShut } from "./nala-push.js";
import { readFileSync } from "node:fs";
import { createECDH, createDecipheriv, hkdfSync, randomBytes, webcrypto } from "node:crypto";

let P = 0, F = 0;
const ck = (name, ok, detail) => {
  ok ? P++ : F++;
  console.log((ok ? "PASS " : "FAIL ") + name + (!ok && detail !== undefined ? " | " + JSON.stringify(detail) : ""));
};
const b64u = (b) => Buffer.from(b).toString("base64url");

/* ── phones ─────────────────────────────────────────────────────── */
function phone() {
  const ecdh = createECDH("prime256v1"); ecdh.generateKeys();
  const auth = randomBytes(16);
  return { ecdh, auth, keys: { p256dh: b64u(ecdh.getPublicKey()), auth: b64u(auth) } };
}
/* RFC 8291, aes128gcm, from the RFC on node:crypto: not the Worker's code. */
function decrypt(ph, body) {
  const buf = Buffer.from(body);
  const salt = buf.subarray(0, 16), idlen = buf[20];
  const serverPub = buf.subarray(21, 21 + idlen), ct = buf.subarray(21 + idlen);
  const shared = ph.ecdh.computeSecret(serverPub);
  const info = Buffer.concat([Buffer.from("WebPush: info\0"), ph.ecdh.getPublicKey(), serverPub]);
  const ikm = Buffer.from(hkdfSync("sha256", shared, ph.auth, info, 32));
  const cek = Buffer.from(hkdfSync("sha256", ikm, salt, Buffer.from("Content-Encoding: aes128gcm\0"), 16));
  const nonce = Buffer.from(hkdfSync("sha256", ikm, salt, Buffer.from("Content-Encoding: nonce\0"), 12));
  const d = createDecipheriv("aes-128-gcm", cek, nonce);
  d.setAuthTag(ct.subarray(ct.length - 16));
  const plain = Buffer.concat([d.update(ct.subarray(0, ct.length - 16)), d.final()]);
  let end = plain.length - 1; while (end >= 0 && plain[end] === 0) end--;
  if (plain[end] !== 2) throw new Error("no final-record delimiter");
  return JSON.parse(plain.subarray(0, end).toString("utf8"));
}

const PH = { ana: phone(), max: phone(), wes: phone(), hk: phone(), ben: phone() };
const ROLE = { ana: "admin", max: "manager", wes: "waiter", hk: "housekeeping", ben: "housekeeping" };
const subs = () => Object.fromEntries(Object.keys(PH).map((k) => [k + "@x",
  { d1: { endpoint: "https://push.test/" + k, keys: PH[k].keys, role: ROLE[k], at: "2026-10-01T00:00:00Z" } }]));

/* ── the database, and the push services ─────────────────────────── */
const DB = "https://db.test";
const TOKENS = { "T-contact": true, "T-desk": true };
let TREE, SENT, GONE;
function world(over = {}) {
  TREE = {
    pushsubs: subs(),
    notify: { on: true, events: {
      guestMessage: { admin: true, manager: true, waiter: true, housekeeping: false },
      cleaned: { admin: true, housekeeping: true } } },
    permissions: { open: { "guest-contact": true, tasks: true } },
    contactsettings: { teams: {
      maintenance: { members: { "hk@x": true, "ana@x": true } },
      bar: { label: "Pool bar", members: { "wes@x": true } } } },
    ...over
  };
  SENT = []; GONE = new Set();
}
globalThis.fetch = async (url, init = {}) => {
  url = String(url);
  if (url.startsWith(DB)) {
    const u = new URL(url);
    if (!TOKENS[u.searchParams.get("auth")])
      return new Response(JSON.stringify({ error: "Permission denied" }), { status: 401 });
    const path = decodeURIComponent(u.pathname).replace(/\.json$/, "").split("/").filter(Boolean);
    if ((init.method || "GET") === "DELETE") {
      let n = TREE; for (const p of path.slice(0, -1)) n = n && n[p];
      if (n) delete n[path[path.length - 1]];
      return new Response("null");
    }
    let n = TREE; for (const p of path) n = n == null ? null : n[p];
    return new Response(JSON.stringify(n === undefined ? null : n));
  }
  if (url.startsWith("https://push.test/")) {
    const who = url.slice("https://push.test/".length);
    SENT.push({ who, headers: init.headers, body: init.body });
    return new Response("", { status: GONE.has(who) ? 410 : 201 });
  }
  throw new Error("unexpected fetch " + url);
};

const kp = await webcrypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
const ENV = { DB, VAPID_SUBJECT: "mailto:test@example.com",
              VAPID_PRIVATE: (await webcrypto.subtle.exportKey("jwk", kp.privateKey)).d,
              VAPID_PUBLIC: b64u(await webcrypto.subtle.exportKey("raw", kp.publicKey)) };

async function post(body) {
  const r = await worker.fetch(new Request("https://nala-push.test/", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }), ENV);
  return { status: r.status, j: await r.json() };
}
/* who was buzzed, and what each phone shows */
const shown = () => Object.fromEntries(SENT.map((s) => [s.who, decrypt(PH[s.who], s.body)]));
const whom = () => SENT.map((s) => s.who).sort();
const MSG = { idToken: "T-contact", event: "guestMessage", villa: "7", url: "/guest-contact.html?c=61400000001" };

/* ── a guest's message ────────────────────────────────────────────── */
world();
let r = await post(MSG), s = shown();
ck("a guest's message buzzes the roles ticked for it, Chat open: the admin, manager and waiter",
   r.status === 200 && r.j.sent === 3 && JSON.stringify(whom()) === '["ana","max","wes"]', [r, whom()]);
ck("each phone reads Villa 7 - new message, and the tap opens that guest's conversation",
   Object.values(s).every((p) => p.title === "Nala Villas" && p.body === "Villa 7 - new message" &&
     p.url === "/guest-contact.html?c=61400000001"), s);
ck("one banner per conversation, buzzing again for the next message",
   Object.values(s).every((p) => p.tag === "chat-61400000001" && p.renotify === true), s);
ck("signed by VAPID, as every push",
   SENT.every((x) => /^vapid t=[\w-]+\.[\w-]+\.[\w-]+, k=/.test(x.headers.Authorization)), SENT.map((x) => x.headers));

world({ permissions: {} });
r = await post(MSG);
ck("while Chat is still the admin's alone, only the admin's phone is buzzed",
   JSON.stringify(whom()) === '["ana"]', whom());

world();
await post({ ...MSG, villa: "" });
ck("a guest not staying tonight: New guest message, not Villa ?",
   Object.values(shown()).every((p) => p.body === "New guest message"), shown());

world();
await post({ ...MSG, url: "https://evil.example/x" });
const off = Object.values(shown()).map((p) => p.url);
world();
await post({ ...MSG, url: "/guest-contact.html?c=61400000001&next=https://evil.example" });
ck("a tap never leaves Chat: any other url opens Chat's list",
   off.length && off.every((u) => u === "/guest-contact.html") &&
   Object.values(shown()).every((p) => p.url === "/guest-contact.html"), off);

world({ notify: { on: false, events: { guestMessage: { admin: true } } } });
r = await post(MSG);
ck("notifications off in Settings: nothing goes", r.j.sent === 0 && SENT.length === 0, r);
world({ notify: { on: true, hours: { from: "00:00", to: "00:00" }, events: { guestMessage: { admin: true } } } });
r = await post(MSG);
ck("and nothing in the quiet hours", r.j.skipped === "quiet hours" && SENT.length === 0, r);

world();
r = await post({ ...MSG, idToken: "T-forged" });
ck("a token the database refuses sends nothing", r.status === 401 && SENT.length === 0, r);

/* ── a task ───────────────────────────────────────────────────────── */
const TASK = { idToken: "T-desk", event: "guestTask", villa: "7", actor: "max@x",
               team: "maintenance", label: "Maintenance", url: "/tasks.html" };
world();
r = await post(TASK); s = shown();
ck("a task buzzes its team's own logins, whatever their role: the housekeeper and the admin",
   r.j.sent === 2 && JSON.stringify(whom()) === '["ana","hk"]', [r, whom()]);
ck("reading Villa 7 - Maintenance task, opening Tasks, and buzzing again for the next",
   Object.values(s).every((p) => p.body === "Villa 7 - Maintenance task" && p.url === "/tasks.html" &&
     p.tag === "task-maintenance-7" && p.renotify === true), s);

world();
await post({ ...TASK, team: "bar", label: "Bar" });
ck("a team renamed in Settings is called by its new name", JSON.stringify(whom()) === '["wes"]' &&
   shown().wes.body === "Villa 7 - Pool bar task", shown());

world();
await post({ ...TASK, label: undefined, villa: "" });
ck("with no name anywhere, the team's key; with no villa, no villa",
   Object.values(shown()).every((p) => p.body === "maintenance task"), shown());

world();
await post({ ...TASK, label: "Maintenance\u0007 and a great deal more than forty characters of name" });
ck("a name from the page is cut to a name", Object.values(shown()).every((p) =>
   p.body === "Villa 7 - " + "Maintenance and a great deal more than forty characters".slice(0, 40) + " task"), shown());

world();
await post({ ...TASK, actor: "ana@x" });
ck("never a buzz for your own tap, team member or not", JSON.stringify(whom()) === '["hk"]', whom());

world({ permissions: { open: { "guest-contact": true } } });
await post(TASK);
ck("while Tasks is still the admin's alone, a team's housekeeper is not buzzed for it",
   JSON.stringify(whom()) === '["ana"]', whom());

/* Settings' Guest task row (1 Oct): the team decides who, the row which of
   their roles; until the row is drawn, every role. */
world({ notify: { on: true, events: { guestTask: { admin: true, housekeeping: false } } } });
r = await post(TASK);
ck("Guest task off for housekeeping in Settings: the team's housekeeper is not told, its admin is",
   JSON.stringify(whom()) === '["ana"]' && r.j.sent === 1, [whom(), r.j]);
world({ notify: { on: true, events: { guestTask: { admin: true, housekeeping: true } } } });
await post({ ...TASK, team: "bar", label: "Bar" });
ck("Bar's waiter, waiter not ticked for Guest task, is not told; nor is anyone outside Bar",
   JSON.stringify(whom()) === '[]', whom());
world();
await post(TASK);
ck("with no Guest task row yet, every role of the team is told", JSON.stringify(whom()) === '["ana","hk"]', whom());

/* The reply counts what was passed over, so the page can say why no phone
   buzzed: the sender's own, and phones whose login cannot open Tasks yet. */
world();
r = await post({ ...TASK, actor: "hk@x" });
ck("the sender's own phone, passed over, is counted", r.j.self === 1 && r.j.sent === 1 && r.j.shut === 0, r.j);
world({ permissions: { open: { "guest-contact": true } } });
r = await post(TASK);
ck("and a team member's phone the preview keeps from Tasks", r.j.shut === 1 && r.j.sent === 1 && r.j.self === 0, r.j);
world();
r = await post({ idToken: "T-desk", event: "cleaned", villa: 4, actor: "hk@x" });
ck("every event's reply carries the counts", r.j.self === 1 && r.j.sent === 2 && r.j.shut === 0, r.j);

world();
r = await post({ ...TASK, team: "Maint!" });
const r2 = await post({ ...TASK, team: undefined });
ck("a task with no team key, or a bad one, is refused", r.status === 400 && r2.status === 400 &&
   SENT.length === 0, [r, r2]);

/* ── what was there before ────────────────────────────────────────── */
world({ permissions: {} });
r = await post({ idToken: "T-desk", event: "cleaned", villa: 4, actor: "max@x" });
s = shown();
ck("a cleaned villa still goes by role, both housekeepers and the admin, Chat's preview no matter",
   JSON.stringify(whom()) === '["ana","ben","hk"]', whom());
ck("reading Villa 4 - cleaned as before: the Cleans board, a tag per villa, no second buzz",
   Object.values(s).length === 3 && Object.values(s).every((p) => p.body === "Villa 4 - cleaned" &&
     p.url === "/cleaners.html" && p.tag === "villa-4" && !("renotify" in p)), s);

world();
GONE.add("wes");
r = await post(MSG);
ck("a phone that has gone is taken off the list", r.j.removed === 1 && !TREE.pushsubs["wes@x"].d1, r);

/* ── the preview rule, the third copy, answers to the shared table ── */
const PREVIEW = JSON.parse(readFileSync(new URL("../tests/contact_cases.json", import.meta.url), "utf8")).preview.cases;
const wrong = PREVIEW.filter(([page, role, perms, shut]) => previewShut(page, role, perms) !== shut);
ck("previewShut answers every case of tests/contact_cases.json's preview, as its two twins do",
   PREVIEW.length > 5 && wrong.length === 0, wrong);

console.log("RESULT: " + P + " passed, " + F + " failed");
process.exit(F ? 1 : 0);
