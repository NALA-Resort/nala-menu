/* Chat Worker suite. Run: node worker/contact-test.mjs
 *
 * Firebase, Google's sign-in, Twilio and the push Worker are all stubbed.
 * Green here checks the logic and says nothing about the real services:
 * no Twilio account exists yet, and the sandbox reaches neither Twilio nor
 * Cloudflare. The one outside fact it does pin is Twilio's own published
 * signature example, which the signing code reproduces exactly.
 */
import worker, { normalisePhone as workerNorm, waWindow as wWindow,
                 contactChannel as wChannel, contactTemplateText as wTemplate,
                 mayDo as wMayDo, twilioSignature, forgetToken } from "./guest-contact.js";
import { readFileSync } from "node:fs";
import { createHmac } from "node:crypto";

let P = 0, F = 0;
const ck = (name, ok, detail) => {
  ok ? P++ : F++;
  console.log((ok ? "PASS " : "FAIL ") + name + (!ok && detail !== undefined ? " | " + JSON.stringify(detail) : ""));
};

/* ── the twins answer to the tables ───────────────────────────────
   Each function is cut out of nala-shared.js by matching its braces, the
   invites-test.mjs way, and run beside the Worker's copy on every case. */
const SHARED = readFileSync(new URL("../nala-shared.js", import.meta.url), "utf8");
function cut(name, kind = "function") {
  const i = SHARED.indexOf(kind + " " + name);
  if (i < 0) throw new Error("not in nala-shared.js: " + name);
  const open = kind === "var" ? SHARED.indexOf("=", i) : SHARED.indexOf("{", i);
  if (kind === "var") {
    let k = open + 1; while (/\s/.test(SHARED[k])) k++;
    const [o, c] = SHARED[k] === "[" ? ["[", "]"] : SHARED[k] === "{" ? ["{", "}"] : [];
    if (!o) return SHARED.slice(i, SHARED.indexOf(";", i) + 1);
    let depth = 0;
    for (let x = k; x < SHARED.length; x++) {
      if (SHARED[x] === o) depth++;
      else if (SHARED[x] === c && --depth === 0) return SHARED.slice(i, x + 1) + ";";
    }
  }
  let depth = 0;
  for (let k = open; k < SHARED.length; k++) {
    if (SHARED[k] === "{") depth++;
    else if (SHARED[k] === "}" && --depth === 0) return SHARED.slice(i, k + 1);
  }
  throw new Error("unbalanced: " + name);
}
const page = new Function([cut("normalisePhone"), cut("parseISO"), cut("parseDepDate"),
  cut("WA_WINDOW_MS", "var"), cut("waWindow"), cut("waAgreed"), cut("contactChannel"),
  cut("CONTACT_TEMPLATES", "var"), cut("contactTemplateText"),
  cut("ROLE_GRANTS", "var"), cut("normaliseRole"), cut("grantedByDefault"), "var PERMISSIONS = null;",
  cut("setPermissions"), cut("can")].join("\n") +
  "\nreturn { normalisePhone, waWindow, contactChannel, contactTemplateText, setPermissions, can };")();

{
  const phones = JSON.parse(readFileSync(new URL("../tests/phone_cases.json", import.meta.url), "utf8")).cases;
  ck("the Worker's phone rule and the page's agree on every case in phone_cases.json",
     phones.every(([g, want]) => workerNorm(g) === want && page.normalisePhone(g) === want));
  const T = JSON.parse(readFileSync(new URL("../tests/contact_cases.json", import.meta.url), "utf8"));
  const winOk = (f) => T.window.cases.every(([last, now, open, until]) => {
    const w = f(last, Date.parse(now));
    return w.open === open && (until === null ? w.until === null : w.until === Date.parse(until));
  });
  ck("the 24 hours: the Worker's copy says what contact_cases.json says", winOk(wWindow));
  ck("and so does the page's", winOk(page.waWindow));
  const chOk = (f) => T.channel.cases.every(([t, now, want]) => f(t, Date.parse(now)).ch === want);
  ck("which way a message goes: the Worker's copy agrees with the table", chOk(wChannel));
  ck("and the page's", chOk(page.contactChannel));
  const tpOk = (f) => T.templates.cases.every(([id, first, arrive, want]) => f(id, first, arrive) === want);
  ck("the approved words: the Worker records what the page previews", tpOk(wTemplate) && tpOk(page.contactTemplateText));
  /* Who may use the desk, and who may reply: the page's can() and the
     Worker's twin, on every case (30 Sep, the reply switch). */
  const off = (f) => T.grants.cases.filter(([role, perms, desk, rep]) =>
    f("editBookings", role, perms) !== desk || f("guestReply", role, perms) !== rep);
  const pageMay = (what, role, perms) => { page.setPermissions(perms); return page.can(role, what); };
  ck("who may use the desk and who may reply: the Worker agrees with contact_cases.json",
     !off(wMayDo).length, off(wMayDo));
  ck("and so does the page's can()", !off(pageMay).length, off(pageMay));
}

/* ── Twilio's own example ─────────────────────────────────────────
   From Twilio's webhook security page: this URL, these parameters and the
   Auth Token 12345 sign to 0/KCTR6DLpKmkAf8muzZqo1nDgQ=. */
ck("the signing reproduces Twilio's published example",
   await twilioSignature("12345", "https://mycompany.com/myapp.php?foo=1&bar=2",
     { CallSid: "CA1234567890ABCDE", Caller: "+12349013030", Digits: "1234",
       From: "+12349013030", To: "+18005551212" }) === "0/KCTR6DLpKmkAf8muzZqo1nDgQ=");

/* ── one world per test ─────────────────────────────────────────── */
const AUTH = "tok_live_secret";
const BASE = "https://nala-contact.example.workers.dev";
const envOf = (over = {}) => Object.assign({
  TWILIO_ACCOUNT_SID: "AC123", TWILIO_AUTH_TOKEN: AUTH, TWILIO_FROM: "+61480000000",
  TWILIO_WA_FROM: "+61480000000", TPL_QUESTION_SID: "HXquestion", TPL_ARRIVAL_SID: "HXarrival",
  CONTACT_EMAIL: "559210@staff.nala", CONTACT_PASSWORD: "559210", FB_API_KEY: "fb", BUZZ: "1" }, over);
let STORE, SENT, BUZZ, STATE, WRITES, CDN;
const SARAH = "61412345678", LEA = "33612345678";
const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Australia/Brisbane",
  year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
function install() {
  STORE = {}; SENT = []; BUZZ = []; WRITES = []; CDN = [];
  STATE = { email: "waiter@nala.x", tokenOk: true, loginOk: true, twilioOk: true };
  forgetToken();
  STORE["/staff/waiter@nala,x"] = { role: "waiter" };
  STORE["/staff/chef@nala,x"] = { role: "chef" };
  STORE["/staff/mgr@nala,x"] = { role: "manager" };
  STORE["/stays/" + today] = { "7": { id: "b-sarah", first: "Sarah", phone: "0412 345 678" } };
  STORE["/bookings/b-sarah/pms"] = { first: "Sarah", last: "Whitfield", phone: "0412 345 678",
                                     arrive: "2026-09-27", depart: "2026-10-02", villa: "7" };
  STORE["/bookings/b-james/pms"] = { first: "James", last: "Harrington", phone: "+61 438 220 761",
                                     arrive: "2026-10-03", depart: "2026-10-06" };
  STORE["/bookings/b-fixed/pms"] = { first: "Owen", phone: "07 3358 1122", arrive: "2026-10-01" };
  STORE["/phonefix/b-fixed"] = { phone: "+61400000015" };
  globalThis.fetch = async (url, opt = {}) => {
    const u = String(url), method = opt.method || "GET";
    if (u.includes("accounts:signInWithPassword")) {
      if (!STATE.loginOk) return new Response(JSON.stringify({ error: { message: "INVALID_PASSWORD" } }), { status: 400 });
      return new Response(JSON.stringify({ idToken: "MACHINE" }), { status: 200 });
    }
    if (u.includes("accounts:lookup")) {
      if (!STATE.tokenOk) return new Response(JSON.stringify({ error: {} }), { status: 400 });
      return new Response(JSON.stringify({ users: [{ email: STATE.email }] }), { status: 200 });
    }
    if (u.startsWith("https://api.twilio.com/") && u.endsWith("/Messages.json")) {
      const form = Object.fromEntries(new URLSearchParams(opt.body));
      SENT.push({ form, auth: opt.headers.Authorization });
      if (!STATE.twilioOk)
        return new Response(JSON.stringify({ code: 21211, message: "The 'To' number is not valid." }), { status: 400 });
      return new Response(JSON.stringify({ sid: "SM" + SENT.length, status: "queued" }), { status: 201 });
    }
    /* The account and its numbers, as the setup check asks for them.
       twilioAuthOk false is a token Twilio refuses. */
    if (u.startsWith("https://api.twilio.com/2010-04-01/Accounts/AC123.json") ||
        u.includes("/IncomingPhoneNumbers.json")) {
      if (STATE.twilioAuthOk === false || opt.headers.Authorization !== "Basic " + btoa("AC123:" + AUTH))
        return new Response(JSON.stringify({ code: 20003, message: "Authenticate" }), { status: 401 });
      if (u.endsWith("AC123.json"))
        return new Response(JSON.stringify(Object.assign({ sid: "AC123", status: "active", type: "Full" },
                                                          STATE.account || {})), { status: 200 });
      const want = decodeURIComponent((u.split("PhoneNumber=")[1] || ""));
      const nums = (STATE.numbers || [{ phone_number: "+61480000000", sms_url: BASE + "/twilio/in",
                                        sms_method: "POST" }]).filter((n) => n.phone_number === want);
      return new Response(JSON.stringify({ incoming_phone_numbers: nums }), { status: 200 });
    }
    if (u.startsWith("https://api.twilio.com/")) {
      SENT.push({ media: u, auth: opt.headers && opt.headers.Authorization });
      /* Twilio answers a media address with a redirect to a signed link. A
         runtime that follows it unasked may keep the header on: modelled. */
      const cdn = "https://media.twiliocdn.test/ME1?Signature=s";
      if (opt.redirect === "manual") return new Response(null, { status: 307, headers: { Location: cdn } });
      return globalThis.fetch(cdn, opt);
    }
    if (u.startsWith("https://media.twiliocdn.test/")) {
      const auth = opt.headers && opt.headers.Authorization;
      CDN.push({ auth });
      /* S3's own refusal of a signed link that also carries a header */
      if (auth) return new Response("Only one auth mechanism allowed", { status: 400 });
      return new Response("JPEGBYTES", { status: 200, headers: { "Content-Type": "image/jpeg" } });
    }
    if (u.includes("nala-push")) { BUZZ.push(JSON.parse(opt.body)); return new Response("{}"); }
    const [path, query] = u.split("firebasedatabase.app")[1].split(".json");
    const token = new URLSearchParams(query.slice(1)).get("auth");
    /* dbRefuse: the rules before their paste, which refuse the Worker */
    if (STATE.dbRefuse && token === "MACHINE") return new Response('{"error":"Permission denied"}', { status: 401 });
    if (method !== "GET") WRITES.push({ method, path, token });
    if (method === "PUT") { STORE[path] = JSON.parse(opt.body); return new Response(opt.body); }
    if (method === "PATCH") {
      const cur = Object.assign({}, STORE[path] || {});
      for (const [k, v] of Object.entries(JSON.parse(opt.body))) { if (v === null) delete cur[k]; else cur[k] = v; }
      STORE[path] = cur; return new Response(opt.body);
    }
    if (method === "DELETE") { delete STORE[path]; return new Response("null"); }
    /* A read of a node answers with what is stored at it, inside the
       record that holds it, or beneath it. */
    let base;
    if (path in STORE) base = STORE[path];
    else {
      const holder = Object.keys(STORE).filter((k) => path.startsWith(k + "/"))
                                       .sort((a, b) => b.length - a.length)[0];
      if (holder) {
        let o = STORE[holder];
        for (const part of path.slice(holder.length + 1).split("/")) o = o == null ? null : o[part];
        return new Response(JSON.stringify(o === undefined ? null : o));
      }
    }
    /* and whatever was written beneath it since, as the database would */
    const kids = base && typeof base === "object" ? JSON.parse(JSON.stringify(base)) : {};
    let under = false;
    for (const k of Object.keys(STORE)) if (k.startsWith(path + "/")) {
      under = true;
      const rest = k.slice(path.length + 1).split("/");
      let o = kids;
      for (let i = 0; i < rest.length - 1; i++) o = o[rest[i]] = o[rest[i]] || {};
      o[rest[rest.length - 1]] = STORE[k];
    }
    if (!under) return new Response(JSON.stringify(base === undefined ? null : base));
    return new Response(JSON.stringify(Object.keys(kids).length ? kids : null));
  };
}

/* A request as Twilio would make it: form encoded and signed, by node's own
   HMAC rather than the Worker's, so the two implementations meet here. */
function signed(path, params, { sign = true, token = AUTH } = {}) {
  const url = BASE + path;
  let data = url;
  for (const k of Object.keys(params).sort()) data += k + params[k];
  const sig = createHmac("sha1", token).update(data).digest("base64");
  const headers = { "Content-Type": "application/x-www-form-urlencoded" };
  if (sign) headers["X-Twilio-Signature"] = sig;
  return new Request(url, { method: "POST", headers, body: new URLSearchParams(params).toString() });
}
const inbound = (params, opts, env = envOf()) =>
  worker.fetch(signed("/twilio/in", params, opts), env, { waitUntil: () => {} });
const desk = (body, env = envOf()) => worker.fetch(new Request(BASE + "/", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(Object.assign({ idToken: "T" }, body)) }), env);
const settle = () => new Promise((r) => setTimeout(r, 5));
const msgs = (k) => Object.keys(STORE).filter((p) => p.startsWith("/contactmsgs/" + k + "/"));

/* ── a guest's message arriving ─────────────────────────────────── */
install();
let r = await inbound({ From: "+61412345678", To: "+61480000000", Body: "Could we have a late checkout?",
                        MessageSid: "SMa1", NumMedia: "0" });
await settle();
ck("an SMS from a guest is taken, and Twilio is answered with empty TwiML",
   r.status === 200 && (await r.text()).includes("<Response></Response>"));
let m = STORE["/contactmsgs/" + SARAH + "/in-SMa1"];
ck("the message is kept under the guest's number, keyed by Twilio's id",
   !!m && m.dir === "in" && m.ch === "sms" && m.body === "Could we have a late checkout?");
ck("and filed as new, for the desk to sort", STORE["/contactnew/" + SARAH + "/in-SMa1"] === true);
let t = STORE["/contact/" + SARAH];
ck("the thread says who, when, and which way they wrote",
   t && t.phone === "+61412345678" && t.lastInCh === "sms" && t.dir === "in" &&
   t.preview === "Could we have a late checkout?" && !!t.lastIn && !("lastInWa" in t));
ck("every write is the Worker's own login, never a caller's",
   WRITES.length > 0 && WRITES.every((w) => w.token === "MACHINE"));
ck("the desk is buzzed, as the Worker, with the villa the number is staying in",
   BUZZ.length === 1 && BUZZ[0].event === "guestMessage" && BUZZ[0].villa === "7" &&
   BUZZ[0].idToken === "MACHINE", BUZZ);
install();
await inbound({ From: "+61412345678", Body: "Hello", MessageSid: "SMq1" }, undefined, envOf({ BUZZ: "" }));
await settle();
ck("but not until BUZZ says the push Worker knows the event",
   BUZZ.length === 0 && STORE["/contactnew/" + SARAH + "/in-SMq1"] === true);

install();
STORE["/contact/" + SARAH] = { waBad: true, phone: "+61412345678" };
r = await inbound({ From: "whatsapp:+61412345678", Body: "The umbrella on our deck won't close.",
  MessageSid: "MMb2", NumMedia: "2", ProfileName: "Sarah W",
  MediaUrl0: "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/MMb2/Media/ME1",
  MediaContentType0: "image/jpeg", MediaUrl1: "https://evil.example/x.jpg",
  MediaContentType1: "image/jpeg" });
m = STORE["/contactmsgs/" + SARAH + "/in-MMb2"];
t = STORE["/contact/" + SARAH];
ck("a WhatsApp message is marked as WhatsApp, with the name the guest goes by there",
   m && m.ch === "wa" && m.profile === "Sarah W" && t.lastInCh === "wa" && !!t.lastInWa && t.profile === "Sarah W");
ck("its photo is kept, but only an address Twilio gave",
   m && m.media && m.media[0] && m.media[0].url.startsWith("https://api.twilio.com/") && !m.media[1]);
ck("and writing on WhatsApp clears a number WhatsApp once did not know", !("waBad" in t));

install();
await inbound({ From: "+61412345678", Body: "Hello", MessageSid: "SMdup" });
await inbound({ From: "+61412345678", Body: "Hello", MessageSid: "SMdup" });
ck("a webhook Twilio retries is one message, not two", msgs(SARAH).length === 1);

install();
r = await inbound({ From: "+61412345678", Body: "Hello", MessageSid: "SMx" }, { sign: false });
ck("an unsigned request is refused", r.status === 403);
ck("and nothing is written", WRITES.length === 0 && msgs(SARAH).length === 0);
r = await inbound({ From: "+61412345678", Body: "Hello", MessageSid: "SMx" }, { token: "someone-else" });
ck("a request signed with another key is refused too", r.status === 403 && WRITES.length === 0);

install();
await inbound({ From: "+61412345678", Body: " stop ", MessageSid: "SMs1" });
ck("STOP marks the guest as opted out", STORE["/contact/" + SARAH].optout &&
   STORE["/contact/" + SARAH].optout.word === "STOP");
ck("and is still a message the desk sees", STORE["/contactnew/" + SARAH + "/in-SMs1"] === true);
await inbound({ From: "+61412345678", Body: "START", MessageSid: "SMs2" });
ck("START takes it back", !("optout" in STORE["/contact/" + SARAH]));
await inbound({ From: "+61412345678", Body: "Please stop by the room later", MessageSid: "SMs3" });
ck("a sentence with the word in it is just a sentence", !("optout" in STORE["/contact/" + SARAH]));

install(); STATE.loginOk = false;
r = await inbound({ From: "+61412345678", Body: "Hello", MessageSid: "SMl" });
ck("if the Worker's own login fails, Twilio hears an error rather than a silent loss",
   r.status === 500 && WRITES.length === 0);

/* ── the desk ───────────────────────────────────────────────────── */
install();
r = await desk({ kind: "hello" });
let j = await r.json();
ck("hello says it is set up, WhatsApp too, and not in test mode", r.status === 200 && j.ready && j.wa && !j.test);
ck("and whether the buzz is on", j.buzz === true);
r = await desk({ kind: "hello" }, envOf({ TEST_NUMBERS: "0412 345 678, +33 6 12 34 56 78" }));
ck("and says so when it is in test mode", (await r.json()).test === true);
install(); STATE.tokenOk = false;
ck("an unverifiable token is refused", (await desk({ kind: "hello" })).status === 401);
install(); STATE.email = "chef@nala.x";
ck("a login without editBookings is refused", (await desk({ kind: "hello" })).status === 403);
install(); STORE["/permissions"] = { editBookings: { waiter: false } };
ck("and so is a waiter the matrix has switched off", (await desk({ kind: "hello" })).status === 403);
install(); STATE.email = "mgr@nala.x";
ck("the manager is let in", (await desk({ kind: "hello" })).status === 200);

/* free text, the way the guest last wrote */
install();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: new Date().toISOString(),
  lastIn: new Date().toISOString(), lastInCh: "sms" };
r = await desk({ kind: "send", ck: SARAH, text: "Of course - 1pm is yours." });
j = await r.json();
let s = SENT[0] && SENT[0].form;
ck("a guest who texted is answered by SMS, from the resort's number",
   r.status === 200 && j.ch === "sms" && s && s.From === "+61480000000" && s.To === "+61412345678" &&
   s.Body === "Of course - 1pm is yours.", { j, s });
ck("with Twilio's account credentials", SENT[0].auth === "Basic " + btoa("AC123:" + AUTH));
ck("and a receipt address that names the message",
   s.StatusCallback === BASE + "/twilio/status?ck=" + SARAH + "&m=" + j.id);
m = STORE["/contactmsgs/" + SARAH + "/" + j.id];
ck("the message is recorded as sent, by whom, with Twilio's id",
   m && m.dir === "out" && m.ch === "sms" && m.by === "waiter@nala.x" && m.sid === "SM1" &&
   m.status === "queued" && m.kind === "staff", m);
ck("and it was written before it went, as the Worker",
   WRITES[0].method === "PUT" && WRITES[0].path === "/contactmsgs/" + SARAH + "/" + j.id &&
   WRITES.every((w) => w.token === "MACHINE"));
ck("the thread's preview moves to what we said",
   STORE["/contact/" + SARAH].dir === "out" && STORE["/contact/" + SARAH].preview === "Of course - 1pm is yours.");

install();
const fresh = new Date(Date.now() - 60 * 60 * 1000).toISOString();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: fresh, lastIn: fresh, lastInCh: "wa", lastInWa: fresh };
r = await desk({ kind: "send", ck: SARAH, text: "Happy birthday to Tom!" });
j = await r.json(); s = SENT[0] && SENT[0].form;
ck("inside 24 hours on WhatsApp, free text goes on WhatsApp",
   r.status === 200 && j.ch === "wa" && s.From === "whatsapp:+61480000000" &&
   s.To === "whatsapp:+61412345678" && s.Body === "Happy birthday to Tom!", { j, s });

install();
const old = new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: old, lastIn: old, lastInCh: "wa", lastInWa: old };
r = await desk({ kind: "send", ck: SARAH, text: "Your transfer is at 2pm." });
j = await r.json();
ck("past 24 hours, free text on WhatsApp is refused, and says why",
   r.status === 409 && j.window === "closed" && /24 hours/.test(j.error));
ck("with nothing sent and nothing recorded", SENT.length === 0 && msgs(SARAH).length === 0);
r = await desk({ kind: "send", ck: SARAH, text: "Your transfer is at 2pm.", via: "sms" });
j = await r.json();
ck("the same words go by SMS when the desk asks", r.status === 200 && j.ch === "sms" &&
   SENT[0].form.To === "+61412345678" && !("ContentSid" in SENT[0].form));

install();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: old, lastIn: old, lastInCh: "wa", lastInWa: old };
r = await desk({ kind: "send", ck: SARAH, template: "question", booking: "b-sarah", text: "ignored" });
j = await r.json(); s = SENT[0] && SENT[0].form;
ck("an approved message goes by its Content SID, the name as its one variable",
   r.status === 200 && s.ContentSid === "HXquestion" && JSON.parse(s.ContentVariables)["1"] === "Sarah" &&
   !("2" in JSON.parse(s.ContentVariables)) && !("Body" in s), s);
m = STORE["/contactmsgs/" + SARAH + "/" + j.id];
ck("and the record holds the words the guest got, not what the page typed",
   m.body === "Hi Sarah, it's Nala Resort with a quick question about your stay. Could you reply to this message when you have a moment?" &&
   m.kind === "template" && m.tpl === "question");

install();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: old, lastIn: old, lastInCh: "wa", lastInWa: old };
r = await desk({ kind: "send", ck: SARAH, template: "question", booking: "b-james" });
j = await r.json();
ck("a booking that is not this guest's lends no name: the approved words say 'there'",
   r.status === 200 && JSON.parse(SENT[0].form.ContentVariables)["1"] === "there");

install();
const JAMES = "61438220761";
STORE["/contact/" + JAMES] = { phone: "+61438220761", lastAt: old, wa: { on: true, by: "x", at: old } };
r = await desk({ kind: "send", ck: JAMES, template: "arrival", booking: "b-james" });
j = await r.json(); s = SENT[0] && SENT[0].form;
ck("Your arrival carries the name and the booking's day",
   r.status === 200 && s.ContentSid === "HXarrival" &&
   JSON.stringify(JSON.parse(s.ContentVariables)) === JSON.stringify({ 1: "James", 2: "Saturday 3 October" }), s);
install();
STORE["/contact/" + JAMES] = { phone: "+61438220761", lastAt: old, wa: { on: true, by: "x", at: old } };
r = await desk({ kind: "send", ck: JAMES, template: "arrival" });
ck("and is refused without the booking to take them from", r.status === 400 && SENT.length === 0);

install();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: old, lastIn: old, lastInCh: "sms" };
r = await desk({ kind: "send", ck: SARAH, template: "question", booking: "b-sarah" });
ck("an approved WhatsApp message to a guest who never agreed to WhatsApp is refused",
   r.status === 409 && SENT.length === 0);
install();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: old, lastInWa: old };
r = await desk({ kind: "send", ck: SARAH, template: "question" }, envOf({ TPL_QUESTION_SID: "" }));
ck("and one Twilio does not hold yet says so", r.status === 503 && SENT.length === 0);

install();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: fresh, lastIn: fresh, lastInCh: "wa", lastInWa: fresh };
r = await desk({ kind: "send", ck: SARAH, text: "Hello" }, envOf({ TWILIO_WA_FROM: "" }));
j = await r.json();
ck("with no WhatsApp sender set up, everything goes by SMS", r.status === 200 && j.ch === "sms" &&
   SENT[0].form.From === "+61480000000");

/* the test list */
install();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: fresh, lastIn: fresh, lastInCh: "sms" };
r = await desk({ kind: "send", ck: SARAH, text: "Hello" }, envOf({ TEST_NUMBERS: "+61400000099" }));
j = await r.json();
ck("in test mode a guest's number is refused, and the page is told why",
   r.status === 403 && j.test === true && /Test mode/.test(j.error));
ck("nothing sent, nothing recorded", SENT.length === 0 && msgs(SARAH).length === 0);
r = await desk({ kind: "send", ck: SARAH, text: "Hello" }, envOf({ TEST_NUMBERS: "0400 000 099; 0412 345 678" }));
ck("a number on the test list is sent to, however it was typed", r.status === 200 && SENT.length === 1);

install();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: fresh, optout: { at: fresh, word: "STOP" } };
r = await desk({ kind: "send", ck: SARAH, text: "Hello" });
ck("a guest who texted STOP is not sent anything", r.status === 409 && SENT.length === 0 &&
   /STOP/.test((await r.json()).error));

/* a first message */
install();
r = await desk({ kind: "send", ck: SARAH, text: "Welcome to Nala!" });
ck("a first message to a number with no thread needs the booking it is on",
   r.status === 400 && SENT.length === 0 && msgs(SARAH).length === 0);
r = await desk({ kind: "send", ck: SARAH, text: "Welcome to Nala!", booking: "b-james" });
ck("and a booking that is someone else's will not do", r.status === 400 && SENT.length === 0);
r = await desk({ kind: "send", ck: SARAH, text: "Welcome to Nala!", booking: "b-sarah" });
ck("with the guest's own booking it goes, and the thread begins",
   r.status === 200 && SENT.length === 1 && STORE["/contact/" + SARAH].phone === "+61412345678");
install();
r = await desk({ kind: "send", ck: "61400000015", text: "Your room is ready.", booking: "b-fixed" });
ck("the number the desk corrected counts as the booking's", r.status === 200 && SENT[0].form.To === "+61400000015");

install(); STATE.twilioOk = false;
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: fresh, lastIn: fresh, lastInCh: "sms" };
r = await desk({ kind: "send", ck: SARAH, text: "Hello" });
j = await r.json();
m = STORE["/contactmsgs/" + SARAH + "/" + j.id];
ck("a send Twilio refuses is reported with Twilio's words", r.status === 502 && /not valid/.test(j.error));
ck("and recorded as failed, so the conversation shows it", m && m.status === "failed" && /not valid/.test(m.err));

install();
ck("a message longer than a page will hold is refused",
   (await desk({ kind: "send", ck: SARAH, text: "x".repeat(1001) })).status === 400);
ck("so is a number that is not one", (await desk({ kind: "send", ck: "0412", text: "hi" })).status === 400);

/* ── receipts ───────────────────────────────────────────────────── */
install();
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: fresh, lastIn: fresh, lastInCh: "wa", lastInWa: fresh };
r = await desk({ kind: "send", ck: SARAH, text: "Happy birthday to Tom!" });
j = await r.json();
const status = (params, opts) =>
  worker.fetch(signed("/twilio/status?ck=" + SARAH + "&m=" + j.id, params, opts), envOf());
await status({ MessageSid: "SM1", MessageStatus: "read" });
ck("a receipt moves the message's status", STORE["/contactmsgs/" + SARAH + "/" + j.id].status === "read");
await status({ MessageSid: "SM1", MessageStatus: "delivered" });
ck("and a late 'delivered' does not undo 'read'", STORE["/contactmsgs/" + SARAH + "/" + j.id].status === "read");
r = await status({ MessageSid: "SM1", MessageStatus: "failed" }, { sign: false });
ck("an unsigned receipt is refused", r.status === 403 && STORE["/contactmsgs/" + SARAH + "/" + j.id].status === "read");

/* not on WhatsApp: the same words go by SMS, once */
install();
STORE["/contact/" + LEA] = { phone: "+33612345678", lastAt: old, wa: { on: true, by: "x", at: old } };
STORE["/contactmsgs/" + LEA + "/o1"] = { dir: "out", ch: "wa", body: "Hi Léa, it's Nala Resort with a quick question.",
  at: old, by: "waiter@nala.x", kind: "template", tpl: "question", sid: "SMw", status: "queued" };
const lea = (params) => worker.fetch(signed("/twilio/status?ck=" + LEA + "&m=o1", params), envOf());
await lea({ MessageSid: "SMw", MessageStatus: "failed", ErrorCode: "63024" });
m = STORE["/contactmsgs/" + LEA + "/o1"];
ck("WhatsApp saying it does not know the number marks the thread SMS only",
   STORE["/contact/" + LEA].waBad === true && m.status === "failed" && /63024/.test(m.err));
const fb = m.fell && STORE["/contactmsgs/" + LEA + "/" + m.fell];
ck("and the same words go by SMS, recorded as the fallback of the first",
   SENT.length === 1 && SENT[0].form.To === "+33612345678" && SENT[0].form.From === "+61480000000" &&
   SENT[0].form.Body === "Hi Léa, it's Nala Resort with a quick question." &&
   fb && fb.kind === "fallback" && fb.of === "o1" && fb.ch === "sms" && fb.sid === "SM1", { m, fb });
await lea({ MessageSid: "SMw", MessageStatus: "undelivered", ErrorCode: "63024" });
ck("a second receipt for the same failure sends nothing more", SENT.length === 1);

install();
STORE["/contact/" + LEA] = { phone: "+33612345678", lastAt: old, wa: { on: true } };
STORE["/contactmsgs/" + LEA + "/o1"] = { dir: "out", ch: "wa", body: "x", at: old, status: "queued" };
await lea({ MessageSid: "SMw", MessageStatus: "failed", ErrorCode: "63016" });
ck("any other WhatsApp failure is reported, not retried by SMS",
   SENT.length === 0 && !("waBad" in STORE["/contact/" + LEA]) &&
   STORE["/contactmsgs/" + LEA + "/o1"].status === "failed");

install();
STORE["/contact/" + LEA] = { phone: "+33612345678", lastAt: old, wa: { on: true } };
STORE["/contactmsgs/" + LEA + "/o1"] = { dir: "out", ch: "wa", body: "x", at: old, status: "queued" };
await worker.fetch(signed("/twilio/status?ck=" + LEA + "&m=o1",
  { MessageSid: "SMw", MessageStatus: "failed", ErrorCode: "63024" }), envOf({ TEST_NUMBERS: "+61400000099" }));
ck("and in test mode the fallback does not reach a guest either", SENT.length === 0);

/* ── a guest's photo ────────────────────────────────────────────── */
install();
STORE["/contactmsgs/" + SARAH + "/in-MM1"] = { dir: "in", ch: "wa", body: "", at: fresh,
  media: { 0: { url: "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/MM1/Media/ME1", type: "image/jpeg" } } };
r = await desk({ kind: "media", ck: SARAH, m: "in-MM1", i: "0" });
ck("a photo comes through the Worker, fetched with the account's credentials",
   r.status === 200 && r.headers.get("Content-Type") === "image/jpeg" && (await r.text()) === "JPEGBYTES" &&
   SENT[0].auth === "Basic " + btoa("AC123:" + AUTH));
ck("and the credentials go to Twilio only, never on to the signed link it redirects to",
   CDN.length === 1 && !CDN[0].auth);
ck("and a photo that is not there is a 404", (await desk({ kind: "media", ck: SARAH, m: "in-MM1", i: "1" })).status === 404);
STORE["/contactmsgs/" + SARAH + "/in-MM2"] = { dir: "in", ch: "wa", at: fresh,
  media: { 0: { url: "https://evil.example/steal", type: "image/jpeg" } } };
const before = SENT.length;
ck("an address that is not Twilio's is never fetched with our credentials",
   (await desk({ kind: "media", ck: SARAH, m: "in-MM2", i: "0" })).status === 404 && SENT.length === before);
install(); STATE.email = "chef@nala.x";
ck("and a login without editBookings sees no photo",
   (await desk({ kind: "media", ck: SARAH, m: "in-MM1", i: "0" })).status === 403);

/* ── a team's view of its own task (29 Sep) ──────────────────────
   The owner: the login doing a task "can only see what the guest has
   requested ... can't see any of the responses". The door hands a team
   its task's stretch of the conversation - the request and everything
   after it until Done - and nothing else. */
function teamWorld() {
  install();
  STORE["/staff/ray@nala,x"] = { role: "housekeeping" };
  STORE["/contactsettings"] = { teams: { bar: { members: { "ray@nala,x": true } } } };
  const T0 = Date.now() - 30 * 60000, at = (min) => new Date(T0 + min * 60000).toISOString();
  STORE["/contactmsgs/" + SARAH] = {
    "in-SMold":    { dir: "in", ch: "wa", body: "Is breakfast included?", at: at(-90) },
    "in-SMdrinks": { dir: "in", ch: "wa", body: "Can we get some drinks by the pool?", at: at(0) },
    "odesk1":      { dir: "out", ch: "wa", body: "Of course! What would you like?", at: at(1),
                     by: "waiter@nala.x", status: "read" },
    "in-SMwhat":   { dir: "in", ch: "wa", body: "Two G&Ts and a lemonade please", at: at(3),
                     media: { 0: { url: "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/MM9/Media/ME9",
                                   type: "image/jpeg" } } }
  };
  STORE["/tasks/bar/t1"] = { ck: SARAH, msg: "in-SMdrinks", villa: "7", name: "Sarah Whitfield",
                             text: "Can we get some drinks by the pool?", state: "open", at: at(0), by: "waiter@nala.x" };
  STORE["/tasks/maintenance/t2"] = { ck: SARAH, msg: "in-SMold", villa: "7", name: "Sarah Whitfield",
                                     text: "Is breakfast included?", state: "open", at: at(-90), by: "waiter@nala.x" };
  return at;
}
let at = teamWorld(); STATE.email = "ray@nala.x";
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }, { team: "maintenance", t: "t2" }] });
j = await r.json();
const bar1 = (j.logs || {})["bar/t1"] || [];
ck("a team's login gets its task's conversation: the request, the desk's reply, the guest's answer",
   r.status === 200 && bar1.map((x) => x.id).join() === "in-SMdrinks,odesk1,in-SMwhat" &&
   bar1[1].dir === "out" && bar1[1].by === "waiter@nala.x" && bar1[2].body === "Two G&Ts and a lemonade please");
ck("nothing from before the request, and never another team's task",
   !bar1.some((x) => x.id === "in-SMold") && !("maintenance/t2" in (j.logs || {})));
STORE["/contactmsgs/" + SARAH]["in-SMcandle"] = { dir: "in", ch: "wa", at: at(4),
  body: "Any chance of a candle on the dessert?", tasks: { kitchen: "t9" } };
STORE["/contactmsgs/" + SARAH]["in-SMsoon"] = { dir: "in", ch: "wa", at: at(5), body: "See you soon!" };
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }] });
j = await r.json();
ck("a later request made into another team's task is theirs, not this card's; the rest stays",
   !(j.logs["bar/t1"] || []).some((x) => x.id === "in-SMcandle") &&
   (j.logs["bar/t1"] || []).some((x) => x.id === "in-SMsoon"));
delete STORE["/contactmsgs/" + SARAH]["in-SMcandle"]; delete STORE["/contactmsgs/" + SARAH]["in-SMsoon"];
ck("a photo is counted, its address never handed over",
   bar1[2].photos === 1 && !JSON.stringify(j).includes("api.twilio.com"));
STORE["/tasks/bar/t1"].state = "done"; STORE["/tasks/bar/t1"].doneAt = at(2);
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }] });
j = await r.json();
ck("a task done keeps the conversation up to its Done, and no further",
   (j.logs["bar/t1"] || []).map((x) => x.id).join() === "in-SMdrinks,odesk1");
at = teamWorld();
r = await desk({ kind: "tasklog", tasks: [{ team: "maintenance", t: "t2" }] });
j = await r.json();
ck("the desk may read any team's task", (j.logs["maintenance/t2"] || []).length === 4);
at = teamWorld(); STATE.email = "chef@nala.x";
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }] });
j = await r.json();
ck("a login on no team gets nothing", r.status === 200 && !Object.keys(j.logs || {}).length);
ck("and is still refused a send", (await desk({ kind: "send", ck: SARAH, text: "hi" })).status === 403);
at = teamWorld(); STATE.email = "ray@nala.x";
r = await desk({ kind: "taskmedia", team: "bar", t: "t1", m: "in-SMwhat", i: "0" });
ck("the team sees a photo in its task's conversation",
   r.status === 200 && (await r.text()) === "JPEGBYTES");
STORE["/contactmsgs/" + SARAH]["in-SMold"].media = { 0: { url: "https://api.twilio.com/x/Media/ME1", type: "image/jpeg" } };
ck("but not one from before the request",
   (await desk({ kind: "taskmedia", team: "bar", t: "t1", m: "in-SMold", i: "0" })).status === 404);
ck("nor any photo of a team it is not on",
   (await desk({ kind: "taskmedia", team: "maintenance", t: "t2", m: "in-SMold", i: "0" })).status === 403);

/* ── a reply from a task's card (30 Sep) ─────────────────────────
   The owner: "a toggle in settings for a role being able to respond to
   messages". A role switched on in Settings replies from its own open
   tasks, to that task's guest and nobody else; switched off, it reads. */
function replyWorld(perms) {
  const at = teamWorld();
  STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: at(3), lastIn: at(3),
                                 lastInCh: "wa", lastInWa: at(3) };
  STORE["/contact/" + LEA] = { phone: "+33612345678", lastAt: at(3), lastIn: at(3), lastInCh: "sms" };
  if (perms) STORE["/permissions"] = perms;
  STATE.email = "ray@nala.x";
  return at;
}
const HK_ON = { guestReply: { housekeeping: true } };
replyWorld();
r = await desk({ kind: "send", team: "bar", t: "t1", text: "Coming right up." });
j = await r.json();
ck("a team's login its role may not reply from is refused, and told where the switch is",
   r.status === 403 && /Settings, General, Roles/.test(j.error) && SENT.length === 0 && msgs(SARAH).length === 0, j);
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }] });
j = await r.json();
ck("and its cards carry no way to send", r.status === 200 && (j.logs["bar/t1"] || []).length === 3 &&
   !Object.keys(j.routes || {}).length, j.routes);
replyWorld(HK_ON);
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }] });
j = await r.json();
ck("switched on, each open card says which way a reply goes: WhatsApp, the way she wrote",
   j.routes && j.routes["bar/t1"] && j.routes["bar/t1"].ch === "wa" && j.routes["bar/t1"].until > Date.now(), j.routes);
r = await desk({ kind: "send", team: "bar", t: "t1", ck: LEA, text: "Two G&Ts and a lemonade, on their way." });
j = await r.json(); s = SENT[0] && SENT[0].form;
ck("a reply from the card goes to the task's guest, whatever number the page names",
   r.status === 200 && j.ch === "wa" && s && s.To === "whatsapp:+61412345678" &&
   s.Body === "Two G&Ts and a lemonade, on their way." && !SENT.some((x) => x.form && /33612345678/.test(x.form.To)), { j, s });
m = STORE["/contactmsgs/" + SARAH + "/" + j.id];
ck("recorded in the login's name, written by the Worker, the desk's conversation and the card's",
   m && m.dir === "out" && m.by === "ray@nala.x" && m.kind === "staff" &&
   WRITES.every((w) => w.token === "MACHINE") && STORE["/contact/" + SARAH].lastOut === m.at, m);
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }] });
j = await r.json();
ck("and the card shows it under the guest's answer",
   (j.logs["bar/t1"] || []).slice(-1).map((x) => x.by + "|" + x.body).join() ===
   "ray@nala.x|Two G&Ts and a lemonade, on their way.", j.logs["bar/t1"]);
r = await desk({ kind: "send", team: "maintenance", t: "t2", text: "hi" });
ck("never from a task of a team it is not on", r.status === 403 && SENT.length === 1);
r = await desk({ kind: "send", ck: SARAH, text: "hi" });
ck("nor with no task at all: only the desk writes to any guest", r.status === 403 && SENT.length === 1);
r = await desk({ kind: "send", team: "bar", t: "t1", template: "question" });
ck("an approved message is the desk's, not the card's", r.status === 400 && SENT.length === 1);
ck("and the desk's doors stay shut to it", (await desk({ kind: "hello" })).status === 403);
STORE["/tasks/bar/t1"].state = "done"; STORE["/tasks/bar/t1"].doneAt = new Date().toISOString();
r = await desk({ kind: "send", team: "bar", t: "t1", text: "One more thing" });
ck("once Done, the card's reply is over", r.status === 403 && SENT.length === 1);
replyWorld(HK_ON);
const stale = new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString();
Object.assign(STORE["/contact/" + SARAH], { lastIn: stale, lastInWa: stale });
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }] });
j = await r.json();
ck("past WhatsApp's 24 hours the card is told so", j.routes["bar/t1"].ch === "watpl", j.routes);
r = await desk({ kind: "send", team: "bar", t: "t1", text: "Your drinks are on the deck." });
ck("free text on WhatsApp is refused, as it is for the desk", r.status === 409 && SENT.length === 0);
r = await desk({ kind: "send", team: "bar", t: "t1", text: "Your drinks are on the deck.", via: "sms" });
j = await r.json();
ck("and goes by SMS instead", r.status === 200 && j.ch === "sms" && SENT[0].form.To === "+61412345678");
replyWorld(HK_ON);
STORE["/contact/" + SARAH].optout = { at: new Date().toISOString(), word: "STOP" };
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }] });
j = await r.json();
ck("a guest who texted STOP: the card is told nothing can go",
   j.routes["bar/t1"].ch === "none" &&
   (await desk({ kind: "send", team: "bar", t: "t1", text: "x", via: "sms" })).status === 409 && SENT.length === 0);
replyWorld(HK_ON);
r = await desk({ kind: "tasklog", tasks: [{ team: "bar", t: "t1" }] }, envOf({ TWILIO_WA_FROM: "" }));
j = await r.json();
ck("with WhatsApp not set up, the card says SMS", j.routes["bar/t1"].ch === "sms", j.routes);
teamWorld(); STORE["/permissions"] = { guestReply: { waiter: false } };
STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: new Date().toISOString(),
  lastIn: new Date().toISOString(), lastInCh: "sms" };
r = await desk({ kind: "send", ck: SARAH, text: "hi" });
ck("the desk switched off: the waiter still reads Chat, but may not reply",
   (await desk({ kind: "hello" })).status === 200 && r.status === 403 && SENT.length === 0);
STATE.email = "mgr@nala.x";
ck("the manager always may", (await desk({ kind: "send", ck: SARAH, text: "hi" })).status === 200);

/* ── the setup check (30 Sep) ────────────────────────────────────
   The owner, a test text refused and Twilio's console no help: "Why
   don't you just create an error webhook url". The Worker checks each
   thing the setup steps set and says in plain words what is wrong. */
const check = async (env = envOf()) => {
  const r = await desk({ kind: "check" }, env);
  const j = await r.json().catch(() => ({}));
  return { status: r.status, by: Object.fromEntries((j.check || []).map((x) => [x.key, x])), list: j.check || [] };
};
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
let c = await check();
ck("set up as the steps say, every line of the check is working, in the steps' order",
   c.status === 200 && ["twilio", "number", "webhook", "login", "rules"].every((k) => c.by[k] && c.by[k].ok === true) &&
   c.list.map((x) => x.key).join() === "twilio,number,webhook,login,rules,test,whatsapp", c.list);
ck("and what is only for knowing says so: test mode, WhatsApp",
   c.by.test.ok === null && /Test mode is off/.test(c.by.test.say) && c.by.whatsapp.ok === null &&
   /WhatsApp is set up/.test(c.by.whatsapp.say));
ck("nothing secret in it: no token, no password, no Account SID",
   !JSON.stringify(c.list).includes(AUTH) && !JSON.stringify(c.list).includes("559210\"") &&
   !JSON.stringify(c.list).includes("AC123"));
install(); STORE["/staff/559210@staff,nala"] = { role: "contact" };
ck("only the admin and the manager may ask for it", (await check()).status === 403);
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
STATE.twilioAuthOk = false;
c = await check();
ck("a token Twilio refuses is named, with where to copy it from",
   c.by.twilio.ok === false && /refuses TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN/.test(c.by.twilio.say), c.by.twilio);
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
STATE.account = { type: "Trial" };
ck("a trial account is named: it can only text verified phones", /still a trial/.test((await check()).by.twilio.say));
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
STATE.numbers = [{ phone_number: "+61480000000", sms_url: "https://demo.twilio.com/welcome/sms/reply", sms_method: "POST" }];
c = await check();
ck("texts handed somewhere else: the check names where, and where they should go",
   c.by.number.ok === true && c.by.webhook.ok === false &&
   c.by.webhook.say.includes("https://demo.twilio.com/welcome/sms/reply") &&
   c.by.webhook.say.includes(BASE + "/twilio/in by HTTP POST"), c.by.webhook);
STATE.numbers = [{ phone_number: "+61480000000", sms_url: BASE + "/twilio/in", sms_method: "GET" }];
ck("and a GET where it must be POST", (await check()).by.webhook.ok === false);
STATE.numbers = [];
ck("a number that is not on the account", /is not a number on this Twilio account/.test((await check()).by.number.say));
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
STATE.loginOk = false;
c = await check();
ck("the Worker's own login failing, with the passcode to check",
   c.by.login.ok === false && /cannot sign in \(INVALID_PASSWORD\)/.test(c.by.login.say) && !c.by.rules, c.by.login);
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "waiter" };
c = await check();
ck("a login with the wrong role in Settings, its address - its password's digits - never said",
   /the role waiter/.test(c.by.rules.say) && !JSON.stringify(c.list).includes("559210"), c.by.rules);
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
STATE.dbRefuse = true;
ck("rules not yet published: the database refuses the Worker",
   /publish the rules \(step 1\)/.test((await check()).by.rules.say));
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
await inbound({ From: "+61412345678", Body: "Test 1", MessageSid: "SMz1" }, { token: "a-different-token" });
c = await check();
ck("a text refused for its signature is told, with when, while the Worker remembers it",
   c.by.inbound && c.by.inbound.ok === false && /signature did not match TWILIO_AUTH_TOKEN/.test(c.by.inbound.say) &&
   !!c.by.inbound.at, c.by.inbound);
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
STATE.loginOk = false;
await inbound({ From: "+61412345678", Body: "Test 2", MessageSid: "SMz2" });
c = await check();
ck("and one refused because the Worker could not write it, in the Worker's words",
   c.by.inbound && /login failed: INVALID_PASSWORD/.test(c.by.inbound.say), c.by.inbound);
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
c = await check(envOf({ TWILIO_WA_FROM: "", TEST_NUMBERS: "0412 345 678", TWILIO_AUTH_TOKEN: "" }));
ck("a setting left out is named by its name, and test mode counts its phones",
   c.by.twilio.ok === false && /TWILIO_AUTH_TOKEN is not set/.test(c.by.twilio.say) &&
   /only message 1 phone/.test(c.by.test.say) && /not set up yet/.test(c.by.whatsapp.say), c.list);

/* Twilio's Debugger webhook (Monitor, Settings), which the owner found:
   its error reports join the check. */
const debugHook = (params) => worker.fetch(new Request(BASE + "/twilio/debug", { method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: new URLSearchParams(params).toString() }), envOf(), { waitUntil: () => {} });
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
r = await debugHook({ AccountSid: "AC123", Sid: "NO1", Level: "Error", Timestamp: "2026-09-30T03:46:31Z",
  PayloadType: "application/json", Payload: JSON.stringify({ resource_sid: "SMx", error_code: "11200",
    more_info: { Msg: "An attempt to retrieve content returned the HTTP status code 403", httpResponse: "403" },
    webhook: { response: { status_code: 403, body: "not from Twilio" } } }) });
c = await check();
ck("Twilio's own error report joins the check: its number, the Worker's answer, Twilio's words",
   r.status === 200 && c.by.twilioerror && c.by.twilioerror.ok === false &&
   /error 11200: the Worker answered 403, not from Twilio\. Twilio says: An attempt to retrieve/.test(c.by.twilioerror.say) &&
   c.by.twilioerror.at === "2026-09-30T03:46:31Z", c.by.twilioerror);
install(); STATE.email = "mgr@nala.x"; STORE["/staff/559210@staff,nala"] = { role: "contact" };
r = await debugHook({ AccountSid: "ACsomeoneelse", Level: "Error", Payload: JSON.stringify({ error_code: "11200" }) });
ck("another account's report is refused and kept nowhere",
   r.status === 403 && !(await check()).by.twilioerror && WRITES.length === 0);

/* ── the admin deletes a message (30 Sep) ─────────────────────────
   The owner: "is it possible to delete individual items from a message
   stream?" The admin's alone; the thread is re-read from what is left. */
function deleteWorld() {
  install();
  STORE["/staff/admin@nala,x"] = { role: "admin" };
  STATE.email = "admin@nala.x";
  const T0 = Date.now() - 60 * 60000, at = (min) => new Date(T0 + min * 60000).toISOString();
  STORE["/contactmsgs/" + SARAH + "/in-SMa"] = { dir: "in", ch: "sms", body: "Test 3", at: at(0) };
  STORE["/contactmsgs/" + SARAH + "/oA"] = { dir: "out", ch: "sms", body: "Do you need towels?", at: at(5), by: "admin@nala.x" };
  STORE["/contactmsgs/" + SARAH + "/in-MMb"] = { dir: "in", ch: "sms", body: "Nope.", at: at(9),
    media: { 0: { url: "https://api.twilio.com/x/Media/ME1", type: "image/jpeg" } } };
  STORE["/contactnew/" + SARAH + "/in-MMb"] = true;
  STORE["/contact/" + SARAH] = { phone: "+61412345678", lastAt: at(9), lastIn: at(9), lastInCh: "sms",
    lastOut: at(5), dir: "in", preview: "Nope.", wa: { on: true, by: "admin@nala.x", at: at(0) } };
  return at;
}
at = deleteWorld();
r = await desk({ kind: "delete", ck: SARAH, m: "in-MMb" });
let th = STORE["/contact/" + SARAH];
ck("the admin deletes a message: it goes from the conversation and from the new list",
   r.status === 200 && !STORE["/contactmsgs/" + SARAH + "/in-MMb"] && !STORE["/contactnew/" + SARAH + "/in-MMb"] &&
   !!STORE["/contactmsgs/" + SARAH + "/oA"]);
ck("and the thread is re-read from what is left: its preview, its order, WhatsApp's clock",
   th.lastAt === at(5) && th.preview === "Do you need towels?" && th.dir === "out" &&
   th.lastIn === at(0) && th.lastInCh === "sms" && th.lastOut === at(5) && !("lastInWa" in th), th);
ck("what no message says is kept: the number, the guest's WhatsApp consent",
   th.phone === "+61412345678" && th.wa && th.wa.on === true);
ck("written as the Worker", WRITES.length > 0 && WRITES.every((w) => w.token === "MACHINE"));
await desk({ kind: "delete", ck: SARAH, m: "oA" });
await desk({ kind: "delete", ck: SARAH, m: "in-SMa" });
th = STORE["/contact/" + SARAH];
ck("the last one deleted, the thread has no messages to point at, and keeps its guest",
   !("lastAt" in th) && !("preview" in th) && !("lastIn" in th) && th.phone === "+61412345678", th);
at = deleteWorld();
ck("a message that is not there is a 404", (await desk({ kind: "delete", ck: SARAH, m: "nosuch" })).status === 404);
STATE.email = "mgr@nala.x";
ck("the manager may not delete", (await desk({ kind: "delete", ck: SARAH, m: "in-MMb" })).status === 403 &&
   !!STORE["/contactmsgs/" + SARAH + "/in-MMb"]);
STATE.email = "waiter@nala.x";
ck("nor the desk", (await desk({ kind: "delete", ck: SARAH, m: "in-MMb" })).status === 403);

console.log("RESULT: %d passed, %d failed", P, F);
process.exit(F ? 1 : 0);
