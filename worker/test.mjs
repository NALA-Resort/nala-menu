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
      /* And the reverse: a child of a stored object resolves too, as it
         would in Firebase, where paths address one tree rather than flat
         keys. Without this a read of /prearrival/forCustomerId after a
         PATCH to /prearrival comes back null and the Worker re-stamps a
         form the real database would have told it was already stamped. */
      const cut = path.lastIndexOf("/");
      const up = STORE[path.slice(0, cut)];
      if (up && typeof up === "object") {
        const leaf = up[path.slice(cut + 1)];
        if (leaf !== undefined)
          return new Response(JSON.stringify(leaf), { status: 200 });
      }
      return new Response(JSON.stringify(null), { status: 200 });
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

/* ── an unrecognised villa on a booking that had one ────────── */
/* The name change of 3 Sep. A modification whose villa mapping was missing
   or unrecognised fed the clear pass an empty list of nights to keep, so
   every night the booking held was deleted, none rewritten, and the reply
   was still ok - the room left every board with the only trace a field in
   a Zap history nobody reads. Refused whole now, before anything writes. */
install();
await post(RES);
const renamed = await post(Object.assign({}, RES,
  { FirstName: "Sam", ResourceName: "Spa Suite" }));
ck("a modification with an unrecognised villa is refused, not applied",
   renamed.status === 400);
ck("and the nights it would have erased are still there",
   !!STORE["/stays/2026-09-10/3"] && !!STORE["/stays/2026-09-11/3"] &&
   !!STORE["/stays/2026-09-12/3"]);
ck("and the booking still reads as it did before the bad event",
   STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/pms"].first === "Mark");
ck("the refusal names both villas so the Zap history explains itself",
   await renamed.json().then(j => j.received === "Spa Suite" && j.held === "3"));
/* A cancellation is different: it clears the nights whatever the villa
   field says, and refusing it would leave a cancelled guest on the board. */
install();
await post(RES);
const bye = await post(Object.assign({}, RES,
  { State: "Canceled", ResourceName: "Spa Suite" }));
ck("a cancellation with a bad villa still clears the nights",
   bye.status === 200 && STORE["/stays/2026-09-10/3"] === undefined);

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

/* ── Id2, the spelling the live Zap serialises ──────────────── */
/* Seen live 1 Sep, 02:01: a new reservation's first event carried its GUID
   under Id2 and nothing under Id or MewsId, so the first event of every new
   booking 400'd and the booking waited for its next modification to exist.
   Which Zap-editor choice produced that key name was never established; the
   payload is the fact. Shape still rules: a non GUID under Id2 is refused
   like anywhere else, and a real Id or MewsId outranks it when present. */
install();
const id2run = await post({ Id2: "dfcc2614-67b5-4cd4-8b58-b4b7001ac418",
  FirstName: "James", StartUtc: "2026-09-10T04:00:00Z",
  EndUtc: "2026-09-13T02:00:00Z", ResourceName: "3", State: "Confirmed" });
ck("a GUID arriving under Id2 is accepted", id2run.status === 200);
ck("and the booking is stored under that GUID",
   !!STORE["/bookings/dfcc2614-67b5-4cd4-8b58-b4b7001ac418/pms"]);

install();
await post({ MewsId: "ff129c05-9902-4d9f-9bfd-b4a800a91f52",
  Id2: "dfcc2614-67b5-4cd4-8b58-b4b7001ac418",
  StartUtc: "2026-09-10T04:00:00Z", EndUtc: "2026-09-13T02:00:00Z",
  ResourceName: "3", State: "Confirmed" });
ck("MewsId outranks Id2 when both are GUIDs",
   !!STORE["/bookings/ff129c05-9902-4d9f-9bfd-b4a800a91f52/pms"] &&
   !STORE["/bookings/dfcc2614-67b5-4cd4-8b58-b4b7001ac418/pms"]);

install();
const id2zap = await post({ Id2: "5f593a0c708cbb49e77f324e07bee616",
  StartUtc: "2026-09-10T04:00:00Z", EndUtc: "2026-09-13T02:00:00Z",
  ResourceName: "3", State: "Confirmed" });
ck("Zapier's event key under Id2 is refused like anywhere else",
   id2zap.status === 400 && Object.keys(STORE).length === 0);

/* The refusal for a payload with NO id names the keys that did arrive, so
   the Zap history shows which mapping went missing instead of a bare no. */
install();
const noid = await post({ FirstName: "Nobody", ResourceName: "3" });
ck("the no-id refusal lists the keys that were received",
   noid.status === 400 &&
   JSON.stringify((await noid.json()).receivedKeys) ===
     JSON.stringify(["FirstName", "ResourceName"]));

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
   !!STORE["/bookings/" + RES.MewsId + "/pms"] &&
   STORE["/bookings/" + RES.MewsId + "/pms"].customerId == null);

/* The triggers carry the field unevenly, exactly like the rate, and losing
   it costs more: /guests is keyed on it, so a modification with CustomerId
   unmapped used to DELETE the person from the booking and with them every
   dietary's way home. */
install();
await post(Object.assign({}, RES, {
  CustomerId: "7c1e4a90-3b55-4a11-9d02-b4a800c12abc" }));
await post(RES);
ck("an event with no customer id leaves the stored one standing",
   STORE["/bookings/" + RES.MewsId + "/pms"].customerId ===
     "7c1e4a90-3b55-4a11-9d02-b4a800c12abc");
await post(Object.assign({}, RES, { CustomerId: "be99712182a11b7e1c854af0ecdaf669" }));
ck("and a lone Zapier key does not replace a real customer either",
   STORE["/bookings/" + RES.MewsId + "/pms"].customerId ===
     "7c1e4a90-3b55-4a11-9d02-b4a800c12abc");

/* ── whose answers the form holds ───────────────────────────── */
/* The booking carries two people and they may differ, the owner's ruling of
   3 Sep: pms.customerId is who Mews says the booking is for NOW, and
   prearrival.forCustomerId is who the ANSWERS were given for. The answers
   are personal and follow their person, so on the very event that changes
   the customer, the form is stamped with the OLD one - re-attributing a
   reservation must not re-home what somebody else already said. */
const CID_A = "7c1e4a90-3b55-4a11-9d02-b4a800c12abc";
const CID_B = "9a2b7c31-88d4-4e0b-9c1f-2b6d5e7a1c04";
install();
await post(Object.assign({}, RES, { CustomerId: CID_A }));
ck("an untouched form is not stamped: nobody has answered anything",
   STORE["/bookings/" + RES.MewsId + "/prearrival"] === undefined);
STORE["/bookings/" + RES.MewsId + "/prearrival/at"] = "2026-09-01T09:00:00Z";
await post(Object.assign({}, RES, { CustomerId: CID_B }));
ck("the event that changes the customer stamps the answers with the OLD one",
   STORE["/bookings/" + RES.MewsId + "/prearrival"].forCustomerId === CID_A);
ck("while the booking itself moves to the new customer",
   STORE["/bookings/" + RES.MewsId + "/pms"].customerId === CID_B);
await post(Object.assign({}, RES, { CustomerId: CID_B }));
ck("a standing stamp is never overwritten",
   STORE["/bookings/" + RES.MewsId + "/prearrival"].forCustomerId === CID_A);
/* The guest-first case: the form is answered days before Mews sends the
   booking, so there is no prev to prefer and the incoming customer is the
   person the answers were given for. */
install();
STORE["/bookings/" + RES.MewsId + "/prearrival/at"] = "2026-09-01T09:00:00Z";
await post(Object.assign({}, RES, { CustomerId: CID_A }));
ck("a form answered before Mews knew the booking is stamped on first sight",
   STORE["/bookings/" + RES.MewsId + "/prearrival"].forCustomerId === CID_A);

/* ── the rate ───────────────────────────────────────────────── */
/* The Mews rate name, as words. The desk's booking flags read it through
   BOOKING_FLAGS in nala-shared.js; this Worker only carries it, so all that
   is pinned here is the carrying. */
install();
await post(Object.assign({}, RES, { RateName: "Luxury Escapes AU - BB" }));
ck("the rate name is kept on the booking",
   STORE["/bookings/" + RES.MewsId + "/pms"].rate === "Luxury Escapes AU - BB");
ck("and is not copied into every night",
   STORE["/stays/2026-09-10/3"].rate === undefined);

/* The triggers carry the field unevenly, so an event without it must leave
   the stored rate standing rather than nulling it away: the explicit-null
   treatment is for fields being REMOVED, and this one is merely unmapped on
   some triggers. Without this, the first modification after a new booking
   would strip the breakfast pill off the Service Sheet. */
await post(RES);
ck("an event with no rate leaves the stored one standing",
   STORE["/bookings/" + RES.MewsId + "/pms"].rate === "Luxury Escapes AU - BB");

/* A Rate mapped as Mews nests it is an object, which coerces to null, and
   null in this PATCH is a deletion. It must be treated as unmapped. */
await post(Object.assign({}, RES, { Rate: { Id: "r-1", Name: "nested" } }));
ck("and a rate mapped as a nested object does not wipe it either",
   STORE["/bookings/" + RES.MewsId + "/pms"].rate === "Luxury Escapes AU - BB");

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
await wake();
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

/* ── a Mews change under a massage ───────────────────────────────────────
 * The spaStay event, the owner's ask of 27 Aug: somebody holds a live
 * treatment and the stay it hangs on is cancelled, or its dates move out
 * from under the chosen day. Declined records are past caring. */
const BID = "ff129c05-9902-4d9f-9bfd-b4a800a91f52";

installSweep({}, {}, {});
await post(RES);
STORE["/spa/" + BID] = { t1: { status: "booked", day: "2026-09-11",
                               time: "10:00", at: "x", source: "prearrival" } };
PUSHES.length = 0;
await post(Object.assign({}, RES, { State: "Canceled" }));
ck("a cancellation under a booked massage fires spaStay with the villa",
   PUSHES.length === 1 && PUSHES[0].event === "spaStay" &&
   PUSHES[0].villa === "3" && PUSHES[0].idToken === "T");

installSweep({}, {}, {});
await post(RES);
STORE["/spa/" + BID] = { t1: { status: "declined", reqDay: "2026-09-11", at: "x" } };
PUSHES.length = 0;
await post(Object.assign({}, RES, { State: "Canceled" }));
ck("a declined record is past caring: a cancellation over it stays quiet",
   PUSHES.length === 0);

installSweep({}, {}, {});
await post(RES);
STORE["/spa/" + BID] = { t1: { status: "booked", day: "2026-09-11",
                               time: "10:00", at: "x" } };
PUSHES.length = 0;
await post(Object.assign({}, RES, { StartUtc: "2026-09-14T04:00:00Z",
                                    EndUtc: "2026-09-17T02:00:00Z" }));
ck("a date change stranding a booked day fires spaStay",
   PUSHES.length === 1 && PUSHES[0].event === "spaStay");
PUSHES.length = 0;
await post(RES);
ck("a change that still covers the day stays quiet", PUSHES.length === 0);
/* The departure DAY itself is bookable - stayDays' own rule - so a
 * massage on the checkout morning is inside the stay, not stranded. */
STORE["/spa/" + BID] = { t1: { status: "booked", day: "2026-09-13",
                               time: "10:00", at: "x" } };
PUSHES.length = 0;
await post(RES);
ck("a massage on the departure morning is not stranded", PUSHES.length === 0);
/* An open ask is judged on the day it asked about. */
STORE["/spa/" + BID] = { t1: { status: "requested", reqDay: "2026-09-12", at: "x" } };
PUSHES.length = 0;
await post(Object.assign({}, RES, { EndUtc: "2026-09-11T02:00:00Z" }));
ck("an ask now outside the shortened stay fires spaStay",
   PUSHES.length === 1 && PUSHES[0].event === "spaStay");

/* ── the spa ask sweep ───────────────────────────────────────────────────
 * A guest's form answer is born in the browser and nothing staff-side sees
 * it happen; the sweep announces each one once, as spaRequest. Every villa
 * is marked done in /hk so the arriving sweep stays quiet and the pushes
 * here are the spa sweep's alone. */
installSweep({
  "9":  { id: "s9",  arrive: TODAY, depart: "2026-09-12" },
  "12": { id: "s12", arrive: TODAY, depart: "2026-09-12" },
  "14": { id: "s14", arrive: TODAY, depart: "2026-09-12" },
  "15": { id: "s15", arrive: TODAY, depart: "2026-09-12" },
}, {
  "9": { done: "x" }, "12": { done: "x" }, "14": { done: "x" }, "15": { done: "x" },
}, {
  "s9":  { wellness: true, wellDay: "2026-09-11", wellTime: "morning" },
  "s12": { wellness: false },
  "s14": { wellness: true },
});
/* s15 never answered the form; s14's ask was already answered at the desk. */
STORE["/spa/s14"] = { t1: { status: "booked", day: TODAY, time: "10:00",
                            at: "x", source: "prearrival" } };
await wake();
ck("the sweep announces the answered form once, as spaRequest, with the villa",
   PUSHES.filter((p) => p.event === "spaRequest").length === 1 &&
   PUSHES.some((p) => p.event === "spaRequest" && p.villa === "9" &&
                      p.idToken === "T"));
ck("a no thank you, a silent form and an answered ask are all quiet",
   !PUSHES.some((p) => p.event === "spaRequest" &&
                       (p.villa === "12" || p.villa === "14" || p.villa === "15")));
ck("the marker means announced, is written before the send, and only then",
   !!STORE["/spaalerts/s9"] && !STORE["/spaalerts/s12"] && !STORE["/spaalerts/s15"] &&
   CALLS.indexOf("PUT /spaalerts/s9") > -1 &&
   CALLS.indexOf("PUT /spaalerts/s9") < CALLS.indexOf("PUSH 9"));

/* A guest answering later: quiet inside the hour, announced by the next
 * sweep, once - and the marker still guards the ask announced before. */
STORE["/bookings/s15/prearrival"] = { wellness: true };
PUSHES.length = 0;
await wake();
ck("inside the hour the sweep rests: the gate, not the marker, quiets it",
   PUSHES.length === 0);
delete STORE["/spaalerts/sweptAt"];
await wake();
ck("a form answered later is announced by the next sweep, once",
   PUSHES.filter((p) => p.event === "spaRequest").length === 1 &&
   PUSHES[0].villa === "15");
ck("and the marker still guards the already-announced ask",
   !PUSHES.some((p) => p.villa === "9"));
delete STORE["/spaalerts/sweptAt"];
PUSHES.length = 0;
await wake();
ck("a sweep with nothing new announces nobody", PUSHES.length === 0);

globalThis.Date = RealDate;

console.log("RESULT: %d passed, %d failed", P, F);
if (F) process.exit(1);
