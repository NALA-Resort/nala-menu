/* Invitations Worker suite. Run: node worker/invites-test.mjs
 *
 * Firebase and ClickSend are stubbed. Green here checks the logic and says
 * nothing about the real services: no ClickSend account exists yet, and the
 * sandbox reaches neither ClickSend nor Cloudflare. HANDOVER.md's warning
 * applies in full.
 */
import worker, { normalisePhone as workerNorm } from "./send-invites.js";
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
let STORE, SENDS, STATE;

function install() {
  STORE = {}; SENDS = [];
  STATE = { tokenOk: true, email: "waiter@nala.x", clicksendOk: true,
            recordOk: true, linksOk: true };
  STORE["/staff/waiter@nala,x"] = { role: "waiter" };
  STORE["/staff/hk@nala,x"] = { role: "housekeeping" };
  STORE["/staff/old@nala,x"] = { role: "staff" };   /* the pre-rename records */
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
    if (u.includes("clicksend.com")) {
      SENDS.push(JSON.parse(opt.body));
      if (!STATE.clicksendOk)
        return new Response(JSON.stringify({ data: { messages: [{ status: "INVALID_RECIPIENT" }] } }), { status: 200 });
      return new Response(JSON.stringify({ data: { messages: [{ status: "SUCCESS", message_id: "mid-1" }] } }), { status: 200 });
    }
    const path = u.split("firebasedatabase.app")[1].split(".json")[0];
    if ((opt.method || "GET") === "PUT") {
      /* recordOk gates the /invites record alone: the send-worked-but-the-
         record-did-not case. linksOk gates the token store, which fails a
         villa BEFORE anything is sent. */
      if (!STATE.recordOk && path.startsWith("/invites/"))
        return new Response("no", { status: 401 });
      if (!STATE.linksOk && path.startsWith("/links/"))
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
const sentBody = SENDS[0].messages[0].body;
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

console.log("RESULT: " + P + " passed, " + F + " failed");
process.exit(F ? 1 : 0);
