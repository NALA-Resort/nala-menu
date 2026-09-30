/* NALA Chat Worker
 *
 * The messenger behind guest-contact.html: Twilio, for SMS and WhatsApp,
 * from one Australian mobile number. Asked for by the owner on 29 Sep to
 * replace Guest Touch, so that every guest's reply lands in this app.
 * GUEST-CONTACT.md is the whole brief and the setup.
 *
 * Three callers, three doors:
 *   guest-contact.html  POST JSON {idToken, kind, ...}
 *                         hello  is it set up, and is it in test mode?
 *                         send   one message from the desk to one guest
 *                         media  a guest's photo, fetched from Twilio
 *   tasks.html            tasklog    each task's conversation, from the
 *                                    request until Done, for its team
 *                         taskmedia  a photo inside that stretch
 *   Twilio              POST /twilio/in      a guest's message arriving
 *   Twilio              POST /twilio/status  a receipt for one we sent
 *
 * The page proposes; this Worker decides, as send-invites.js does. The
 * number comes off the thread, not the browser. Whether a message may be
 * free text is decided HERE by WhatsApp's 24 hours (contactChannel below),
 * and an approved message's words are built here from the booking. Twilio's
 * two doors answer only a request Twilio signed with the account's Auth
 * Token (X-Twilio-Signature): the URLs are public, the signature is not.
 *
 * Every message is written by this Worker's own login, a machine account
 * with the role `contact` - the Mews sync's pattern. The rules let that
 * login write messages and nothing else, and let no browser write one, so
 * a page cannot claim a message went that did not.
 *
 * NOT deployed by worker/wrangler.jsonc, which builds nala-mews-sync. A
 * third Worker: create it in the Cloudflare dashboard as `nala-contact`
 * (the page posts to nala-contact.ben-681.workers.dev), paste this file,
 * and set these secrets there, never in this repo:
 *   TWILIO_ACCOUNT_SID  AC..., from the Twilio console
 *   TWILIO_AUTH_TOKEN   its Auth Token: signs Twilio's requests, and ours
 *   TWILIO_FROM         the Australian mobile number, +614XXXXXXXX
 *   TWILIO_WA_FROM      the same number once Meta has approved it as a
 *                       WhatsApp sender; leave unset and everything is SMS
 *   TPL_QUESTION_SID    the Content SID (HX...) of "A quick question"
 *   TPL_ARRIVAL_SID     the Content SID (HX...) of "Your arrival"
 *   CONTACT_EMAIL       the machine login: six digits then @staff.nala
 *   CONTACT_PASSWORD    its six digits
 *   FB_API_KEY          AIzaSyA0zAzL-zfPivrIRhY_ip8BABjuYVMlzqI
 *   TEST_NUMBERS        your own phones, comma separated. While this is
 *                       set, nothing is sent to any other number: the
 *                       module runs on the live app without reaching a
 *                       guest. Delete it to go live.
 *   BUZZ                set to 1 once the push Worker (nala-push) knows
 *                       the events guestMessage and guestTask. Until then
 *                       nothing is sent to it: it is not in this repo, and
 *                       what it does with an event it does not know is
 *                       unknown. GUEST-CONTACT.md has the change it needs.
 *
 * The sandbox this was written in reaches neither Twilio nor Cloudflare.
 * worker/contact-test.mjs checks the logic against stubs; nothing here has
 * been run against the real services.
 */

const DB = "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app";
const TWILIO = "https://api.twilio.com/2010-04-01/Accounts/";
const PUSH_URL = "https://nala-push.ben-681.workers.dev";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};
const reply = (status, body) =>
  new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json", ...CORS } });
/* Twilio is answered with empty TwiML: nothing is sent back automatically.
   The desk answers, in words a person chose. */
const twiml = () => new Response('<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
  { status: 200, headers: { "Content-Type": "text/xml" } });

/* ── twins of nala-shared.js ─────────────────────────────────────
   A Worker cannot import from the site, so each rule the page and this
   Worker both apply lives in both, and both answer to one table:
   normalisePhone to tests/phone_cases.json, the rest to
   tests/contact_cases.json (CLAUDE.md rule 3). Exported for the test. */
export function normalisePhone(raw) {
  let s = String(raw == null ? "" : raw).replace(/[\s().\-]/g, "");
  if (/^0011[1-9]\d/.test(s))    s = "+" + s.slice(4);
  else if (/^00[1-9]\d/.test(s)) s = "+" + s.slice(2);
  if (/^04\d{8}$/.test(s))    return "+61" + s.slice(1);
  if (/^614\d{8}$/.test(s))   return "+" + s;
  if (/^\+61\d+$/.test(s))    return /^\+614\d{8}$/.test(s) ? s : null;
  if (/^\+[1-9]\d{7,14}$/.test(s)) return s;
  return null;
}

/* parseISO's twin: Safari's three fractional digits are the page's
   problem, but trimming here too keeps both copies reading every stamp
   the same way. */
function stampMs(s) {
  if (!s) return null;
  const t = String(s).trim().replace(/(\.\d{3})\d+/, "$1");
  let ms = Date.parse(t);
  if (isNaN(ms)) ms = Date.parse(t.replace(/\.\d+/, ""));
  return isNaN(ms) ? null : ms;
}

export const WA_WINDOW_MS = 24 * 60 * 60 * 1000;
export function waWindow(lastInWa, nowMs) {
  const at = stampMs(lastInWa);
  if (at == null) return { open: false, until: null };
  return { open: nowMs < at + WA_WINDOW_MS, until: at + WA_WINDOW_MS };
}
export function waAgreed(t) {
  if (!t || t.waBad) return false;
  return !!((t.wa && t.wa.on === true) || t.lastInWa);
}
export function contactChannel(t, nowMs) {
  t = t || {};
  if (t.optout) return { ch: "none", until: null };
  const inAt = stampMs(t.lastIn);
  if (inAt != null && nowMs - inAt < WA_WINDOW_MS)
    return t.lastInCh === "wa"
      ? { ch: "wa", until: inAt + WA_WINDOW_MS }
      : { ch: "sms", until: null };
  if (waAgreed(t)) return { ch: "watpl", until: null };
  return { ch: "sms", until: null };
}

export const CONTACT_TEMPLATES = [
  { id: "question",
    text: "Hi {first}, it's Nala Resort with a quick question about your stay. " +
          "Could you reply to this message when you have a moment?" },
  { id: "arrival",
    text: "Hi {first}, we look forward to welcoming you to Nala Resort on " +
          "{arrive}. If there is anything we can prepare before you arrive, " +
          "just reply to this message." }
];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                "August", "September", "October", "November", "December"];
/* A booking's arrival day in words. The date is the booking's own local
   day, read from its digits, never through a time zone. */
export function arriveWords(arrive) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(arrive || "").trim());
  if (!m) return "";
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return WEEKDAYS[d.getUTCDay()] + " " + d.getUTCDate() + " " + MONTHS[d.getUTCMonth()];
}
export function contactTemplateText(id, first, arrive) {
  const t = CONTACT_TEMPLATES.find((x) => x.id === id);
  if (!t) return "";
  first = String(first == null ? "" : first).trim() || "there";
  return t.text.split("{first}").join(first)
               .split("{arrive}").join(arriveWords(arrive) || "your arrival day");
}

/* ── who may do what ─────────────────────────────────────────────
   can() as nala-shared.js answers it, for the two things this Worker asks:
   editBookings, the desk - Chat's own gate, the same line the
   rules draw for the desk's writes - and guestReply, a reply to a guest
   (30 Sep, a switch per role in Settings, Roles). The admin and the
   manager always; an explicit matrix answer; else what the role ships
   with in ROLE_GRANTS. contact_cases.json "grants" holds both copies to
   one answer. */
const SHIPPED = { editBookings: ["waiter"], guestReply: ["waiter"] };
const NO_REPLY = "Replying to guests is switched off for this login. " +
                 "An admin can switch it on in Settings, General, Roles.";
export function mayDo(what, role, permissions) {
  role = role === "staff" ? "admin" : role;
  if (!SHIPPED[what]) return false;
  if (role === "admin" || role === "manager") return true;
  const row = permissions && permissions[what];
  if (row && typeof row[role] === "boolean") return row[role];
  return SHIPPED[what].indexOf(role) > -1;
}

const emailKey = (e) => String(e || "").trim().toLowerCase().replace(/\./g, ",");

/* ── the database ────────────────────────────────────────────────
   Reads that decide what a caller may see are made AS the caller, with
   their own token, so the rules answer for them. Messages are written as
   this Worker's login. */
let TOKEN = null, TOKEN_AT = 0;
async function machineToken(env) {
  if (TOKEN && Date.now() - TOKEN_AT < 50 * 60 * 1000) return TOKEN;
  const r = await fetch(
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + env.FB_API_KEY,
    { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: (env.CONTACT_EMAIL || "").trim(),
                             password: (env.CONTACT_PASSWORD || "").trim(),
                             returnSecureToken: true }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.idToken)
    throw new Error("the Worker's login failed: " + ((j.error && j.error.message) || r.status) +
                    " - check CONTACT_EMAIL and CONTACT_PASSWORD");
  TOKEN = j.idToken; TOKEN_AT = Date.now();
  return TOKEN;
}
export function forgetToken() { TOKEN = null; TOKEN_AT = 0; REFUSED = null; }   /* for the test */

async function db(env, path, method, body) {
  const t = await machineToken(env);
  const r = await fetch(DB + path + ".json?auth=" + encodeURIComponent(t), {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) throw new Error(method + " " + path + " refused: " + r.status);
  return r.status === 204 ? null : r.json();
}
async function dbAs(idToken, path) {
  const r = await fetch(DB + path + ".json?auth=" + encodeURIComponent(idToken));
  if (!r.ok) throw new Error("db read refused: " + path);
  return r.json();
}

/* ── Twilio ──────────────────────────────────────────────────────── */
const twilioAuth = (env) => "Basic " + btoa((env.TWILIO_ACCOUNT_SID || "").trim() + ":" +
                                              (env.TWILIO_AUTH_TOKEN || "").trim());

async function twilioSend(env, params) {
  const r = await fetch(TWILIO + (env.TWILIO_ACCOUNT_SID || "").trim() + "/Messages.json", {
    method: "POST",
    headers: { "Authorization": twilioAuth(env),
               "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(params).toString() }).catch(() => null);
  const j = r ? await r.json().catch(() => null) : null;
  if (r && r.ok && j && j.sid) return { ok: true, sid: j.sid, status: j.status || "queued" };
  return { ok: false,
           error: (j && (j.message || (j.code && "Twilio error " + j.code))) ||
                  (r ? "Twilio answered " + r.status : "Twilio did not answer") };
}

/* X-Twilio-Signature: HMAC-SHA1 of the URL Twilio called, then each posted
   parameter's name and value in name order, keyed with the Auth Token,
   base64. Exported for the test, which signs its own requests with it. */
export async function twilioSignature(authToken, url, params) {
  let data = url;
  for (const k of Object.keys(params).sort()) data += k + params[k];
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(authToken),
    { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(data)));
  let s = ""; for (const b of sig) s += String.fromCharCode(b);
  return btoa(s);
}
async function fromTwilio(request, env, params) {
  const got = request.headers.get("X-Twilio-Signature") || "";
  const token = (env.TWILIO_AUTH_TOKEN || "").trim();
  if (!got || !token) return false;
  const want = await twilioSignature(token, request.url, params);
  if (got.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= want.charCodeAt(i) ^ got.charCodeAt(i);
  return diff === 0;
}
/* A guest's photo. Twilio answers a media address with a redirect to a
   signed link on its storage, and the account's credentials go to Twilio
   only: a signed link refuses a request that also carries an Authorization
   header, and a runtime left to follow the redirect itself may keep it on. */
async function twilioMedia(env, url) {
  let r = await fetch(url, { headers: { "Authorization": twilioAuth(env) },
                             redirect: "manual" }).catch(() => null);
  const to = r && r.status >= 300 && r.status < 400 && r.headers.get("Location");
  if (to) {
    const next = new URL(to, url).toString();
    r = next.startsWith("https://") ? await fetch(next).catch(() => null) : null;
  }
  return r && r.ok ? r : null;
}
async function formOf(request) {
  const out = {};
  const f = await request.formData().catch(() => null);
  if (f) for (const [k, v] of f.entries()) out[k] = String(v);
  return out;
}

/* ── the test list ───────────────────────────────────────────────
   While TEST_NUMBERS is set, the Worker sends to those numbers and
   nothing else - the owner's condition for building on the live app
   (29 Sep): "tested without it actually sending messages to the guests".
   Checked here, where no page can get past it. */
function testList(env) {
  const raw = String(env.TEST_NUMBERS || "").trim();
  if (!raw) return null;
  /* Commas, semicolons or new lines between numbers - never spaces, which
     are inside a number as often as between two. */
  return raw.split(/[,;\n]+/).map(normalisePhone).filter(Boolean);
}
function mayMessage(env, phone) {
  const list = testList(env);
  return !list || list.indexOf(phone) > -1;
}

/* ── the words a guest may use ─────────────────────────────────── */
const STOP_WORDS = new Set(["STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END",
                            "QUIT", "OPTOUT", "REVOKE"]);
const START_WORDS = new Set(["START", "UNSTOP"]);
/* WhatsApp's "this number is not on WhatsApp", which the Worker answers by
   sending the same words as an SMS. */
const NO_WHATSAPP = new Set(["63024", "63003"]);

const previewOf = (body, media) => {
  const b = String(body || "").replace(/\s+/g, " ").trim();
  if (b) return b.length > 120 ? b.slice(0, 119) + "…" : b;
  return media && Object.keys(media).length ? "Photo" : "";
};
const newId = () => {
  const abc = "abcdefghijklmnopqrstuvwxyz0123456789";
  let r = ""; for (let i = 0; i < 6; i++) r += abc[Math.floor(Math.random() * abc.length)];
  return "o" + Date.now().toString(36) + r;
};
const RESORT_DAY = new Intl.DateTimeFormat("en-CA", { timeZone: "Australia/Brisbane",
  year: "numeric", month: "2-digit", day: "2-digit" });

/* The villa a number is staying in tonight, for the buzz. Best effort. */
async function villaOf(env, phone) {
  const stays = await db(env, "/stays/" + RESORT_DAY.format(new Date()), "GET").catch(() => null);
  for (const v of Object.keys(stays || {})) {
    const s = stays[v];
    if (s && typeof s === "object" && normalisePhone(s.phone) === phone) return String(v);
  }
  return "";
}

/* ── a guest's message arriving ─────────────────────────────────── */
/* The last text Twilio passed here that was refused, and why, for the
   setup check (30 Sep). Kept in the Worker's memory only: it holds no
   message, and a restart forgets it, which costs one more test text. */
let REFUSED = null;
async function inbound(request, env, ctx) {
  const p = await formOf(request);
  if (!(await fromTwilio(request, env, p))) {
    REFUSED = { at: new Date().toISOString(), why: (env.TWILIO_AUTH_TOKEN || "").trim()
      ? "its signature did not match TWILIO_AUTH_TOKEN. Copy the Auth Token again from the " +
        "Twilio console's home page, the live one, not a test credential"
      : "TWILIO_AUTH_TOKEN is not set on the Worker" };
    return new Response("not from Twilio", { status: 403 });
  }
  const raw = String(p.From || "");
  const wa = /^whatsapp:/i.test(raw);
  const phone = normalisePhone(raw.replace(/^whatsapp:/i, ""));
  if (!phone) return twiml();                 /* nothing a thread can be keyed on */
  const ck = phone.slice(1);
  const now = new Date().toISOString();
  const body = String(p.Body || "").slice(0, 1600);
  const media = {};
  const n = Math.min(parseInt(p.NumMedia, 10) || 0, 10);
  for (let i = 0; i < n; i++) {
    const url = String(p["MediaUrl" + i] || "");
    if (url.startsWith("https://api.twilio.com/"))
      media[i] = { url: url.slice(0, 500), type: String(p["MediaContentType" + i] || "").slice(0, 100) };
  }
  /* Keyed by Twilio's own id, so a retried webhook writes the same record
     rather than a second copy of the message. */
  const sid = String(p.MessageSid || p.SmsSid || "").replace(/[^A-Za-z0-9]/g, "").slice(0, 60);
  const id = "in-" + (sid || newId());
  const msg = { dir: "in", ch: wa ? "wa" : "sms", body, at: now };
  if (sid) msg.sid = sid;
  if (p.ProfileName) msg.profile = String(p.ProfileName).slice(0, 120);
  if (Object.keys(media).length) msg.media = media;

  const thread = { phone, lastAt: now, lastIn: now, lastInCh: msg.ch,
                   preview: previewOf(body, media), dir: "in" };
  if (wa) { thread.lastInWa = now; thread.waBad = null; }
  if (msg.profile) thread.profile = msg.profile;
  const word = body.trim().toUpperCase();
  if (STOP_WORDS.has(word)) thread.optout = { at: now, word };
  if (START_WORDS.has(word)) thread.optout = null;

  await db(env, "/contactmsgs/" + ck + "/" + id, "PUT", msg);
  await db(env, "/contactnew/" + ck + "/" + id, "PUT", true);
  await db(env, "/contact/" + ck, "PATCH", thread);

  /* Buzz the desk. Fire and tolerate: a lost buzz costs a buzz, the
     message is already safe. Only once BUZZ is set - see the secrets. */
  if (!String(env.BUZZ || "").trim()) return twiml();
  const buzz = (async () => {
    const villa = await villaOf(env, phone).catch(() => "");
    await fetch(PUSH_URL, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken: await machineToken(env), event: "guestMessage",
                             villa, url: "/guest-contact.html?c=" + ck }) });
  })().catch(() => {});
  if (ctx && ctx.waitUntil) ctx.waitUntil(buzz); else await buzz;
  return twiml();
}

/* ── a receipt for a message we sent ────────────────────────────── */
const RANK = { accepted: 0, scheduled: 0, queued: 1, sending: 2, sent: 3,
               delivered: 4, read: 5, undelivered: 6, failed: 6 };
async function receipt(request, env) {
  const p = await formOf(request);
  if (!(await fromTwilio(request, env, p))) return new Response("not from Twilio", { status: 403 });
  const q = new URL(request.url).searchParams;
  const ck = q.get("ck") || "", m = q.get("m") || "";
  if (!/^[1-9]\d{7,14}$/.test(ck) || !/^[A-Za-z0-9_-]{1,64}$/.test(m))
    return new Response("", { status: 200 });
  const status = String(p.MessageStatus || p.SmsStatus || "").toLowerCase();
  if (!(status in RANK)) return new Response("", { status: 200 });
  const rec = await db(env, "/contactmsgs/" + ck + "/" + m, "GET");
  if (!rec || rec.dir !== "out") return new Response("", { status: 200 });
  /* Receipts can arrive out of order: a late "delivered" must not
     overwrite "read". A failure always lands. */
  const was = RANK[rec.status] == null ? -1 : RANK[rec.status];
  const code = String(p.ErrorCode || "");
  if (RANK[status] >= was || status === "failed" || status === "undelivered") {
    const patch = { status, statusAt: new Date().toISOString() };
    if (code) patch.err = ("Error " + code + (p.ErrorMessage ? ": " + p.ErrorMessage : "")).slice(0, 300);
    await db(env, "/contactmsgs/" + ck + "/" + m, "PATCH", patch);
  }
  /* Not on WhatsApp: the same words go by SMS, once, and the number is
     remembered as SMS only until the guest writes on WhatsApp. */
  if (rec.ch === "wa" && (status === "failed" || status === "undelivered") &&
      NO_WHATSAPP.has(code) && !rec.fell) {
    await db(env, "/contact/" + ck, "PATCH", { waBad: true });
    const thread = await db(env, "/contact/" + ck, "GET").catch(() => null);
    const phone = normalisePhone("+" + ck);
    if (phone && mayMessage(env, phone) && !(thread && thread.optout) && rec.body) {
      const m2 = newId(), now = new Date().toISOString();
      await db(env, "/contactmsgs/" + ck + "/" + m, "PATCH", { fell: m2 });
      await db(env, "/contactmsgs/" + ck + "/" + m2, "PUT", { dir: "out", ch: "sms",
        body: rec.body, at: now, by: rec.by || "", kind: "fallback", of: m, status: "sending" });
      const sent = await twilioSend(env, { From: (env.TWILIO_FROM || "").trim(), To: phone,
        Body: rec.body, StatusCallback: statusUrl(request.url, ck, m2) });
      await db(env, "/contactmsgs/" + ck + "/" + m2, "PATCH", sent.ok
        ? { sid: sent.sid, status: sent.status }
        : { status: "failed", err: String(sent.error).slice(0, 300) });
    }
  }
  return new Response("", { status: 200 });
}
/* The booking's Mews record when this number is its guest's - Mews' own
   copy or the one the desk corrected at /phonefix - else null. Read as the
   caller, so the rules answer for them. */
async function bookingHolds(idToken, booking, phone) {
  const b = String(booking || "");
  if (!/^[A-Za-z0-9-]{4,64}$/.test(b)) return null;
  const pms = await dbAs(idToken, "/bookings/" + b + "/pms").catch(() => null);
  if (!pms) return null;
  const fix = await dbAs(idToken, "/phonefix/" + b).catch(() => null);
  return (normalisePhone(pms.phone) === phone ||
          (fix && normalisePhone(fix.phone) === phone)) ? pms : null;
}
function statusUrl(base, ck, m) {
  return new URL(base).origin + "/twilio/status?ck=" + ck + "&m=" + encodeURIComponent(m);
}

/* ── the setup check ─────────────────────────────────────────────
   Each line: ok true (working), false (to fix, and how) or null (only so
   you know). In the order the setup steps set them. */
export async function setupCheck(request, env) {
  const out = [];
  const add = (key, ok, say, at) => out.push(at ? { key, ok, say, at } : { key, ok, say });
  const sid = (env.TWILIO_ACCOUNT_SID || "").trim(), tok = (env.TWILIO_AUTH_TOKEN || "").trim();
  const from = normalisePhone(env.TWILIO_FROM || "");
  const want = new URL(request.url).origin + "/twilio/in";
  const tw = (path) => fetch(TWILIO + sid + path, { headers: { "Authorization": twilioAuth(env) } })
    .catch(() => null);

  /* 1. Twilio's keys, asked of Twilio itself */
  let acct = null;
  if (!sid || !tok) {
    add("twilio", false, (!sid ? "TWILIO_ACCOUNT_SID" : "TWILIO_AUTH_TOKEN") +
                         " is not set on the Worker (step 5).");
  } else {
    const r = await tw(".json");
    acct = r && r.ok ? await r.json().catch(() => null) : null;
    if (!r) add("twilio", false, "Twilio could not be reached just now. Check again in a minute.");
    else if (r.status === 401 || r.status === 404)
      add("twilio", false, "Twilio refuses TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN. Copy both again " +
                           "from the Twilio console's home page, Account Info (step 5).");
    else if (!acct) add("twilio", false, "Twilio answered " + r.status + " when asked for the account.");
    else if (acct.status && acct.status !== "active")
      add("twilio", false, "The Twilio account is " + acct.status + ", not active.");
    else if (String(acct.type || "").toLowerCase() === "trial")
      add("twilio", false, "The Twilio account is still a trial, which can only text phones " +
                           "verified in Twilio. Upgrade it (step 3).");
    else add("twilio", true, "Twilio accepts the Account SID and the Auth Token.");
  }

  /* 2. the number, and where Twilio hands its texts */
  if (!from) {
    add("number", false, env.TWILIO_FROM
      ? "TWILIO_FROM is not a number Chat can send from: it should read +614 and eight digits."
      : "TWILIO_FROM is not set on the Worker (step 5).");
  } else if (acct) {
    const r = await tw("/IncomingPhoneNumbers.json?PhoneNumber=" + encodeURIComponent(from));
    const j = r && r.ok ? await r.json().catch(() => null) : null;
    const n = j && Array.isArray(j.incoming_phone_numbers) ? j.incoming_phone_numbers[0] : null;
    if (!n) add("number", false, "TWILIO_FROM, " + from + ", is not a number on this Twilio account.");
    else {
      add("number", true, "The number " + from + " is on the Twilio account.");
      const url = String(n.sms_url || "").trim(), how = String(n.sms_method || "").toUpperCase();
      if (url === want && how === "POST") add("webhook", true, "Twilio hands the number's texts to Chat.");
      else add("webhook", false, "Twilio hands the number's texts to " +
        (url ? url + " by " + (how || "an unknown method") : "nowhere") + ". It should be " + want +
        " by HTTP POST: Active numbers, the number, A message comes in (step 6).");
    }
  }

  /* 3. the Worker's own login, its role, and the rules */
  let signed = false;
  if (!(env.CONTACT_EMAIL || "").trim() || !(env.CONTACT_PASSWORD || "").trim()) {
    add("login", false, ((env.CONTACT_EMAIL || "").trim() ? "CONTACT_PASSWORD" : "CONTACT_EMAIL") +
                        " is not set on the Worker (step 5).");
  } else {
    try { await machineToken(env); signed = true; add("login", true, "The Chat Worker signs in."); }
    catch (e) {
      const m = String((e && e.message) || e);
      add("login", false, /API key/i.test(m)
        ? "FB_API_KEY is not the app's key: paste it again from step 5."
        : "The Chat Worker cannot sign in (" + m.replace(/^the Worker's login failed: /, "")
            .replace(/ - check.*$/, "") + "). CONTACT_EMAIL must be its six digit passcode then " +
          "@staff.nala, and CONTACT_PASSWORD the same six digits (steps 2 and 5).");
    }
  }
  if (signed) {
    const who = String(env.CONTACT_EMAIL).trim();
    const rec = await db(env, "/staff/" + emailKey(who), "GET").catch(() => undefined);
    const threads = await db(env, "/contact/0", "GET").then(() => true).catch(() => false);
    if (rec === undefined || !threads)
      add("rules", false, "The database refuses the Chat Worker: publish the rules (step 1), and " +
                          "check its role is contact in Settings (step 2).");
    else if (!rec || rec.role !== "contact")
      /* The address is never said: its six digits are the Worker's password. */
      add("rules", false, (rec ? "Settings gives the Chat Worker's login the role " + (rec.role || "none")
                                : "Settings has no one with the Chat Worker's login") +
                          ": it should be the Chat Worker, role contact (step 2).");
    else add("rules", true, "The database takes the guests' messages from the Chat Worker.");
  }

  /* 4. the last text refused, while the Worker remembers it */
  if (REFUSED)
    add("inbound", false, "The last text Twilio passed here was refused: " + REFUSED.why + ".", REFUSED.at);

  /* 5. only so you know */
  const tl = testList(env);
  add("test", null, tl ? "Test mode is on: Chat can only message " + tl.length +
                         (tl.length === 1 ? " phone" : " phones") + ", the ones in TEST_NUMBERS."
                       : "Test mode is off: Chat can message any guest.");
  add("whatsapp", null, (env.TWILIO_WA_FROM || "").trim()
    ? "WhatsApp is set up on " + normalisePhone(env.TWILIO_WA_FROM) + "."
    : "WhatsApp is not set up yet, so everything goes by SMS.");
  return out;
}

/* ── the desk ────────────────────────────────────────────────────── */
async function desk(request, env) {
  let body;
  try { body = await request.json(); }
  catch { return reply(400, { error: "not JSON" }); }
  const { idToken, kind } = body || {};
  if (!idToken) return reply(401, { error: "no idToken" });
  if (["hello", "send", "media", "tasklog", "taskmedia", "check"].indexOf(kind) < 0)
    return reply(400, { error: "unknown kind" });

  /* 1. Who is asking, from the token: accounts:lookup checks the signature,
     the expiry and the project, and names the account. */
  const look = await fetch(
    "https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=" + env.FB_API_KEY,
    { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idToken }) }).catch(() => null);
  const who = look ? await look.json().catch(() => null) : null;
  const email = look && look.ok && who && who.users && who.users[0] && who.users[0].email;
  if (!email) return reply(401, { error: "sign in again" });

  /* 2. What the role may do: editBookings is the desk, Chat's own
     gate; guestReply is a reply to a guest, from there or a task's card. */
  let staffRec, permissions;
  try {
    staffRec = await dbAs(idToken, "/staff/" + emailKey(email));
    permissions = await dbAs(idToken, "/permissions").catch(() => null);
  } catch {
    return reply(403, { error: "could not read the staff record" });
  }
  const role = staffRec && staffRec.role;
  const deskOk = mayDo("editBookings", role, permissions);
  const replyOk = mayDo("guestReply", role, permissions);

  /* The teams Settings puts this login on: the desk acts for any. Read as
     the caller, and only when a team's door needs it. */
  const settings = !deskOk && ["tasklog", "taskmedia", "send"].indexOf(kind) > -1
    ? await dbAs(idToken, "/contactsettings").catch(() => null) : null;
  const onTeam = (team) => deskOk || !!(settings && settings.teams && settings.teams[team] &&
    settings.teams[team].members && settings.teams[team].members[emailKey(email)] === true);
  /* A task of a team this login may act for, read as the caller. */
  const taskOf = async (team, t) => {
    if (!/^[a-z]{2,20}$/.test(team) || !/^[A-Za-z0-9_-]{1,64}$/.test(t) || !onTeam(team)) return null;
    const task = await dbAs(idToken, "/tasks/" + team + "/" + t).catch(() => null);
    return task && /^[1-9]\d{7,14}$/.test(String(task.ck || "")) ? task : null;
  };

  /* ── a team's view of its own tasks (29 Sep) ─────────────────────
     The owner, on the first build: the login doing a task "can only see
     what the guest has requested ... can't see any of the responses". A
     team's login reads no conversation - the rules keep it so, and the
     masseuse is an outside contractor - so this door hands it the part of
     one that belongs to its task: every message from the request until
     the task is done, nothing before it. The desk may ask for any team's
     tasks; any other login only for a team Settings puts it on. */
  if (kind === "tasklog" || kind === "taskmedia") {
    const excerpt = async (team, t) => {
      const task = await taskOf(team, t);
      if (!task) return null;
      const ck = String(task.ck);
      const msgs = (await db(env, "/contactmsgs/" + ck, "GET").catch(() => null)) || {};
      const src = msgs[task.msg];
      const from = stampMs(src && src.at) != null ? stampMs(src.at) : (stampMs(task.at) || 0);
      const until = task.state === "done" && stampMs(task.doneAt) != null ? stampMs(task.doneAt) : Infinity;
      /* A later request the desk made into another team's task is that
         team's to read, not this one's: the candle is the kitchen's, even
         when it came after the umbrella. */
      const theirs = (m) => m.dir === "in" && m.tasks && typeof m.tasks === "object" &&
                            Object.keys(m.tasks).length > 0 && !m.tasks[team];
      const ids = Object.keys(msgs).filter((id) => {
        const at = stampMs(msgs[id] && msgs[id].at);
        return at != null && at >= from && at <= until && !theirs(msgs[id]);
      }).sort((a, b) => (stampMs(msgs[a].at) - stampMs(msgs[b].at)) || (a < b ? -1 : 1));
      return { msgs, ids, task, ck };
    };
    if (kind === "tasklog") {
      const logs = {}, routes = {}, threads = {};
      const waOn = !!(env.TWILIO_WA_FROM || "").trim(), now = Date.now();
      for (const it of (Array.isArray(body.tasks) ? body.tasks.slice(0, 40) : [])) {
        const team = String((it && it.team) || ""), t = String((it && it.t) || "");
        const x = await excerpt(team, t);
        if (!x) continue;
        /* Which way a reply from this card would go, for a login that may
           send one (30 Sep): the thread as the Worker reads it, since a
           team's login reads none. Only while the task is open. */
        if (replyOk && x.task.state === "open") {
          if (!(x.ck in threads))
            threads[x.ck] = (await db(env, "/contact/" + x.ck, "GET").catch(() => null)) || {};
          const c = contactChannel(threads[x.ck], now);
          routes[team + "/" + t] = (!waOn && (c.ch === "wa" || c.ch === "watpl"))
            ? { ch: "sms", until: null } : c;
        }
        /* The words and who said them; never a photo's address, which
           only this Worker may fetch. */
        logs[team + "/" + t] = x.ids.slice(-40).map((id) => {
          const m = x.msgs[id];
          return { id, dir: m.dir === "out" ? "out" : "in", ch: m.ch === "wa" ? "wa" : "sms",
                   body: String(m.body || "").slice(0, 1600), at: m.at,
                   by: m.dir === "out" ? String(m.by || "") : "",
                   photos: m.media ? Object.keys(m.media).length : 0 };
        });
      }
      return reply(200, { logs, routes });
    }
    /* taskmedia: a photo inside the task's stretch of the conversation. */
    const m = String(body.m || ""), i = String(body.i || "0");
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(m) || !/^[0-9]$/.test(i)) return reply(400, { error: "bad photo" });
    const x = await excerpt(String(body.team || ""), String(body.t || ""));
    if (!x) return reply(403, { error: "not one of this login's tasks" });
    const tm = x.ids.indexOf(m) > -1 && x.msgs[m].media && x.msgs[m].media[i];
    if (!tm || !String(tm.url || "").startsWith("https://api.twilio.com/"))
      return reply(404, { error: "no such photo" });
    const tr = await twilioMedia(env, tm.url);
    if (!tr) return reply(502, { error: "Twilio would not give the photo" });
    return new Response(tr.body, { status: 200, headers: {
      "Content-Type": tr.headers.get("Content-Type") || tm.type || "application/octet-stream",
      "Cache-Control": "private, max-age=3600", ...CORS } });
  }

  if (!deskOk && kind !== "send") return reply(403, { error: "this login may not use Chat" });
  /* Reply to guests, the switch per role in Settings (30 Sep): every send,
     the desk's and a team's, stops here without it. */
  if (kind === "send" && !replyOk) return reply(403, { error: NO_REPLY });

  /* ── the setup check (30 Sep) ──────────────────────────────────
     The owner, a test text refused and a Twilio console that would not say
     why: "Why don't you just create an error webhook url". So the Worker
     checks itself - each thing the setup steps set - and Chat says, in
     plain words, what is wrong, where the admin already looks. Nothing
     secret leaves it: which settings are there, whether Twilio and
     Firebase accept them, and where Twilio sends the number's texts. */
  if (kind === "check") {
    const r = role === "staff" ? "admin" : role;
    if (r !== "admin" && r !== "manager")
      return reply(403, { error: "Only the admin and the manager see the setup check" });
    return reply(200, { check: await setupCheck(request, env) });
  }

  const test = !!testList(env);
  if (kind === "hello")
    return reply(200, { test, wa: !!(env.TWILIO_WA_FROM || "").trim(),
                        buzz: !!String(env.BUZZ || "").trim(),
                        ready: !!((env.TWILIO_ACCOUNT_SID || "").trim() && (env.TWILIO_FROM || "").trim()) });

  /* A reply from a team's task card (30 Sep): a login that is not the
     desk may message only the guest of an open task on one of its teams,
     and only if Settings lets its role reply. The guest is the task's,
     never a number the page names. */
  let task = null;
  if (!deskOk) {
    task = await taskOf(String(body.team || ""), String(body.t || ""));
    if (!task || task.state !== "open")
      return reply(403, { error: "That is not an open task of this login's teams" });
    if (body.template) return reply(400, { error: "An approved message goes from Chat" });
  }
  const ck = task ? String(task.ck) : String(body.ck || "");
  if (!/^[1-9]\d{7,14}$/.test(ck)) return reply(400, { error: "bad guest number" });

  if (kind === "media") {
    /* The photo's address comes off the stored message, never the browser:
       this door fetches with the account's credentials, so it must only
       ever fetch what Twilio itself told us about. */
    const m = String(body.m || ""), i = String(body.i || "0");
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(m) || !/^[0-9]$/.test(i)) return reply(400, { error: "bad photo" });
    const md = await dbAs(idToken, "/contactmsgs/" + ck + "/" + m + "/media/" + i).catch(() => null);
    if (!md || !String(md.url || "").startsWith("https://api.twilio.com/"))
      return reply(404, { error: "no such photo" });
    const r = await twilioMedia(env, md.url);
    if (!r) return reply(502, { error: "Twilio would not give the photo" });
    return new Response(r.body, { status: 200, headers: {
      "Content-Type": r.headers.get("Content-Type") || md.type || "application/octet-stream",
      "Cache-Control": "private, max-age=3600", ...CORS } });
  }

  /* ── kind "send" ── */
  /* The desk reads the thread as itself; a team's login reads none, so for
     its task the Worker does. */
  const thread = (task ? await db(env, "/contact/" + ck, "GET").catch(() => null)
                       : await dbAs(idToken, "/contact/" + ck).catch(() => null)) || {};
  const phone = normalisePhone(thread.phone || "+" + ck);
  if (!phone || phone.slice(1) !== ck) return reply(400, { error: "bad guest number" });
  if (thread.optout)
    return reply(409, { error: "This guest texted " + (thread.optout.word || "STOP") +
                               ". Nothing can be sent until they text START." });
  if (!mayMessage(env, phone))
    return reply(403, { test: true, error: "Test mode: only the test phones can be messaged. " +
                                           "Remove TEST_NUMBERS in Cloudflare to go live." });
  if (!(env.TWILIO_ACCOUNT_SID || "").trim() || !(env.TWILIO_FROM || "").trim())
    return reply(503, { error: "Twilio is not set up yet" });

  /* A first message goes only to a number on a booking: the page names the
     booking and the number is checked against it here, Mews' copy or the
     desk's corrected one. Once a thread exists - the guest wrote, or we
     did - it is the guest's own number and needs no booking. Without this
     an edited page could text anyone from the resort's number. */
  if (!thread.lastAt && (task || !(await bookingHolds(idToken, body.booking, phone))))
    return reply(400, { error: "That number is not on the guest's booking" });

  const now = Date.now();
  const waOn = !!(env.TWILIO_WA_FROM || "").trim();
  let route = contactChannel(thread, now).ch;
  if (!waOn && (route === "wa" || route === "watpl")) route = "sms";
  const via = body.via === "sms" ? "sms" : "";
  const tplId = body.template ? String(body.template) : "";

  let ch, text = "", params;
  if (tplId) {
    const tpl = CONTACT_TEMPLATES.find((x) => x.id === tplId);
    if (!tpl) return reply(400, { error: "no such approved message" });
    if (!waOn || !waAgreed(thread))
      return reply(409, { error: "This guest has not asked for WhatsApp: send an SMS instead" });
    const sidEnv = (env["TPL_" + tplId.toUpperCase() + "_SID"] || "").trim();
    if (!sidEnv) return reply(503, { error: "That approved message is not set up in Twilio yet" });
    /* The name and the day come off the booking here, not from the page:
       an approved message must not become a way to send free text. */
    let first = "", arrive = "";
    const pms = await bookingHolds(idToken, body.booking, phone);
    if (pms) {
      first = String(pms.first || "").trim().slice(0, 40);
      arrive = String(pms.arrive || "");
    }
    if (tplId === "arrival" && !arriveWords(arrive))
      return reply(400, { error: "Your arrival needs the guest's booking" });
    ch = "wa";
    text = contactTemplateText(tplId, first, arrive);
    /* Only the variables the approved wording holds: {{1}} the name, and
       for Your arrival {{2}} the day. */
    const vars = { 1: first || "there" };
    if (tplId === "arrival") vars[2] = arriveWords(arrive);
    params = { ContentSid: sidEnv, ContentVariables: JSON.stringify(vars) };
  } else {
    text = typeof body.text === "string" ? body.text.trim() : "";
    if (!text || text.length > 1000) return reply(400, { error: "bad message" });
    if (via === "sms") ch = "sms";
    else if (route === "watpl")
      return reply(409, { window: "closed", error: "More than 24 hours since this guest last " +
        "wrote on WhatsApp: choose an approved message, or send an SMS" });
    else ch = route;
    params = { Body: text };
  }

  /* Recorded BEFORE it goes, so a receipt that beats the reply still finds
     its message, and a send that dies half way leaves a trace. */
  const m = newId(), at = new Date(now).toISOString();
  const rec = { dir: "out", ch, body: text, at, by: email,
                kind: tplId ? "template" : "staff", status: "sending" };
  if (tplId) rec.tpl = tplId;
  try { await db(env, "/contactmsgs/" + ck + "/" + m, "PUT", rec); }
  catch (e) { return reply(500, { error: "could not record the message, so it was not sent" }); }

  const from = ch === "wa" ? "whatsapp:" + (env.TWILIO_WA_FROM || "").trim() : (env.TWILIO_FROM || "").trim();
  const sent = await twilioSend(env, Object.assign({ From: from,
    To: ch === "wa" ? "whatsapp:" + phone : phone,
    StatusCallback: statusUrl(request.url, ck, m) }, params));
  await db(env, "/contactmsgs/" + ck + "/" + m, "PATCH", sent.ok
    ? { sid: sent.sid, status: sent.status }
    : { status: "failed", err: String(sent.error).slice(0, 300) }).catch(() => {});
  await db(env, "/contact/" + ck, "PATCH", { phone, lastAt: at, lastOut: at,
    preview: previewOf(text), dir: "out" }).catch(() => {});
  if (!sent.ok) return reply(502, { id: m, ch, error: "Not sent: " + sent.error });
  return reply(200, { id: m, ch, status: sent.status, test });
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (request.method !== "POST") return reply(405, { error: "POST only" });
    const path = new URL(request.url).pathname;
    try {
      if (path === "/twilio/in") return await inbound(request, env, ctx);
      if (path === "/twilio/status") return await receipt(request, env);
      return await desk(request, env);
    } catch (e) {
      const why = String((e && e.message) || e).slice(0, 200);
      if (path === "/twilio/in") REFUSED = { at: new Date().toISOString(), why };
      return reply(500, { error: why });
    }
  }
};
