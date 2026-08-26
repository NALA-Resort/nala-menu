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
      if (kids) return new Response(JSON.stringify(kids), { status: 200 });
      /* And the other direction: Firebase serves a child of a stored object,
         so a read of /internal/<id>/fromMews after a PATCH of /internal/<id>
         must find the field inside the parent. Without this the seed-once
         guard reads null forever and every event looks like a first seed. */
      var slash = path.lastIndexOf("/");
      var parent = STORE[path.slice(0, slash)], leaf = path.slice(slash + 1);
      if (parent && typeof parent === "object" && leaf in parent) {
        return new Response(JSON.stringify(parent[leaf]), { status: 200 });
      }
      return new Response("null", { status: 200 });
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

const RES = { MewsId: "ff129c05-9902-4d9f-9bfd-b4a800a91f52", FirstName: "Mark", LastName: "Whitfield",
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
const pms = STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/pms"];
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
   STORE["/stays/2026-09-10/3"].id === "ff129c05-9902-4d9f-9bfd-b4a800a91f52");

/* ── the field names the Zap actually sends ─────────────────── */
/* Mapped by hand in Zapier, so the spellings are whatever was typed that day.
   UpdateUtc without the d is the one in the live Zap. */
install();
await post({ Id: "a1b2c3d4-0000-4000-8000-000000000002", "Companions 0 First Name": "x",
             UpdateUtc: "2026-08-01T10:00:00Z", StartUtc: "2026-09-10T04:00:00Z",
             EndUtc: "2026-09-12T02:00:00Z", SpaceName: "11", State: "Confirmed",
             BookingId: 169, GroupId: "grp-1", AdultCount: 2,
             NotesText: "Package includes flights", NotesType: "General",
             SpaceState: "Dirty" });
const kept = STORE["/bookings/a1b2c3d4-0000-4000-8000-000000000002/pms"];
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
   STORE["/stays/2026-09-10/9"].id === "ff129c05-9902-4d9f-9bfd-b4a800a91f52");
ck("and is GONE from the old one, not left in both",
   STORE["/stays/2026-09-10/3"] === undefined &&
   STORE["/stays/2026-09-11/3"] === undefined &&
   STORE["/stays/2026-09-12/3"] === undefined);
ck("the record itself is still one record", !!STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/pms"]);

/* ── damage done before the fix existed ─────────────────────── */
/* Exactly what happened on 16 Aug: one booking left in three villas at once,
   because the old clearing trusted a remembered villa and cleared only that.
   The fix must remove entries it never wrote and has no memory of. */
install();
STORE["/stays/2026-09-10/13"] = { id: "ff129c05-9902-4d9f-9bfd-b4a800a91f52", first: "Ben", last: "Davidson" };
STORE["/stays/2026-09-10/14"] = { id: "ff129c05-9902-4d9f-9bfd-b4a800a91f52", first: "Ben", last: "Davidson" };
STORE["/stays/2026-09-11/13"] = "ff129c05-9902-4d9f-9bfd-b4a800a91f52";              // and in the older shape
await post(Object.assign({}, RES, { ResourceName: "15" }));
ck("a booking stranded across several villas is cleared from all of them",
   STORE["/stays/2026-09-10/13"] === undefined &&
   STORE["/stays/2026-09-10/14"] === undefined &&
   STORE["/stays/2026-09-11/13"] === undefined);
ck("and ends up in the one villa Mews says it is in",
   STORE["/stays/2026-09-10/15"].id === "ff129c05-9902-4d9f-9bfd-b4a800a91f52" &&
   STORE["/stays/2026-09-11/15"].id === "ff129c05-9902-4d9f-9bfd-b4a800a91f52");

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
   STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/pms"].state === "cancelled");
ck("but the record survives: what was asked for is worth knowing",
   STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/pms"].first === "Mark");

/* ── late delivery ──────────────────────────────────────────── */
/* Webhooks are not ordered. A move delivered, then the pre-move event
   arriving behind it, must not put the guest back in the old villa. */
install();
await post(Object.assign({}, RES, { UpdatedUtc: "2026-08-01T10:00:00Z" }));
await post(Object.assign({}, RES, { ResourceName: "9", UpdatedUtc: "2026-08-01T11:00:00Z" }));
await post(Object.assign({}, RES, { ResourceName: "3", UpdatedUtc: "2026-08-01T10:30:00Z" }));
ck("a late event is ignored, not applied",
   STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/pms"].villa === "9");
ck("and the index still reflects the newest event only",
   STORE["/stays/2026-09-10/9"].id === "ff129c05-9902-4d9f-9bfd-b4a800a91f52" &&
   STORE["/stays/2026-09-10/3"] === undefined);

/* ── what it must never touch ───────────────────────────────── */
install();
STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/prearrival"] = { dining: true };
STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/dining"] = { covers: 2 };
await post(RES);
ck("the questionnaire is untouched",
   JSON.stringify(STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/prearrival"]) === '{"dining":true}');
ck("the dining data is untouched",
   JSON.stringify(STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/dining"]) === '{"covers":2}');
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
   !!STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/pms"]);
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


/* ── one party, several villas ──────────────────────────────── */
/* A family booking two villas is two reservations under one group. Without the
   group id on the night, the boards see two unrelated guests who happen to
   share a surname. */
install();
await post(Object.assign({}, RES, { GroupId: "grp-9" }));
ck("every night carries the group id, so one party can be recognised",
   STORE["/stays/2026-09-10/3"].groupId === "grp-9");

install();
await post(RES);
ck("and a booking with no group carries null rather than nothing",
   STORE["/stays/2026-09-10/3"].groupId === null);


/* ── the id that caused three Ben Davidsons ─────────────────── */
/* Zapier's own "ID" is a per-event dedupe key: 32 hex characters, no dashes,
   different on every event. Keyed on it, every change looked like a brand new
   booking, so one guest appeared in three villas and a move never cleared the
   villa it left. Found on 17 Aug by comparing two Zap runs for one booking. */
install();
const zapKey = await post({ Id: "5f593a0c708cbb49e77f324e07bee616",
  StartUtc: "2026-09-10T04:00:00Z", EndUtc: "2026-09-13T02:00:00Z",
  ResourceName: "3", State: "Confirmed" });
ck("Zapier's own event key is refused, not stored as a booking",
   zapKey.status === 400);
ck("and the refusal says what to send instead",
   (await zapKey.json()).hint.indexOf("whichever is a GUID") > -1);
ck("nothing was written", Object.keys(STORE).length === 0);

/* Both present is the likely shape of a half-corrected mapping. */
install();
await post({ Id: "5f593a0c708cbb49e77f324e07bee616",
  MewsId: "ff129c05-9902-4d9f-9bfd-b4a800a91f52",
  StartUtc: "2026-09-10T04:00:00Z", EndUtc: "2026-09-13T02:00:00Z",
  ResourceName: "3", State: "Confirmed" });
ck("with both present the Mews id wins",
   !!STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/pms"]);

/* The same booking moving villa twice must stay ONE booking. */
install();
const RES_MOVE = { MewsId: "ff129c05-9902-4d9f-9bfd-b4a800a91f52",
  StartUtc: "2026-09-10T04:00:00Z", EndUtc: "2026-09-11T02:00:00Z",
  State: "Confirmed" };
await post(Object.assign({}, RES_MOVE, { ResourceName: "13", UpdateUtc: "2026-08-17T07:36:00Z" }));
await post(Object.assign({}, RES_MOVE, { ResourceName: "14", UpdateUtc: "2026-08-17T09:00:00Z" }));
await post(Object.assign({}, RES_MOVE, { ResourceName: "15", UpdateUtc: "2026-08-17T11:02:00Z" }));
const nights = Object.keys(STORE).filter(k => k.startsWith("/stays/"));
ck("a booking moved twice holds exactly one villa, not three",
   nights.length === 1 && nights[0].endsWith("/15"));


/* ── a cancellation for a booking we never saw ──────────────── */
/* The cancellation trigger has no MewsId field, only Id, so it works only if
   that Id is the same GUID as the reservation trigger's Mews Id. If it is a
   cancellation event id instead, every cancellation lands here clearing
   nothing, and used to reply with a cheerful ok. */
install();
const orphan = await post({ MewsId: "00000000-0000-4000-8000-00000000dead",
  State: "Canceled", StartUtc: "2026-09-10T04:00:00Z",
  EndUtc: "2026-09-11T02:00:00Z", ResourceName: "3" });
ck("a cancellation for an unknown booking says so",
   (await orphan.json()).unknownCancellation === true);

install();
await post(RES);
const known = await post(Object.assign({}, RES, { State: "Canceled" }));
ck("and a cancellation for one we know does not",
   (await known.json()).unknownCancellation === undefined);


/* ── the three triggers name the id differently ─────────────── */
/* Measured 17 Aug. No single field name is right, so the Worker takes
   whichever value is a GUID.

     New reservation  the GUID arrives as Id, and there is no MewsId
     Modification     the GUID arrives as MewsId, and Id is Zapier's own key
     Cancellation     the GUID arrives as Id                                 */
const GUID = "c0a444b2-b2d8-4e5f-90bb-b4a900c12ed8";
const BASE = { StartUtc: "2026-09-10T04:00:00Z", EndUtc: "2026-09-11T02:00:00Z",
               ResourceName: "3", State: "Confirmed" };

install();
await post(Object.assign({}, BASE, { Id: GUID }));
ck("a new reservation, where the GUID is in Id", !!STORE["/bookings/" + GUID + "/pms"]);

install();
await post(Object.assign({}, BASE, { Id: "be99712182a11b7e1c854af0ecdaf669", MewsId: GUID }));
ck("a modification, where Id is Zapier's key and the GUID is in MewsId",
   !!STORE["/bookings/" + GUID + "/pms"]);
ck("and Zapier's key is not used as a booking",
   !STORE["/bookings/be99712182a11b7e1c854af0ecdaf669/pms"]);

/* The one that mattered: a new reservation and its later modification must be
   the SAME booking, or every change looks like a new arrival. */
install();
await post(Object.assign({}, BASE, { Id: GUID, ResourceName: "13",
                                     UpdateUtc: "2026-08-17T07:36:00Z" }));
await post(Object.assign({}, BASE, { Id: "be99712182a11b7e1c854af0ecdaf669",
                                     MewsId: GUID, ResourceName: "15",
                                     UpdateUtc: "2026-08-17T11:02:00Z" }));
const held = Object.keys(STORE).filter(k => k.startsWith("/stays/"));
ck("a booking created then moved holds one villa, not two",
   held.length === 1 && held[0].endsWith("/15"));


/* ── the number a human can read ────────────────────────────── */
/* The GUID is the key, but nobody can read it out over the phone. The
   reservation number is what staff see in Mews. */
install();
await post(Object.assign({}, RES, { Number: 1159, BookingId: 900 }));
ck("the reservation number reaches every night",
   STORE["/stays/2026-09-10/3"].number === 1159);
ck("and Number wins over BookingId, which numbers the group not the booking",
   STORE["/bookings/" + RES.MewsId + "/pms"].bookingNumber === 1159);

/* ── the person behind the stay ─────────────────────────────── */
/* The reservation id names one stay. The customer id names the guest across
   all of them, and stage 6 writes a dietary back against the guest. Kept on
   the booking only: the nights are read constantly and never need it. */
install();
await post(Object.assign({}, RES, {
  CustomerId: "7c1e4a90-3b55-4a11-9d02-b4a900c12abc" }));
ck("the customer id is kept on the booking",
   STORE["/bookings/" + RES.MewsId + "/pms"].customerId ===
     "7c1e4a90-3b55-4a11-9d02-b4a900c12abc");
ck("and is not copied into every night",
   STORE["/stays/2026-09-10/3"].customerId === undefined);

install();
await post(Object.assign({}, RES, { AccountId: "3f0d1188-2c44-4e77-8a90-b4a900c12def" }));
ck("AccountId is read when CustomerId is not sent",
   STORE["/bookings/" + RES.MewsId + "/pms"].customerId ===
     "3f0d1188-2c44-4e77-8a90-b4a900c12def");

/* Zapier's own 32 character event key turns up in fields that sound like an
   identifier, and storing it here would attach every booking to a customer
   who does not exist. Shape settles it, as it does for the reservation id. */
install();
await post(Object.assign({}, RES, { CustomerId: "be99712182a11b7e1c854af0ecdaf669",
                                    AccountId:  "9a2b7c31-88d4-4e0b-9c1f-2b6d5e7a1c04" }));
ck("a Zapier key in the customer field loses to the real GUID beside it",
   STORE["/bookings/" + RES.MewsId + "/pms"].customerId ===
     "9a2b7c31-88d4-4e0b-9c1f-2b6d5e7a1c04");

install();
await post(RES);
ck("a booking with no customer id at all is still written",
   STORE["/bookings/" + RES.MewsId + "/pms"].customerId === null);

/* ── Mews notes are not imported ────────────────────────────── */
/* Ruled by the owner, 26 Aug. Zapier sends the Mews note as its own
   flattening of the note objects - GUIDs and timestamps around the words -
   and one printed sheet carried nine lines of it in a staff row. The rule
   is now simpler than any parser: whatever matters is typed at the desk on
   the day, and the Worker imports nothing. These pin the nothing. */
const DUMP = "createdUtc: 2026-07-07T06:28:44Z id: c20eda2e-4c43-4e57-b62b-b48008ac53aa " +
  "orderId: 203a773e-4fd0-4418-ad4d-b48000b8ac4f text: Hi, would prefer a view over " +
  "the beach rather than the pool, please. Many thanks, very much looking forward " +
  "to our stay :) type: General updatedUtc: 2026-07-07T06:28:44Z";

install();
await post(Object.assign({}, RES, { Notes: DUMP }));
ck("the flattened note object is written nowhere",
   !Object.keys(STORE).some(k => k.startsWith("/internal")));

install();
await post(Object.assign({}, RES, { Notes: "Owner's friend, do not charge for wine" }));
ck("and so is a clean, human one: the desk is the only writer of notes",
   !Object.keys(STORE).some(k => k.startsWith("/internal")));
ck("so a reservation event writes only under pms and stays, notes included",
   CALLS.filter(c => !c.startsWith("GET"))
        .every(c => c.includes("/pms") || c.includes("/stays/")));

/* ── the clock ──────────────────────────────────────────────── */
/* Mews sends true UTC. Confirmed 18 Aug: 04:00Z is 2pm at the resort, which is
   UTC+10. So the date part of the timestamp is the local date only until 2pm
   UTC, and anything after that belongs to the next local day. Every case here
   was filed a day early before that was fixed. */

install();
await post(Object.assign({}, RES, { StartUtc: "2026-09-10T04:00:00Z",
                                    EndUtc: "2026-09-11T00:00:00Z" }));
ck("the ordinary case is unchanged: 2pm local arrival",
   !!STORE["/stays/2026-09-10/3"] && !STORE["/stays/2026-09-11/3"]);

/* An early arrival. 22:00 UTC on the 9th is 8am on the 10th at the resort, and
   the guest is in the villa on the night of the 10th, not the 9th. */
install();
await post(Object.assign({}, RES, { StartUtc: "2026-09-09T22:00:00Z",
                                    EndUtc: "2026-09-11T00:00:00Z" }));
ck("an arrival before 10am local is not filed on the night before",
   !STORE["/stays/2026-09-09/3"] && !!STORE["/stays/2026-09-10/3"]);

/* And the far side of it. 15:00 UTC is 1am the following day at the resort. */
install();
await post(Object.assign({}, RES, { StartUtc: "2026-09-10T15:00:00Z",
                                    EndUtc: "2026-09-12T00:00:00Z" }));
ck("a late arrival is filed on the local day it lands, not the UTC one",
   !STORE["/stays/2026-09-10/3"] && !!STORE["/stays/2026-09-11/3"]);

/* Departure is exclusive, so a checkout before 10am local must not hold the
   villa for the night before it. A cleaner sent to a villa a day early is the
   visible half of this bug. */
install();
await post(Object.assign({}, RES, { StartUtc: "2026-09-10T04:00:00Z",
                                    EndUtc: "2026-09-12T23:00:00Z" }));
ck("a checkout at 9am local holds the villa for the night before it",
   !!STORE["/stays/2026-09-12/3"] && !STORE["/stays/2026-09-13/3"]);

install();
await post(Object.assign({}, RES, { StartUtc: "2026-09-10T04:00:00Z",
                                    EndUtc: "2026-09-13T02:00:00Z" }));
const tzPms = STORE["/bookings/" + RES.MewsId + "/pms"];
ck("the dates on the booking are resort dates too",
   tzPms.arrive === "2026-09-10" && tzPms.depart === "2026-09-13");

/* Midsummer, when a state that observes daylight saving would be +11 and a
   hardcoded +10 would be an hour out. Brisbane does not, so this is the case
   that has to be revisited if the zone name ever changes. */
install();
await post(Object.assign({}, RES, { StartUtc: "2027-01-15T04:00:00Z",
                                    EndUtc: "2027-01-17T00:00:00Z" }));
ck("summer is handled by the zone, not by a number in the code",
   !!STORE["/stays/2027-01-15/3"]);

/* A Zap mapped to a date field rather than a timestamp. Reinterpreting a bare
   date in a timezone would move it a day, so it is left alone. */
install();
await post(Object.assign({}, RES, { StartUtc: "2026-09-10", EndUtc: "2026-09-12" }));
ck("a date with no time is taken as written",
   !!STORE["/stays/2026-09-10/3"] && !!STORE["/stays/2026-09-11/3"] &&
   !STORE["/stays/2026-09-12/3"]);

/* ── the arriving-soon sweep ─────────────────────────────────────────────
 *
 * The clock is frozen at 13:30 resort time, half past one in the afternoon,
 * so which villas sit inside their red hour is the same whenever the suite
 * runs: 2pm arrivals are red, 4pm ones are not. */
const RealDate = Date;
const FIXED = new RealDate("2026-09-10T03:30:00Z").getTime();
globalThis.Date = class extends RealDate {
  constructor(...a) { a.length ? super(...a) : super(FIXED); }
  static now() { return FIXED; }
};
const TODAY = "2026-09-10", YESTER = "2026-09-09";

let PUSHES;
function installSweep(stays, hk, pre) {
  install();
  PUSHES = [];
  const inner = globalThis.fetch;
  globalThis.fetch = async (url, opt = {}) => {
    if (String(url).includes("nala-push")) {
      const b = JSON.parse(opt.body);
      PUSHES.push(b);
      CALLS.push("PUSH " + b.villa);
      return new Response("ok", { status: 200 });
    }
    return inner(url, opt);
  };
  STORE["/stays/" + TODAY] = stays;
  STORE["/hk/" + TODAY] = hk;
  for (const id in (pre || {})) STORE["/bookings/" + id + "/prearrival"] = pre[id];
}
async function wake() {
  const jobs = [];
  await worker.scheduled({}, env, { waitUntil: (p) => jobs.push(p) });
  await Promise.all(jobs);
}

installSweep({
  /* red: approved 2pm, 13:30 is inside the hour before it */
  "1": { id: "p1", arrive: TODAY, depart: "2026-09-12" },
  /* not yet: the guest asked for 4pm and 13:30 is 90 minutes early */
  "2": { id: "p2", arrive: TODAY, depart: "2026-09-12" },
  /* red: said nothing, and a silent arrival is a 2pm arrival */
  "3": { id: "p3", arrive: TODAY, depart: "2026-09-12" },
  /* claimed: somebody is on it, so it stays quiet */
  "4": { id: "p4", arrive: TODAY, depart: "2026-09-12" },
  /* done: quiet however early the hour was */
  "5": { id: "p5", arrive: TODAY, depart: "2026-09-12" },
  /* stay-over: arrived yesterday, not an arrival at all */
  "7": { id: "p7", arrive: YESTER, depart: "2026-09-12" },
  /* the manager said no arrival tonight, and the override wins */
  "8": { id: "p8", arrive: TODAY, depart: "2026-09-12" },
}, {
  "4": { takenBy: "Ana" },
  "5": { done: "2026-09-10T01:00:00Z" },
  "8": { arriving: false },
  /* a manual Arriving tonight tick with no booking behind it: 2pm, so red */
  "9": { arriving: true },
}, {
  "p1": { arriveApproved: 14 },
  "p2": { arriveSlot: "16" },
  "p4": { arriveApproved: 14 },
  "p5": { arriveApproved: 11 },
  "p8": { arriveApproved: 11 },
});
/* Rode along for the clear-out: villa 1 still holds a note imported before
   the owner retired the import, beside a note the desk typed; villa 3 has
   only the desk's. The same wake that sweeps arrivals retires the import. */
STORE["/internal/p1"] = { fromMews: DUMP, note: "the desk's own words" };
STORE["/internal/p3"] = { note: "typed at the desk" };
await wake();
ck("the wake clears the imported note for tonight's house",
   STORE["/internal/p1"].fromMews === null);
ck("and leaves the desk's notes alone",
   STORE["/internal/p1"].note === "the desk's own words" &&
   STORE["/internal/p3"].note === "typed at the desk");
ck("a record with nothing imported is read, not written",
   !CALLS.includes("PATCH /internal/p3"));
const buzzed = PUSHES.map((p) => p.villa).sort();
ck("the villas inside their red hour and unclaimed are announced, no others",
   buzzed.join() === "1,3,9");
ck("every announcement is the arriving event, signed in",
   PUSHES.every((p) => p.event === "arriving" && p.idToken === "T"));
ck("a silent 2pm arrival warns like a stated one", buzzed.includes("3"));
ck("the manual tick with no booking warns at 2pm like anything else",
   buzzed.includes("9"));
ck("the marker is written per villa announced",
   !!STORE["/alerts/" + TODAY + "/1"] && !!STORE["/alerts/" + TODAY + "/3"] &&
   !!STORE["/alerts/" + TODAY + "/9"] && !STORE["/alerts/" + TODAY + "/2"]);
ck("and written BEFORE the send, so a crash cannot buzz forever",
   ["1", "3", "9"].every((v) =>
     CALLS.indexOf("PUT /alerts/" + TODAY + "/" + v) > -1 &&
     CALLS.indexOf("PUT /alerts/" + TODAY + "/" + v) < CALLS.indexOf("PUSH " + v)));

/* The next wake finds the markers and sends nothing. */
PUSHES.length = 0;
await wake();
ck("a second wake announces nobody twice", PUSHES.length === 0);

/* A villa that becomes red later is picked up by a later wake, once. */
STORE["/stays/" + TODAY]["2"] = { id: "p2", arrive: TODAY, depart: "2026-09-12" };
STORE["/bookings/p2/prearrival"] = { arriveApproved: 14 };
PUSHES.length = 0;
await wake();
ck("a villa whose hour arrives later gets its one announcement then",
   PUSHES.length === 1 && PUSHES[0].villa === "2");

/* Three wakes have now crossed the same frozen day. The clear-out is once
   a day, in the manner of the token cache, not once per five-minute wake. */
ck("the clear-out ran once across every wake of the day",
   CALLS.filter(c => c === "PATCH /internal/p1").length === 1);

globalThis.Date = RealDate;

console.log("RESULT: %d passed, %d failed", P, F);
if (F) process.exit(1);
