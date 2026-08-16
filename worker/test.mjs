/* Worker suite. Run: node worker/test.mjs
 *
 * Firebase is stubbed, exactly as the five browser suites stub it, so this
 * checks the logic and says nothing about the real service. The same warning
 * in HANDOVER.md applies: green here is not proof it works against Mews.
 */
import worker from "./mews-sync.js";

let P = 0, F = 0;
const ck = (name, ok) => { ok ? P++ : F++; console.log((ok ? "PASS " : "FAIL ") + name); };

const env = { SYNC_EMAIL: "x@staff.nala", SYNC_PASSWORD: "000000",
              ZAP_SECRET: "shh", FB_API_KEY: "k" };

/* A tiny in-memory database, plus a log of every call, so a test can assert
   on what was written AND on what was not. */
let STORE, CALLS, SIGNINS, FAIL_DB;

function install() {
  STORE = {}; CALLS = []; SIGNINS = 0; FAIL_DB = false;
  globalThis.fetch = async (url, opt = {}) => {
    if (String(url).includes("identitytoolkit")) {
      SIGNINS++;
      return new Response(JSON.stringify({ idToken: "T" }), { status: 200 });
    }
    if (FAIL_DB) return new Response("boom", { status: 500 });
    const path = String(url).split("firebasedatabase.app")[1].split(".json")[0];
    const m = opt.method || "GET";
    CALLS.push(m + " " + path);
    if (m === "GET") {
      /* Firebase returns a whole subtree, not just exact keys. The flat mock
         has to synthesise that or a read of /stays/<date> comes back empty and
         the clear-by-inspection pass looks broken when it is not. */
      if (STORE[path] !== undefined) {
        return new Response(JSON.stringify(STORE[path]), { status: 200 });
      }
      var kids = null;
      for (var key in STORE) {
        if (key.indexOf(path + "/") !== 0) continue;
        var rest = key.slice(path.length + 1);
        if (rest.indexOf("/") > -1) continue;   // one level only, enough here
        kids = kids || {};
        kids[rest] = STORE[key];
      }
      return new Response(JSON.stringify(kids), { status: 200 });
    }
    if (m === "DELETE") { delete STORE[path]; return new Response(null, { status: 204 }); }
    const body = JSON.parse(opt.body);
    STORE[path] = m === "PATCH" ? Object.assign({}, STORE[path] || {}, body) : body;
    return new Response(JSON.stringify(body), { status: 200 });
  };
}

const post = (body, secret = "shh") => worker.fetch(new Request(
  "https://w.dev/?secret=" + secret,
  { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body) }), env);

const RES = { Id: "res-guid-1", FirstName: "Mark", LastName: "Whitfield",
              Phone: "+61400000000", StartUtc: "2026-09-10T04:00:00Z",
              EndUtc: "2026-09-13T02:00:00Z", ResourceName: "3", State: "Confirmed" };

/* ── the secret ─────────────────────────────────────────────── */
install();
const refused = await post(RES, "nope");
ck("a wrong secret is refused", refused.status === 401);
const why = await refused.json();
ck("the refusal says the secret was configured, not missing", why.configured === true);
ck("and reports lengths without revealing the secret",
   why.configuredLength === 3 && why.receivedLength === 4 &&
   !JSON.stringify(why).includes("shh"));

ck("and nothing was written", Object.keys(STORE).length === 0);
ck("a right secret is accepted", (await post(RES)).status === 200);
/* A trailing newline on either side is invisible in a dashboard and is the
   most common reason two identical looking secrets compare unequal. */
install();
const nl = await worker.fetch(new Request("https://w.dev/?secret=" + encodeURIComponent("shh\n"),
  { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(RES) }), { ...env, ZAP_SECRET: "shh\n" });
ck("a trailing newline on both sides still matches", nl.status === 200);

install();
ck("GET is refused, this is a webhook",
   (await worker.fetch(new Request("https://w.dev/?secret=shh"), env)).status === 405);

install();
ck("a payload with no reservation id is refused",
   (await post({ FirstName: "Nobody" })).status === 400);

/* ── a new booking ──────────────────────────────────────────── */
install();
await post(RES);
const pms = STORE["/bookings/res-guid-1/pms"];
ck("the booking is stored under the Mews id", !!pms);
ck("dates are stored as dkey does, not as ISO timestamps",
   pms.arrive === "2026-09-10" && pms.depart === "2026-09-13");
ck("villa is a string even when Mews sends a bare number", pms.villa === "3");
ck("the raw Mews state is kept alongside ours",
   pms.state === "confirmed" && pms.mewsState === "confirmed");

/* Arrival inclusive, departure exclusive: a guest leaving on the 13th does
   not occupy the villa on the night of the 13th. Including it would collide
   with the next arrival on every single turnover. */
ck("three nights indexed, departure night excluded",
   !!STORE["/stays/2026-09-10/3"] && !!STORE["/stays/2026-09-11/3"] &&
   !!STORE["/stays/2026-09-12/3"] && STORE["/stays/2026-09-13/3"] === undefined);
/* A board reads one date and must get the guest without a second request. */
ck("each night carries the guest, not just a pointer",
   STORE["/stays/2026-09-10/3"].first === "Mark" &&
   STORE["/stays/2026-09-10/3"].last === "Whitfield" &&
   STORE["/stays/2026-09-10/3"].depart === "2026-09-13" &&
   STORE["/stays/2026-09-10/3"].id === "res-guid-1");

/* ── the field names the Zap actually sends ─────────────────── */
/* Mapped by hand in Zapier, so the spellings are whatever was typed that day.
   UpdateUtc without the d is the one in the live Zap. */
install();
await post({ Id: "res-2", "Companions 0 First Name": "x",
             UpdateUtc: "2026-08-01T10:00:00Z", StartUtc: "2026-09-10T04:00:00Z",
             EndUtc: "2026-09-12T02:00:00Z", SpaceName: "11", State: "Confirmed",
             BookingId: 169, GroupId: "grp-1", AdultCount: 2,
             NotesText: "Package includes flights", NotesType: "General",
             SpaceState: "Dirty" });
const kept = STORE["/bookings/res-2/pms"];
ck("UpdateUtc without the d still arms the late event guard",
   kept.updated === "2026-08-01T10:00:00Z");
ck("SpaceName is accepted as the villa, which is what Mews calls it",
   kept.villa === "11");
ck("the extra Mews fields are kept rather than dropped",
   kept.bookingNumber === 169 && kept.groupId === "grp-1" && kept.adults === 2);
/* The notes fields are reception's free text about the guest, and /bookings/<id>
   is readable by anyone holding the id so the guest can open a pre-arrival link
   without signing in. Null rather than absent, so a booking synced before this
   change loses them on its next event instead of keeping them forever. */
ck("reception's notes never reach the world readable node",
   kept.notes === null && kept.notesType === null &&
   kept.guestNotes === null && kept.spaceState === null);

/* ── the same event twice ───────────────────────────────────── */
/* syncedAt is expected to move: it records when we last heard, which is a
   different fact from when the booking last changed. What must not move is
   the guest data and the index, because Zapier retries on any 500. */
const strip = () => JSON.stringify(STORE, (k, v) => k === "syncedAt" ? undefined : v);
install();
await post(RES); const first = strip();
await post(RES);
ck("replaying an event changes nothing, so Zapier may safely retry",
   strip() === first);

/* The sign in costs a round trip on every event if it is not cached. The
   token is cleared on failure, so a failure is how a fresh one is forced. */
install();
FAIL_DB = true; await post(RES);          // clears the cached token
FAIL_DB = false; SIGNINS = 0;
await post(RES); await post(RES);
ck("one sign in serves many events, rather than one each", SIGNINS === 1);

/* ── a villa move ───────────────────────────────────────────── */
install();
await post(RES);
await post(Object.assign({}, RES, { ResourceName: "9" }));
ck("a moved guest is indexed under the new villa",
   STORE["/stays/2026-09-10/9"].id === "res-guid-1");
ck("and is GONE from the old one, not left in both",
   STORE["/stays/2026-09-10/3"] === undefined &&
   STORE["/stays/2026-09-11/3"] === undefined &&
   STORE["/stays/2026-09-12/3"] === undefined);
ck("the record itself is still one record", !!STORE["/bookings/res-guid-1/pms"]);

/* ── damage done before the fix existed ─────────────────────── */
/* Exactly what happened on 16 Aug: one booking left in three villas at once,
   because the old clearing trusted a remembered villa and cleared only that.
   The fix must remove entries it never wrote and has no memory of. */
install();
STORE["/stays/2026-09-10/13"] = { id: "res-guid-1", first: "Ben", last: "Davidson" };
STORE["/stays/2026-09-10/14"] = { id: "res-guid-1", first: "Ben", last: "Davidson" };
STORE["/stays/2026-09-11/13"] = "res-guid-1";              // and in the older shape
await post(Object.assign({}, RES, { ResourceName: "15" }));
ck("a booking stranded across several villas is cleared from all of them",
   STORE["/stays/2026-09-10/13"] === undefined &&
   STORE["/stays/2026-09-10/14"] === undefined &&
   STORE["/stays/2026-09-11/13"] === undefined);
ck("and ends up in the one villa Mews says it is in",
   STORE["/stays/2026-09-10/15"].id === "res-guid-1" &&
   STORE["/stays/2026-09-11/15"].id === "res-guid-1");

/* Another booking in the same villa must survive: the sweep removes entries
   claiming to be THIS reservation, not everything it finds. */
install();
STORE["/stays/2026-09-10/3"] = { id: "someone-else", first: "Not", last: "Ours" };
await post(Object.assign({}, RES, { ResourceName: "9" }));
ck("another guest's night in that villa is left alone",
   STORE["/stays/2026-09-10/3"].id === "someone-else");

/* ── a shortened stay ───────────────────────────────────────── */
install();
await post(RES);
await post(Object.assign({}, RES, { EndUtc: "2026-09-12T02:00:00Z" }));
ck("a shortened stay drops the night it no longer covers",
   STORE["/stays/2026-09-12/3"] === undefined);
ck("and keeps the nights it still does",
   !!STORE["/stays/2026-09-10/3"] && !!STORE["/stays/2026-09-11/3"]);

/* ── an extended stay ───────────────────────────────────────── */
install();
await post(RES);
await post(Object.assign({}, RES, { EndUtc: "2026-09-15T02:00:00Z" }));
ck("an extended stay gains the new nights",
   !!STORE["/stays/2026-09-13/3"] && !!STORE["/stays/2026-09-14/3"]);

/* ── cancellation ───────────────────────────────────────────── */
install();
await post(RES);
await post(Object.assign({}, RES, { State: "Canceled" }));
ck("a cancellation clears every night, so no card prints",
   STORE["/stays/2026-09-10/3"] === undefined &&
   STORE["/stays/2026-09-11/3"] === undefined &&
   STORE["/stays/2026-09-12/3"] === undefined);
ck("American and British spellings both count as cancelled",
   STORE["/bookings/res-guid-1/pms"].state === "cancelled");
ck("but the record survives: what was asked for is worth knowing",
   STORE["/bookings/res-guid-1/pms"].first === "Mark");

/* ── late delivery ──────────────────────────────────────────── */
/* Webhooks are not ordered. A move delivered, then the pre-move event
   arriving behind it, must not put the guest back in the old villa. */
install();
await post(Object.assign({}, RES, { UpdatedUtc: "2026-08-01T10:00:00Z" }));
await post(Object.assign({}, RES, { ResourceName: "9", UpdatedUtc: "2026-08-01T11:00:00Z" }));
await post(Object.assign({}, RES, { ResourceName: "3", UpdatedUtc: "2026-08-01T10:30:00Z" }));
ck("a late event is ignored, not applied",
   STORE["/bookings/res-guid-1/pms"].villa === "9");
ck("and the index still reflects the newest event only",
   STORE["/stays/2026-09-10/9"].id === "res-guid-1" &&
   STORE["/stays/2026-09-10/3"] === undefined);

/* ── what it must never touch ───────────────────────────────── */
install();
STORE["/bookings/res-guid-1/prearrival"] = { dining: true };
STORE["/bookings/res-guid-1/dining"] = { covers: 2 };
await post(RES);
ck("the questionnaire is untouched",
   JSON.stringify(STORE["/bookings/res-guid-1/prearrival"]) === '{"dining":true}');
ck("the dining data is untouched",
   JSON.stringify(STORE["/bookings/res-guid-1/dining"]) === '{"covers":2}');
ck("it writes only under pms and stays",
   CALLS.filter(c => !c.startsWith("GET"))
        .every(c => c.includes("/pms") || c.includes("/stays/")));

/* ── failure ────────────────────────────────────────────────── */
install();
FAIL_DB = true;
const bad = await post(RES);
ck("a database failure returns 500 so Zapier retries", bad.status === 500);

/* ── a runaway range ────────────────────────────────────────── */
install();
await post(Object.assign({}, RES, { EndUtc: "2035-01-01T00:00:00Z" }));
ck("a nonsense date range is capped rather than written forever",
   CALLS.filter(c => c.startsWith("PUT")).length <= 121);

/* ── an unrecognised villa ──────────────────────────────────── */
/* Mews sends whatever the space is called and the Zap maps Space Name. A name
   the app does not know would become a /stays key no board ever reads, so the
   guest would be invisible while the sync reported success. */
install();
let odd = await post(Object.assign({}, RES, { ResourceName: "Spa Suite" }));
ck("an unknown space name writes no stay at all",
   !Object.keys(STORE).some(k => k.startsWith("/stays/")));
ck("but the booking is still recorded",
   !!STORE["/bookings/res-guid-1/pms"]);
ck("and the reply names the value it refused, so the Zap history shows it",
   (await odd.json()).unknownVilla === "Spa Suite");

install();
await post(Object.assign({}, RES, { ResourceName: "18" }));
ck("a villa number above the seventeen that exist is refused too",
   !Object.keys(STORE).some(k => k.startsWith("/stays/")));

install();
await post(Object.assign({}, RES, { ResourceName: "17" }));
ck("seventeen itself is accepted, the boundary is inclusive",
   Object.keys(STORE).some(k => k.startsWith("/stays/") && k.endsWith("/17")));

/* ── the PMS stamp on each night ────────────────────────────── */
/* The app stamps a staff "vacant" with the version of the booking it was
   decided against. Without this in the summary there is nothing to compare to,
   and the decision either sticks forever or is undone on the next poll. */
install();
await post(Object.assign({}, RES, { UpdateUtc: "2026-09-01T08:00:00Z" }));
ck("every night carries the Mews updated stamp",
   STORE["/stays/2026-09-10/3"].updated === "2026-09-01T08:00:00Z");
ck("and a booking Mews never stamped carries null rather than nothing",
   (install(), await post(RES),
    STORE["/stays/2026-09-10/3"].updated === null));

/* ── the cleared count ──────────────────────────────────────── */
/* It used to report the previous booking's night count whether or not anything
   was deleted, which overstated on a first sync and understated on a rescue. */
install();
let firstSync = await post(RES);
ck("a first sync clears nothing and says so",
   (await firstSync.json()).cleared === 0);

console.log("RESULT: %d passed, %d failed", P, F);
if (F) process.exit(1);
