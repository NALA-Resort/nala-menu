/* Invitations Worker suite. Run: node worker/invites-test.mjs
 *
 * Firebase and ClickSend are stubbed. Green here checks the logic and says
 * nothing about the real services: no ClickSend account exists yet, and the
 * sandbox reaches neither ClickSend nor Cloudflare. HANDOVER.md's warning
 * applies in full.
 */
import worker, { normalisePhone as workerNorm, SPA_AHEAD_DAYS,
                 spaReminderText as workerSpaText } from "./send-invites.js";
import { readFileSync } from "node:fs";

let P = 0, F = 0;
const ck = (name, ok) => { ok ? P++ : F++; console.log((ok ? "PASS " : "FAIL ") + name); };

/* ── one table, two copies of one rule ──────────────────────────
   The page decides sendability with normalisePhone in nala-shared.js; this
   Worker sends with its own copy, because a Worker cannot import from the
   site. Two copies of one rule is the thing that goes stale, so both are held
   to ONE table, tests/phone_cases.json, which inv_suite.py runs through the
   page's copy as well. A table written out again here would be a third copy
   with the same problem. The shared function is cut out of nala-shared.js by
   matching its braces - a window of characters is what left four pages of
   broken JavaScript on 23 Aug - and evaluated beside the Worker's. */
const CASES = JSON.parse(
  readFileSync(new URL("../tests/phone_cases.json", import.meta.url), "utf8")
).cases.map(([given, want]) => [given, want]);
{
  const src = readFileSync(new URL("../nala-shared.js", import.meta.url), "utf8");
  const i = src.indexOf("function normalisePhone");
  const j = src.indexOf("{", i);
  let depth = 0, end = j;
  for (let k = j; k < src.length; k++) {
    if (src[k] === "{") depth++;
    else if (src[k] === "}" && --depth === 0) { end = k + 1; break; }
  }
  const sharedNorm = new Function("return " + src.slice(i, end))();
  let agree = true, right = true;
  for (const [given, want] of CASES) {
    if (sharedNorm(given) !== workerNorm(given)) agree = false;
    if (workerNorm(given) !== want) right = false;
  }
  ck("the page's rule and the Worker's agree on every case in the table", agree);
  ck("and both say what the table says", right);
}

const env = { CLICKSEND_USERNAME: "u", CLICKSEND_API_KEY: "k",
              CLICKSEND_FROM: "+61400000000", FB_API_KEY: "fb" };

const today = (() => { const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") +
         "-" + String(d.getDate()).padStart(2, "0"); })();

/* One in-memory world per test. SENDS logs what reached ClickSend, STORE what
   reached the database, LOOKUPS which tokens Google was asked about. */
let STORE, SENDS, STATE, TSENDS;

function install() {
  STORE = {}; SENDS = []; TSENDS = [];
  STATE = { tokenOk: true, email: "waiter@nala.x", clicksendOk: true,
            recordOk: true, linksOk: true, manualOk: true };
  STORE["/staff/waiter@nala,x"] = { role: "waiter" };
  STORE["/staff/hk@nala,x"] = { role: "housekeeping" };
  STORE["/staff/old@nala,x"] = { role: "staff" };   /* the pre-rename records */
  STORE["/staff/mgr@nala,x"] = { role: "manager" }; /* admin minus manageStaff */
  STORE["/menu"] = { main: { name: "Barramundi" },
                     published: new Date().toISOString() };
  STORE["/stays/" + today + "/4"] =
    { id: "b4-guid", first: "Robyn", last: "Williams", phone: "+61 411 222 333" };
  STORE["/stays/" + today + "/7"] =
    { id: "b7-guid", first: "Mark", last: "Whitfield", phone: "" };
  STORE["/stays/" + today + "/9"] =
    { id: "b9-guid", first: "Nadia", last: "Okonkwo", phone: "02 9999 9999" };
  const plus = (days) => { const d = new Date(Date.now() + days * 86400000);
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") +
           "-" + String(d.getDate()).padStart(2, "0"); };
  STORE["/bookings/bk-future/pms"] =
    { arrive: plus(5), depart: plus(8), villa: 6, phone: "0411 222 333",
      first: "Harper", last: "Quinn" };
  STORE["/bookings/bk-past/pms"] =
    { arrive: plus(-10), depart: plus(-7), villa: 3, phone: "0411 222 333" };
  STORE["/bookings/bk-novilla/pms"] =
    { arrive: plus(2), phone: "+61 400 111 222" };
  globalThis.fetch = async (url, opt = {}) => {
    const u = String(url);
    if (u.includes("accounts:lookup")) {
      if (!STATE.tokenOk) return new Response(JSON.stringify({ error: {} }), { status: 400 });
      return new Response(JSON.stringify({ users: [{ email: STATE.email }] }), { status: 200 });
    }
    if (u.includes("/v3/sms/receipts/")) {
      const rc = STATE.receipt;
      if (!rc) return new Response(JSON.stringify({ data: null }), { status: 200 });
      return new Response(JSON.stringify({ data: rc }), { status: 200 });
    }
    /* Twilio, for SMS_VIA=twilio: a send, and a message looked up by id
       for its receipt. twilioOk false is Twilio refusing the number. */
    if (u.startsWith("https://api.twilio.com/") && u.endsWith("/Messages.json")) {
      const form = Object.fromEntries(new URLSearchParams(opt.body));
      TSENDS.push({ form, auth: opt.headers && opt.headers.Authorization });
      if (STATE.twilioOk === false)
        return new Response(JSON.stringify({ code: 21211,
          message: "The 'To' number is not a valid phone number." }), { status: 400 });
      const sid = "SM" + String(TSENDS.length).padStart(32, "0");
      return new Response(JSON.stringify({ sid, status: "queued" }), { status: 201 });
    }
    if (u.startsWith("https://api.twilio.com/")) {
      const t = STATE.twilioMsg;
      return t ? new Response(JSON.stringify(t), { status: 200 })
               : new Response(JSON.stringify({ code: 20404 }), { status: 404 });
    }
    if (u.includes("clicksend.com")) {
      SENDS.push(JSON.parse(opt.body));
      if (!STATE.clicksendOk)
        return new Response(JSON.stringify({ data: { messages: [{ status: "INVALID_RECIPIENT" }] } }), { status: 200 });
      return new Response(JSON.stringify({ data: { messages: [{ status: "SUCCESS", message_id: "mid-1" }] } }), { status: 200 });
    }
    const path = u.split("firebasedatabase.app")[1].split(".json")[0];
    if (opt.method === "DELETE") { delete STORE[path]; return new Response("null", { status: 200 }); }
    if ((opt.method || "GET") === "PUT") {
      /* manualOk gates an external guest's booking: the rules paste not
         made, so the database refuses the status 'awaiting'. */
      if (!STATE.manualOk && path.startsWith("/manual/"))
        return new Response("no", { status: 401 });
      /* recordOk gates the /invites record alone: the send-worked-but-the-
         record-did-not case. linksOk gates the token store, which fails a
         villa BEFORE anything is sent. */
      if (!STATE.recordOk && (path.startsWith("/invites/") || path.startsWith("/spareminders/")))
        return new Response("no", { status: 401 });
      if (!STATE.linksOk && path.startsWith("/links/"))
        return new Response("no", { status: 401 });
      /* oldRules: the rules before the paste that knows earlier, which
         refuse it on the pre-arrival and spa records. */
      if (STATE.oldRules && /^\/(previnvites|spareminders)\//.test(path) && "earlier" in JSON.parse(opt.body))
        return new Response("no", { status: 401 });
      STORE[path] = JSON.parse(opt.body);
      return new Response(opt.body, { status: 200 });
    }
    return new Response(JSON.stringify(STORE[path] ?? null), { status: 200 });
  };
}

const post = (over = {}) => worker.fetch(new Request("https://w.dev/", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ idToken: "T", date: today, villas: ["4"],
                         template: "ready",
                         body: "Tonight's menu is ready. Nala Resort\n<menu>",
                         ...over }) }), env);

/* ── who may call ───────────────────────────────────────────── */
install(); STATE.tokenOk = false;
let r = await post();
ck("an unverifiable token is refused", r.status === 401);
ck("and nothing was sent", SENDS.length === 0);

install(); STATE.email = "hk@nala.x";
r = await post();
ck("a role without editBookings is refused", r.status === 403);
ck("and nothing was sent for it either", SENDS.length === 0);

install(); STATE.email = "old@nala.x";
r = await post();
ck("a record still saying staff sends, read as admin", r.status === 200);

install(); STATE.email = "mgr@nala.x";
r = await post();
ck("a manager sends: the role is the admin's grants minus manageStaff",
   r.status === 200);

install();
STORE["/permissions"] = { editBookings: { waiter: false } };
r = await post();
ck("the permission matrix wins where it has an opinion", r.status === 403);

/* ── the message ────────────────────────────────────────────── */
install();
r = await post({ body: "See https://evil.example/x" });
ck("a body carrying a URL is refused whole", r.status === 400);
ck("and never reached ClickSend", SENDS.length === 0);

install();
r = await post({ date: "2020-01-01" });
ck("a written-out past date is refused", r.status === 400);

/* ── the link is rebuilt here, from the record ──────────────── */
install();
r = await post();
let j = await r.json();
ck("a good send answers per villa", j.results["4"].status === "sent");
/* SMS_VIA unset: ClickSend, as it always was (the Twilio move is below). */
ck("and without SMS_VIA it went through ClickSend, not Twilio",
   SENDS.length === 1 && TSENDS.length === 0);
const sentBody = (SENDS[0] || { messages: [{ body: "" }] }).messages[0].body;
const sentToken = (sentBody.match(/\?t=([a-z0-9]+)/) || [])[1] || "";
ck("the SMS carries our short link: the domain and a 6 character token",
   /https:\/\/menu\.nalaresort\.com\/\?t=[a-z2-9]{6}/.test(sentBody));
ck("the token record holds the booking id AND the villa, off the stay record",
   !!STORE["/links/" + sentToken] &&
   STORE["/links/" + sentToken].b === "b4-guid" &&
   STORE["/links/" + sentToken].r === "4");
ck("and the record keeps the token, so the link can be chased later",
   j.results && STORE["/invites/" + today + "/4"].token === sentToken);
ck("the marker was replaced, not appended twice",
   (sentBody.match(/menu\.nalaresort\.com/g) || []).length === 1);
ck("the number came off the stay record, normalised to E.164",
   SENDS[0].messages[0].to === "+61411222333");
ck("and the record holds the number AS SENT", true);   /* pinned below */
ck("and it goes out from the own number", SENDS[0].messages[0].from === "+61400000000");
let rec = STORE["/invites/" + today + "/4"];
ck("the send is recorded", !!rec && rec.status === "sent");
ck("with what actually went, after any edit", rec.body === sentBody);
ck("and the number as sent, not as Mews held it", rec.to === "+61411222333");
ck("and who pressed send, from the token", rec.by === "waiter@nala.x");
ck("and ClickSend's message id", rec.providerId === "mid-1");

install();
r = await post({ body: "Menu tonight.\nNala Resort" });
ck("a body whose marker was edited out still gets the link, at the end",
   /\nhttps:\/\/menu\.nalaresort\.com\/\?t=[a-z2-9]{6}$/.test(SENDS[0].messages[0].body));

install();
r = await post({ body: "Menu tonight. Nala Resort\n<link>" });
ck("the marker's old name <link> still resolves, for anything saved before the rename",
   /\nhttps:\/\/menu\.nalaresort\.com\/\?t=[a-z2-9]{6}$/.test(SENDS[0].messages[0].body) &&
   !SENDS[0].messages[0].body.includes("<link>"));

install(); STATE.linksOk = false;
r = await post();
j = await r.json();
ck("a token the database refuses fails the villa with nothing sent",
   j.results["4"].status === "failed" && SENDS.length === 0);

/* ── failures are per villa and every one is recorded ───────── */
install();
r = await post({ villas: ["4", "7", "9", "12"] });
j = await r.json();
ck("the villa with no number fails alone", j.results["7"].status === "failed");
ck("naming the reason", /phone/.test(j.results["7"].error));
ck("the villa with no stay fails alone", j.results["12"].status === "failed");
ck("a landline is refused rather than guessed at",
   j.results["9"].status === "failed" && /normalised/.test(j.results["9"].error));
ck("with the raw number in the reason, so it can be chased in Mews",
   /02 9999 9999/.test(STORE["/invites/" + today + "/9"].error));
ck("and it never reached ClickSend", SENDS.length === 1);
ck("the good villa still went", j.results["4"].status === "sent");
ck("a failure is recorded too", STORE["/invites/" + today + "/7"].status === "failed");
ck("with no message body, because none was built",
   STORE["/invites/" + today + "/7"].body === "");

install(); STATE.clicksendOk = false;
r = await post();
j = await r.json();
ck("a ClickSend refusal is a failed villa, not a crash",
   j.results["4"].status === "failed" && /INVALID_RECIPIENT/.test(j.results["4"].error));
ck("and it is on the record verbatim",
   /INVALID_RECIPIENT/.test(STORE["/invites/" + today + "/4"].error));

install(); STATE.recordOk = false;
r = await post();
j = await r.json();
ck("a send whose record failed says so rather than reporting a clean send",
   j.results["4"].status === "sent-unrecorded");

/* ── the menu backstop ──────────────────────────────────────── */
install(); STORE["/menu"] = null;
r = await post();
ck("no menu, no sending, whatever the browser claimed", r.status === 409);

install();
STORE["/menu"].published = new Date(Date.now() - 48 * 3600 * 1000).toISOString();
r = await post();
ck("a stale publish stamp is no menu", r.status === 409);

/* ── kind "pre": the pre-arrival form, per booking ──────────── */
const pre = (over = {}) => worker.fetch(new Request("https://w.dev/", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ idToken: "T", kind: "pre", bookings: ["bk-future"],
                         template: "before",
                         body: "Ahead of your stay, a few questions. Nala Resort\n<form>",
                         ...over }) }), env);

install(); STORE["/menu"] = null;
r = await pre();
j = await r.json();
ck("a pre-arrival send needs no menu: the form exists either way",
   r.status === 200 && j.results["bk-future"].status === "sent");
const preBody = SENDS[0].messages[0].body;
const preTok = (preBody.match(/\?t=([a-z0-9]+)/) || [])[1] || "";
ck("the SMS carries the form's short link, not the menu's",
   /https:\/\/menu\.nalaresort\.com\/prearrival\.html\?t=[a-z2-9]{6}$/.test(preBody));
ck("the <form> marker was replaced, once",
   !preBody.includes("<form>") &&
   (preBody.match(/menu\.nalaresort\.com/g) || []).length === 1);
ck("the token resolves to the booking, its villa and its arrival date",
   !!STORE["/links/" + preTok] &&
   STORE["/links/" + preTok].b === "bk-future" &&
   STORE["/links/" + preTok].r === "6" &&
   STORE["/links/" + preTok].d === STORE["/bookings/bk-future/pms"].arrive);
let prec = STORE["/previnvites/bk-future"];
ck("the send is recorded against the booking, not a villa-night",
   !!prec && prec.status === "sent" && prec.to === "+61411222333" &&
   prec.token === preTok && prec.by === "waiter@nala.x");

install();
r = await pre({ bookings: ["bk-past", "bk-future", "bk-none"] });
j = await r.json();
ck("a past booking is refused by the Worker, whatever the browser claimed",
   j.results["bk-past"].status === "failed" &&
   /upcoming/.test(j.results["bk-past"].error));
ck("an unknown booking fails alone and the good one still goes",
   j.results["bk-none"].status === "failed" &&
   j.results["bk-future"].status === "sent" && SENDS.length === 1);

install();
r = await pre({ bookings: ["bk-novilla"] });
j = await r.json();
ck("a booking with no villa yet still sends, its token carrying villa 0",
   j.results["bk-novilla"].status === "sent");

install(); STATE.email = "hk@nala.x";
r = await pre();
ck("the pre-arrival send obeys the same permission as invitations",
   r.status === 403 && SENDS.length === 0);

/* ── the desk's fixed number outranks the Mews copy ─────────── */
install();
STORE["/phonefix/b9-guid"] = { phone: "+64274875277", was: "02 9999 9999" };
r = await post({ villas: ["9"] });
j = await r.json();
ck("a fixed number makes the Mews landline sendable, to the fix",
   j.results["9"].status === "sent" &&
   SENDS[0].messages[0].to === "+64274875277");
ck("and the record holds the number as sent",
   STORE["/invites/" + today + "/9"].to === "+64274875277");

install();
STORE["/phonefix/bk-future/"] = null;   /* no fix: the pms number stands */
STORE["/phonefix/bk-future"] = { phone: "+61400999888" };
r = await pre();
j = await r.json();
ck("the pre kind reads the same fix",
   j.results["bk-future"].status === "sent" &&
   SENDS[0].messages[0].to === "+61400999888");

/* ── kind "delivery": the handset receipt becomes the record's verdict ── */
const dlv = (over = {}) => worker.fetch(new Request("https://w.dev/", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ idToken: "T", kind: "delivery", ...over }) }), env);

install();
STORE["/invites/" + today + "/9"] =
  { status: "sent", providerId: "mid-9", sentAt: new Date().toISOString(), to: "+61411222333" };
STATE.receipt = { status_code: "201", status_text: "Success: Message received on handset." };
r = await dlv({ invites: [{ date: today, villa: "9" }] });
j = await r.json();
ck("a handset receipt turns sent into delivered, on the record",
   j.changed === 1 && j.results[today + "/9"] === "delivered" &&
   STORE["/invites/" + today + "/9"].delivery === "delivered");
r = await dlv({ invites: [{ date: today, villa: "9" }] });
j = await r.json();
ck("a settled verdict is answered from the record, not asked again",
   j.changed === 0 && j.results[today + "/9"] === "delivered");

install();
STORE["/previnvites/bk-future"] =
  { status: "sent", providerId: "mid-p", sentAt: new Date().toISOString(), to: "+61411222333" };
STATE.receipt = { status_code: "302", status_text: "Handset unreachable",
                  error_text: "Handset unreachable" };
r = await dlv({ pres: ["bk-future"] });
j = await r.json();
ck("a failure receipt lands as failed, in the carrier's words",
   j.results["bk-future"] === "failed" &&
   STORE["/previnvites/bk-future"].delivery === "failed" &&
   /unreachable/i.test(STORE["/previnvites/bk-future"].deliveryText));

install();
STORE["/previnvites/bk-future"] =
  { status: "sent", providerId: "mid-p", sentAt: new Date().toISOString(), to: "+61411222333" };
STATE.receipt = null;
r = await dlv({ pres: ["bk-future"] });
j = await r.json();
ck("no receipt yet is unknown, and the record is left alone",
   j.results["bk-future"] === "unknown" &&
   STORE["/previnvites/bk-future"].delivery === undefined);

install(); STATE.email = "hk@nala.x";
r = await dlv({ pres: ["bk-future"] });
ck("the delivery check obeys the same permission as sending", r.status === 403);

/* ── kind "spa": the morning spa reminder, per treatment ─────────
   The words first, against the one table the page's copy answers to as
   well (tests/spar_suite.py): the preview the desk reads must be the text
   the guest gets. */
{
  const T = JSON.parse(readFileSync(new URL("../tests/spareminder_cases.json", import.meta.url), "utf8"));
  const wrong = T.text.filter((c) => workerSpaText(c.tpl, c.first, c.rec, c.prev) !== c.want);
  ck("the Worker's reminder text says what the shared table says, every case (" +
     T.text.length + ")", T.text.length > 10 && !wrong.length);
  if (wrong.length) console.log("   differs:", wrong.map((c) => c.name));
  ck("and it fences sends at the table's horizon, as far as the page looks (" +
     T.horizon + " days)", T.horizon === 7 && SPA_AHEAD_DAYS === T.horizon);
}

const REMIND = "Hello <first>, a gentle reminder of your booking with us:\n\n<booking>\n\n" +
               "If you need to change anything, just reply to this message. Nala Resort";
const spaDay = (days) => { const d = new Date(Date.now() + days * 86400000);
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") +
         "-" + String(d.getDate()).padStart(2, "0"); };
function spaWorld() {
  install();
  STORE["/spa/bk-spa/t1"] = { status: "booked", day: today, time: "14:00", dur: 60, qty: 1,
                              name: "Freya Lindqvist" };
  STORE["/spa/bk-spa/t2"] = { status: "suggested", day: today, time: "15:00", dur: 60, qty: 1 };
  STORE["/spa/bk-spa/t3"] = { status: "booked", day: spaDay(5), time: "10:00", dur: 60, qty: 1 };
  STORE["/spa/bk-spa/t4"] = { status: "booked", day: spaDay(10), time: "10:00", dur: 60, qty: 1 };
  STORE["/spa/bk-spa/t5"] = { status: "booked", day: spaDay(-2), time: "10:00", dur: 60, qty: 1 };
  STORE["/bookings/bk-spa/pms"] = { first: "Freya", last: "Lindqvist", phone: "0411 222 333",
                                    villa: 17, arrive: spaDay(-1), depart: spaDay(3) };
  STORE["/spa/bk-land/t1"] = { status: "booked", day: today, time: "12:30", dur: 60, qty: 1 };
  STORE["/bookings/bk-land/pms"] = { first: "Ruby", phone: "07 3358 1122" };
}
const spa = (over = {}) => worker.fetch(new Request("https://w.dev/", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ idToken: "T", kind: "spa", treatments: [{ b: "bk-spa", t: "t1" }],
                         template: "remind", body: REMIND, ...over }) }), env);

spaWorld(); STORE["/menu"] = null;
r = await spa();
j = await r.json();
ck("a spa reminder needs no menu, and sends", r.status === 200 &&
   j.results["bk-spa/t1"].status === "sent" && SENDS.length === 1);
const spaBody = SENDS[0].messages[0].body;
ck("its words are built here, from the /spa record and Mews' first name",
   spaBody === workerSpaText(REMIND, "Freya", STORE["/spa/bk-spa/t1"], null) &&
   spaBody.includes("Hello Freya,") && spaBody.includes("Massage, 1 hour\n") &&
   /at 2:00 pm/.test(spaBody));
ck("and it carries no link, and mints no token",
   !/https?:|menu\.nalaresort/.test(spaBody) &&
   !Object.keys(STORE).some((k) => k.startsWith("/links/")));
ck("the number came off Mews' record, normalised", SENDS[0].messages[0].to === "+61411222333");
let srec = STORE["/spareminders/bk-spa/t1"];
ck("the send is recorded against the treatment, with who pressed send",
   !!srec && srec.status === "sent" && srec.by === "waiter@nala.x" &&
   srec.providerId === "mid-1" && srec.body === spaBody && srec.to === "+61411222333");
ck("and the record keeps what the text quoted, to catch a move",
   srec.day === today && srec.time === "14:00" && srec.qty === 1 && srec.dur === 60 &&
   srec.dur2 === undefined);

spaWorld();
STORE["/spareminders/bk-spa/t1"] = { status: "sent", day: today, time: "11:30", qty: 1, dur: 60,
                                     sentAt: new Date().toISOString(), providerId: "mid-0" };
r = await spa();
ck("a booking moved since its text says what it changed from",
   /\nMassage, 1 hour\n.* at 2:00 pm\n\(changed from 11:30 am\)\n/.test(SENDS[0].messages[0].body));
ck("and the new record quotes the booking as it now stands",
   STORE["/spareminders/bk-spa/t1"].time === "14:00");

spaWorld();
STORE["/spareminders/bk-spa/t1"] = { status: "sent", day: today, time: "11:30", qty: 1, dur: 60,
                                     delivery: "failed", deliveryText: "Handset unreachable" };
r = await spa();
ck("a text the guest never got is not corrected, only sent",
   !SENDS[0].messages[0].body.includes("changed"));

spaWorld();
r = await spa({ treatments: [{ b: "bk-spa", t: "t2" }, { b: "bk-spa", t: "t4" },
                             { b: "bk-spa", t: "t5" }, { b: "bk-spa", t: "t9" },
                             { b: "bk-spa", t: "t1" }] });
j = await r.json();
ck("a suggestion is not a booking: refused by the Worker",
   j.results["bk-spa/t2"].status === "failed" && /booked/.test(j.results["bk-spa/t2"].error));
ck("a treatment ten days out is refused: the page looks 7 days at most",
   j.results["bk-spa/t4"].status === "failed" && /next 7 days/.test(j.results["bk-spa/t4"].error));
ck("and so is one already past",
   j.results["bk-spa/t5"].status === "failed" && /next 7 days/.test(j.results["bk-spa/t5"].error));
ck("a treatment that does not exist fails alone",
   j.results["bk-spa/t9"].status === "failed");
ck("and the good one still went, alone", j.results["bk-spa/t1"].status === "sent" &&
   SENDS.length === 1);

/* The owner, 28 Sep: a knob of today, 3 and 7 days, so a text can go
   early. One five days out sends, saying its day in full. */
spaWorld();
r = await spa({ treatments: [{ b: "bk-spa", t: "t3" }] });
j = await r.json();
ck("a treatment five days out sends: a reminder can go early",
   j.results["bk-spa/t3"].status === "sent" && SENDS.length === 1 &&
   SENDS[0].messages[0].body.includes(workerSpaText("<booking>", "", STORE["/spa/bk-spa/t3"], null)) &&
   STORE["/spareminders/bk-spa/t3"].day === spaDay(5));

spaWorld();
r = await spa({ treatments: [{ b: "bk-land", t: "t1" }] });
j = await r.json();
ck("a landline is refused, with the number in the reason",
   j.results["bk-land/t1"].status === "failed" && /07 3358 1122/.test(j.results["bk-land/t1"].error) &&
   SENDS.length === 0);
spaWorld();
STORE["/phonefix/bk-land"] = { phone: "+64274875277" };
r = await spa({ treatments: [{ b: "bk-land", t: "t1" }] });
ck("and the desk's fixed number outranks it", SENDS.length === 1 &&
   SENDS[0].messages[0].to === "+64274875277");

spaWorld();
r = await spa({ body: "A reminder. Nala Resort\n<menu>" });
ck("a link marker in a spa reminder is refused whole", r.status === 400 && SENDS.length === 0);
spaWorld();
r = await spa({ body: "Hello <first>, see you soon. Nala Resort" });
ck("a spa reminder without <booking> is refused: it would say nothing", r.status === 400 &&
   SENDS.length === 0);
spaWorld();
r = await spa({ body: "Hello <first>, <booking> www.evil.example" });
ck("a URL is refused here as everywhere", r.status === 400 && SENDS.length === 0);
spaWorld();
r = await spa({ treatments: [{ b: "../x", t: "t1" }] });
ck("a malformed treatment list is refused", r.status === 400);
spaWorld(); STATE.email = "hk@nala.x";
r = await spa();
ck("a spa reminder obeys the same permission as every send", r.status === 403 &&
   SENDS.length === 0);
spaWorld(); STATE.recordOk = false;
r = await spa();
j = await r.json();
ck("a reminder whose record failed says so", j.results["bk-spa/t1"].status === "sent-unrecorded");

spaWorld();
STORE["/spareminders/bk-spa/t1"] = { status: "sent", providerId: "mid-s", day: today,
                                     time: "14:00", qty: 1, dur: 60 };
STATE.receipt = { status_code: "201", status_text: "Success: Message received on handset." };
r = await dlv({ spas: [{ b: "bk-spa", t: "t1" }, { b: "../x", t: "t1" }] });
j = await r.json();
ck("the handset receipt lands on the spa reminder's record too",
   j.results["bk-spa/t1"] === "delivered" &&
   STORE["/spareminders/bk-spa/t1"].delivery === "delivered" && j.changed === 1);

/* ── kind "ext": a guest from outside the resort ────────────────
   No booking id and no villa: the Worker creates the booking, the link that
   opens it, and sends - or, if the text does not go, takes both back out. */
const EXT_BODY = "Hi Sarah, thanks for your call. Tonight’s menu is below - tap to accept or decline your table for 2. Nala Resort\n<menu>";
const ext = (over = {}) => worker.fetch(new Request("https://w.dev/", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ idToken: "T", kind: "ext", date: today, template: "ext",
                         name: "Sarah Jones", phone: "0412 345 678", pax: 2,
                         body: EXT_BODY, ...over }) }), env);
const keysUnder = (p) => Object.keys(STORE).filter((k) => k.startsWith(p));

install();
r = await ext();
j = await r.json();
const xk = j.key, xt = xk.slice(4);
ck("an external invitation sends and names the booking it made",
   r.status === 200 && j.result.status === "sent" && /^ext-[a-z2-9]{6}$/.test(xk));
ck("to the number reception typed, normalised to E.164",
   SENDS.length === 1 && SENDS[0].messages[0].to === "+61412345678" &&
   SENDS[0].messages[0].from === "+61400000000");
const xBody = SENDS[0].messages[0].body;
ck("carrying the short link, in place of the marker, once",
   xBody.endsWith("\nhttps://menu.nalaresort.com/?t=" + xt) && !xBody.includes("<menu>") &&
   (xBody.match(/menu\.nalaresort\.com/g) || []).length === 1);
ck("the link opens the booking, not a villa: {x, d}, no booking id",
   STORE["/links/" + xt] && STORE["/links/" + xt].x === xk &&
   STORE["/links/" + xt].d === today && STORE["/links/" + xt].b === undefined);
const xb = STORE["/manual/" + today + "/" + xk];
ck("the booking is the External reservation, Awaiting, keyed by the token",
   !!xb && xb.status === "awaiting" && xb.source === "invite" && xb.token === xt &&
   xb.name === "Sarah Jones" && xb.pax === 2 && xb.phone === "+61412345678" &&
   typeof xb.invitedAt === "string");
ck("and it carries no by: nobody has answered yet, so the link may",
   xb.by === undefined);
const xr = STORE["/extinvites/" + today + "/" + xk];
ck("the send is recorded in its own node, with what went and who sent it",
   !!xr && xr.status === "sent" && xr.body === xBody && xr.to === "+61412345678" &&
   xr.by === "waiter@nala.x" && xr.providerId === "mid-1" && xr.token === xt);
ck("and nothing lands among the villas' invitations",
   keysUnder("/invites/").length === 0);

install(); STATE.clicksendOk = false;
r = await ext();
j = await r.json();
ck("a text that does not go fails, in ClickSend's words",
   j.result.status === "failed" && /INVALID_RECIPIENT/.test(j.result.error));
ck("and takes back the booking and the link it made: nothing is Awaiting",
   j.key === "" && keysUnder("/manual/").length === 0 && keysUnder("/links/").length === 0);
ck("the attempt is still on record, for the question what did we try",
   keysUnder("/extinvites/").length === 1 &&
   STORE[keysUnder("/extinvites/")[0]].status === "failed");

install(); STATE.manualOk = false;
r = await ext();
j = await r.json();
ck("a booking the database refuses sends nothing (the rules not pasted)",
   j.result.status === "failed" && /booking did not store/.test(j.result.error) &&
   SENDS.length === 0);
ck("and its link is taken back out", keysUnder("/links/").length === 0);

install(); STATE.linksOk = false;
r = await ext();
j = await r.json();
ck("a link the database refuses sends nothing and books nothing",
   j.result.status === "failed" && SENDS.length === 0 &&
   keysUnder("/manual/").length === 0);

install();
r = await ext({ time: "19:00" });
j = await r.json();
ck("the seating agreed on the phone is stored as every booking's time is",
   j.result.status === "sent" && STORE["/manual/" + today + "/" + j.key].time === "19:00");
install();
r = await ext({ time: "7pm" });
ck("a time that is not one is refused before anything is written",
   r.status === 400 && SENDS.length === 0 && keysUnder("/manual/").length === 0);
install();
r = await ext();
j = await r.json();
ck("and no time chosen stores no time", !("time" in STORE["/manual/" + today + "/" + j.key]));

install();
r = await ext({ phone: "07 3358 1122" });
ck("a landline is refused before anything is written",
   r.status === 400 && SENDS.length === 0 && Object.keys(STORE).every((k) => !k.startsWith("/links/")));
r = await ext({ name: "  " });
ck("a guest with no name is refused", r.status === 400);
r = await ext({ pax: 0 });
ck("so is a table for nobody", r.status === 400);
r = await ext({ body: "Book at www.elsewhere.example" });
ck("and a message carrying a URL", r.status === 400);
r = await ext({ date: "2020-01-01" });
ck("and a night that is not tonight", r.status === 400);
ck("none of which reached ClickSend", SENDS.length === 0);

install(); STORE["/menu"] = null;
r = await ext();
ck("no menu, no invitation: the text promises tonight's menu", r.status === 409);

install(); STATE.email = "hk@nala.x";
r = await ext();
ck("the same permission as every invitation", r.status === 403 && SENDS.length === 0);

/* send again, to one invited tonight */
install();
STORE["/manual/" + today + "/ext-abc234"] = { status: "in", by: "guest", at: "x",
  name: "Tom Becker", phone: "0400 111 222", pax: 4, source: "invite",
  token: "abc234", invitedAt: "x" };
STORE["/links/abc234"] = { x: "ext-abc234", d: today, at: "x" };
r = await ext({ key: "ext-abc234", name: undefined, phone: undefined, pax: undefined });
j = await r.json();
ck("send again goes to the number on the booking now, by the same link",
   j.result.status === "sent" && SENDS[0].messages[0].to === "+61400111222" &&
   SENDS[0].messages[0].body.endsWith("?t=abc234"));
ck("and leaves the booking exactly as it stands, answer included",
   STORE["/manual/" + today + "/ext-abc234"].status === "in" &&
   STORE["/manual/" + today + "/ext-abc234"].by === "guest");
ck("the record is the latest send", STORE["/extinvites/" + today + "/ext-abc234"].status === "sent");

install(); STATE.clicksendOk = false;
STORE["/manual/" + today + "/ext-abc234"] = { status: "awaiting", name: "Tom Becker",
  phone: "0400 111 222", pax: 4, source: "invite", token: "abc234", invitedAt: "x" };
STORE["/links/abc234"] = { x: "ext-abc234", d: today, at: "x" };
r = await ext({ key: "ext-abc234" });
j = await r.json();
ck("a failed send again leaves the booking standing, and says so on the record",
   j.result.status === "failed" && j.key === "ext-abc234" &&
   !!STORE["/manual/" + today + "/ext-abc234"] &&
   STORE["/extinvites/" + today + "/ext-abc234"].status === "failed");

install();
STORE["/manual/" + today + "/ext-1727000000000"] = { status: "in", name: "Cane",
  phone: "0400 000 000", pax: 2, source: "manual" };
r = await ext({ key: "ext-1727000000000" });
j = await r.json();
ck("a booking reception typed in is not an invitation to send again",
   j.result.status === "failed" && /no such invitation/.test(j.result.error) &&
   SENDS.length === 0);
install();
STORE["/manual/" + today + "/ext-zzz999"] = { status: "in", name: "Cane",
  phone: "0400 000 000", pax: 2, source: "manual" };
r = await ext({ key: "ext-zzz999" });
j = await r.json();
ck("nor one keyed like an invitation but made by hand",
   j.result.status === "failed" && /no such invitation/.test(j.result.error) &&
   SENDS.length === 0);

/* the handset receipt reaches an external guest's record too */
install();
STORE["/extinvites/" + today + "/ext-abc234"] =
  { status: "sent", providerId: "mid-x", sentAt: new Date().toISOString(), to: "+61400111222" };
STATE.receipt = { status_code: "302", status_text: "Number not in service" };
r = await dlv({ exts: [{ date: today, key: "ext-abc234" }, { date: today, key: "../evil" }] });
j = await r.json();
ck("a failed receipt lands on the external record, in the carrier's words",
   j.results[today + "/ext-abc234"] === "failed" &&
   STORE["/extinvites/" + today + "/ext-abc234"].delivery === "failed" &&
   /not in service/.test(STORE["/extinvites/" + today + "/ext-abc234"].deliveryText));
ck("and a key in the wrong shape is never looked up",
   Object.keys(j.results).length === 1);

/* ── SMS_VIA=twilio: the everyday texts move to Twilio ─────────────
   The switch-over's last step (GUEST-CONTACT.md). Every kind sends through
   Twilio from the number Guest Contact answers on; nothing reaches
   ClickSend; a receipt is asked of whichever service sent the text, so the
   ones sent before the switch keep resolving. */
const TW = { SMS_VIA: " Twilio ", TWILIO_ACCOUNT_SID: "AC123", TWILIO_AUTH_TOKEN: "tok",
             TWILIO_FROM: "+61480000000" };
Object.assign(env, TW);
install();
r = await post(); j = await r.json();
ck("switched, tonight's menu goes through Twilio, from Guest Contact's number",
   j.results["4"].status === "sent" && SENDS.length === 0 && TSENDS.length === 1 &&
   TSENDS[0].form.From === "+61480000000" && TSENDS[0].form.To === "+61411222333" &&
   TSENDS[0].auth === "Basic " + btoa("AC123:tok"));
ck("with the words and the link the Worker built, and Twilio's id on the record",
   /menu\.nalaresort\.com\/\?t=[a-z2-9]{6}$/.test(TSENDS[0].form.Body) &&
   /^SM0{31}1$/.test(STORE["/invites/" + today + "/4"].providerId));
install(); r = await pre(); j = await r.json();
ck("and so does the pre-arrival form",
   j.results["bk-future"].status === "sent" && SENDS.length === 0 && TSENDS.length === 1 &&
   TSENDS[0].form.Body.includes("prearrival.html?t="));
spaWorld(); r = await spa(); j = await r.json();
ck("and a spa reminder", j.results["bk-spa/t1"].status === "sent" &&
   SENDS.length === 0 && TSENDS.length === 1 && TSENDS[0].form.Body.includes("Hello Freya,"));
install(); r = await ext(); j = await r.json();
ck("and an external guest's invitation, whose booking stands",
   j.result.status === "sent" && SENDS.length === 0 && TSENDS.length === 1 &&
   TSENDS[0].form.To === "+61412345678" && keysUnder("/manual/").length === 1);
install(); STATE.twilioOk = false;
r = await post(); j = await r.json();
ck("Twilio refusing is a failed send, in Twilio's words",
   j.results["4"].status === "failed" && /not a valid phone number/.test(j.results["4"].error) &&
   STORE["/invites/" + today + "/4"].status === "failed");
install(); STATE.twilioOk = false; r = await ext(); j = await r.json();
ck("and an external guest's first send that fails takes its booking back out, as before",
   j.result.status === "failed" && j.key === "" && keysUnder("/manual/").length === 0);

/* receipts, per record, by the id's own shape */
const TSID = "SM" + "a".repeat(32);
function sentRec(id) { return { status: "sent", providerId: id,
                                 sentAt: new Date().toISOString(), to: "+61411222333" }; }
install();
STORE["/previnvites/bk-a"] = sentRec(TSID);
STATE.twilioMsg = { sid: TSID, status: "delivered" };
r = await dlv({ pres: ["bk-a"] }); j = await r.json();
ck("a Twilio text's receipt is asked of Twilio, and delivered lands",
   j.results["bk-a"] === "delivered" && STORE["/previnvites/bk-a"].delivery === "delivered");
install();
STORE["/previnvites/bk-a"] = sentRec(TSID);
STATE.twilioMsg = { sid: TSID, status: "undelivered", error_code: 30005,
                    error_message: "Unknown destination handset" };
r = await dlv({ pres: ["bk-a"] }); j = await r.json();
ck("an undelivered one lands as failed, in the carrier's words",
   j.results["bk-a"] === "failed" &&
   STORE["/previnvites/bk-a"].deliveryText === "Unknown destination handset");
install();
STORE["/previnvites/bk-a"] = sentRec(TSID);
STATE.twilioMsg = { sid: TSID, status: "sent" };
r = await dlv({ pres: ["bk-a"] }); j = await r.json();
ck("and one only handed to the carrier is not known yet, and nothing is written",
   j.results["bk-a"] === "unknown" && !STORE["/previnvites/bk-a"].delivery);
install();
STORE["/previnvites/bk-c"] = sentRec("mid-1");
STATE.receipt = { status_code: "201", status_text: "Delivered" };
r = await dlv({ pres: ["bk-c"] }); j = await r.json();
ck("a text ClickSend sent before the switch is still asked of ClickSend",
   j.results["bk-c"] === "delivered" && STORE["/previnvites/bk-c"].delivery === "delivered");

for (const k of Object.keys(TW)) delete env[k];
install(); r = await post();
ck("and with SMS_VIA gone, the texts are ClickSend's again",
   SENDS.length === 1 && TSENDS.length === 0);

/* ── a text sent again keeps the one it replaced (30 Sep) ─────────
   The owner: Guest Contact must hold "every outgoing and incoming message
   including dinner invitations and pre-arrival form". Each page's record
   is its latest send; the one it replaced rides along under earlier. */
install(); STORE["/menu"] = null;
await pre();
const first = STORE["/previnvites/bk-future"];
await pre({ template: "nudge", body: "A reminder, when you have a moment. Nala Resort\n<form>" });
prec = STORE["/previnvites/bk-future"];
ck("the pre-arrival nudge is the record, and the first text rides under earlier",
   prec.template === "nudge" && prec.earlier && prec.earlier.length === 1 &&
   prec.earlier[0].sentAt === first.sentAt && prec.earlier[0].body === first.body &&
   prec.earlier[0].status === "sent" && !("token" in prec.earlier[0]));
install(); STORE["/menu"] = null; STATE.oldRules = true;
await pre();
r = await pre({ template: "nudge", body: "A reminder, when you have a moment. Nala Resort\n<form>" });
j = await r.json();
prec = STORE["/previnvites/bk-future"];
ck("before the rules know earlier, a text sent again is recorded as it always was, not refused",
   j.results["bk-future"].status === "sent" && prec.template === "nudge" && !("earlier" in prec));
install();
await post(); await post(); await post();
rec = STORE["/invites/" + today + "/4"];
ck("a dinner invitation sent three times: the last, and the two before it, newest first",
   rec.earlier && rec.earlier.length === 2 && rec.earlier[0].sentAt >= rec.earlier[1].sentAt &&
   rec.earlier.every((x) => x.status === "sent" && x.to === "+61411222333"));
STATE.clicksendOk = false;
await post();
rec = STORE["/invites/" + today + "/4"];
ck("an attempt that failed is the record, and the texts that went are all kept",
   rec.status === "failed" && rec.earlier.length === 3);
await post();
ck("and a failed attempt is never kept itself: it was not a message",
   STORE["/invites/" + today + "/4"].earlier.length === 3);
STATE.clicksendOk = true;
for (let n = 0; n < 4; n++) await post();
ck("five at most", STORE["/invites/" + today + "/4"].earlier.length === 5);
install();
await post();
STORE["/invites/" + today + "/4"].earlier = [{ sentAt: "2026-09-29T08:00:00.000Z", status: "sent", body: "x" }];
STATE.receipt = { status_code: "201", status_text: "Success: Message received on handset." };
await dlv({ invites: [{ date: today, villa: "4" }] });
ck("the receipt check writes its verdict and keeps what was sent before",
   STORE["/invites/" + today + "/4"].delivery === "delivered" &&
   (STORE["/invites/" + today + "/4"].earlier || []).length === 1);

console.log("RESULT: " + P + " passed, " + F + " failed");
process.exit(F ? 1 : 0);
