/* NALA Mews sync Worker
 *
 * Zapier posts one reservation here on every Mews reservation event. This
 * signs in as the sync staff account, writes the PMS half of the booking, and
 * maintains the per night index the boards read.
 *
 * It writes exactly two things and nothing else:
 *   /bookings/<id>/pms          the reservation as Mews states it
 *   /stays/<date>/<villa>       one entry per villa night, holding a summary
 *
 * It never touches prearrival or dining. Those belong to the app, and the
 * rules enforce the split rather than trusting this file.
 *
 * Secrets to set in the Cloudflare dashboard, exactly these four names:
 *   SYNC_EMAIL     the sync account address: the six digit code you wrote down
 *                  in job 3, followed by @staff.nala. Do not write it into
 *                  this file, or anywhere else in this repo, which is public.
 *   SYNC_PASSWORD  its six digit code, which is the same six digits
 *   ZAP_SECRET     any long random string you invent, also given to Zapier
 *   FB_API_KEY     AIzaSyA0zAzL-zfPivrIRhY_ip8BABjuYVMlzqI
 *
 * FB_API_KEY is a secret only for tidiness. Firebase web API keys are public
 * by design and this one is already in auth.js in a public repo. The rules are
 * what protect the data, not the key.
 */

const DB = "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app";

/* The sign in costs a round trip, so the token is held for the life of the
   isolate. Firebase ID tokens last an hour; expiring at fifty minutes leaves
   room for a slow request rather than discovering the expiry mid write. */
let TOKEN = null, TOKEN_AT = 0;

async function idToken(env) {
  if (TOKEN && Date.now() - TOKEN_AT < 50 * 60 * 1000) return TOKEN;
  const r = await fetch(
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + env.FB_API_KEY,
    { method: "POST",
      headers: { "Content-Type": "application/json" },
      /* Trimmed for the same reason as the shared secret: a value pasted into
         a dashboard often carries a trailing newline, and Firebase answers a
         newline in an address with INVALID_EMAIL, which reads like the address
         is wrong rather than merely untidy. */
      body: JSON.stringify({ email: (env.SYNC_EMAIL || "").trim(),
                             password: (env.SYNC_PASSWORD || "").trim(),
                             returnSecureToken: true }) });
  const j = await r.json();
  if (!r.ok || !j.idToken) {
    var m = j.error && j.error.message;
    /* Name the likely cause rather than passing Firebase's code straight
       through, because INVALID_EMAIL sounds like the account is wrong when it
       usually means SYNC_EMAIL is missing its @staff.nala part. */
    if (m === "INVALID_EMAIL") m = "INVALID_EMAIL: SYNC_EMAIL should be the six digit code then @staff.nala";
    if (m === "EMAIL_NOT_FOUND") m = "EMAIL_NOT_FOUND: no such account, check the six digits";
    if (m === "INVALID_LOGIN_CREDENTIALS" || m === "INVALID_PASSWORD")
      m = "wrong passcode: SYNC_PASSWORD is the six digits alone, no @staff.nala";
    throw new Error("sign in failed: " + m);
  }
  TOKEN = j.idToken; TOKEN_AT = Date.now();
  return TOKEN;
}

async function db(env, path, method, body) {
  const t = await idToken(env);
  const r = await fetch(DB + path + ".json?auth=" + t, {
    method: method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) throw new Error(method + " " + path + " -> " + r.status + " " + await r.text());
  return r.status === 204 ? null : r.json();
}

/* Dates are stored the way dkey() in nala-shared.js writes them, YYYY-MM-DD,
   so /bookings joins to /hk/<date> and roomguests with no conversion.

   Mews sends true UTC. Confirmed 18 Aug: 2026-09-18T04:00:00Z is 2pm at the
   resort. Until then this kept the date part of the string as written, which
   is the local date only for timestamps before 2pm UTC. Everything after that
   belongs to the NEXT local day and was being filed a day early: an early
   arrival at 8am local is 22:00 UTC the evening before, and the villa would
   have shown the guest arriving, and the Cleans board a job, on the wrong day.

   A zone name rather than a fixed +10, so summer time is the runtime's problem
   rather than a number in here that is right for half the year. Queensland
   does not observe it; if the resort is in a state that does, change this one
   line and the suite will still hold. */
const RESORT_TZ = "Australia/Brisbane";
const DATE_AT_RESORT = new Intl.DateTimeFormat("en-CA", {
  timeZone: RESORT_TZ, year: "numeric", month: "2-digit", day: "2-digit" });

function dkey(v) {
  if (!v) return null;
  const s = String(v);
  /* A date with no time is already a date. Mews sends timestamps, but the Zap
     can be mapped to a date-only field, and reinterpreting midnight in a zone
     would move it a day. */
  if (/^\d{4}-\d{2}-\d{2}$/.test(s.trim())) return s.trim();
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const t = new Date(s);
  /* Something shaped like a date but not parseable as an instant keeps the
     old behaviour rather than becoming null: half a date beats none. */
  if (isNaN(t)) return m[0];
  return DATE_AT_RESORT.format(t);
}

/* Every night the villa is occupied: arrival inclusive, departure exclusive.
   A guest departing on the 14th does not occupy the villa on the night of the
   14th, and including it would put two bookings in one villa on turnover day
   for every single stay. */
function nights(arrive, depart) {
  const out = [];
  if (!arrive || !depart) return out;
  const a = new Date(arrive + "T00:00:00Z"), b = new Date(depart + "T00:00:00Z");
  for (let d = a; d < b; d.setUTCDate(d.getUTCDate() + 1)) {
    out.push(d.toISOString().slice(0, 10));
    if (out.length > 120) break;   /* a runaway range must not write forever */
  }
  return out;
}

/* ── the arriving-soon sweep, run from the cron trigger ──────────────────
 *
 * nala-push, the notification Worker. Not in this repo: it holds the VAPID
 * keys and routes an event to the roles that switched it on. This is the
 * same URL every page posts to from notifyPush() in nala-shared.js. */
const PUSH_URL = "https://nala-push.ben-681.workers.dev";

const HOUR_AT_RESORT = new Intl.DateTimeFormat("en-GB", {
  timeZone: RESORT_TZ, hour: "2-digit", hourCycle: "h23" });

/* The same resolution cleaners.html renders, kept in step by hand and by the
 * suite: reception's approved hour, else the guest's slot, else 14, because
 * 2pm is the resort's standing promise and an absent answer is not an
 * unknown one. */
function effectiveEta(pre) {
  pre = pre || {};
  const ap = Number(pre.arriveApproved);
  if (pre.arriveApproved != null && ap >= 11 && ap <= 23) return ap;
  const s = String(pre.arriveSlot || "");
  if (s === "before2") return 14;
  if (s === "after5") return 17;
  if (s === "14" || s === "15" || s === "16" || s === "17") return Number(s);
  return 14;
}

/* A villa inside its red hour that nobody has claimed gets one notification.
 * The board can only colour a tile; if no cleaner is looking at it, the red
 * hour passes silently, and this is triggered by nothing happening, so no
 * tap exists to hang a page side send on.
 *
 * Send once: the /alerts marker is written before the send and checked
 * first, in the manner of the menu announcement, so however many wakes
 * cross the red hour the phone buzzes for a villa once per day. A claimed,
 * done or pushed villa stays quiet: the point is a guest who is close with
 * nobody on the job, and management resolves the board nightly, so a late
 * red never finds unclaimed work to announce. */
async function alertArrivals(env) {
  const now = new Date();
  const today = DATE_AT_RESORT.format(now);
  const h = Number(HOUR_AT_RESORT.format(now));
  const stays = await db(env, "/stays/" + today, "GET") || {};
  const hk = await db(env, "/hk/" + today, "GET") || {};
  const alerts = await db(env, "/alerts/" + today, "GET") || {};
  const sent = [];

  /* Arrivals the way the board decides them: the manager's override wins,
     otherwise the booking. A manual "Arriving tonight" tick has no booking
     at all, so the candidates are the union of both sources. */
  const villas = new Set(Object.keys(stays));
  for (const v in hk) if (hk[v] && hk[v].arriving === true) villas.add(v);

  for (const v of villas) {
    const s = stays[v], k = hk[v] || {};
    const booked = !!(s && typeof s === "object" && s.id && dkey(s.arrive) === today);
    const arriving = k.arriving === true ? true
                   : k.arriving === false ? false : booked;
    if (!arriving) continue;
    if (k.done || k.pushed || k.takenBy) continue;
    if (alerts[v]) continue;
    /* One read per candidate, after the cheap filters: most wakes read
       nothing beyond the three lists above. */
    const pre = booked
      ? await db(env, "/bookings/" + s.id + "/prearrival", "GET") : null;
    if (h < effectiveEta(pre) - 1) continue;
    /* Marker first. If this write fails the send never happens, and the
       next wake tries again; the reverse order could buzz every five
       minutes forever. */
    await db(env, "/alerts/" + today + "/" + v, "PUT",
             { at: now.toISOString() });
    /* Fire and tolerate: a lost notification costs a buzz, not data, and
       the marker already says this villa had its one chance. */
    try {
      await fetch(PUSH_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken: await idToken(env),
                               event: "arriving", villa: v }) });
    } catch (e) {}
    sent.push(v);
  }
  return sent;
}

/* ── the spa ask sweep, run from the same cron wake ──────────────────────
 *
 * A guest's massage request is born in the browser: the pre-arrival form
 * writes /bookings/<id>/prearrival and nothing server-side sees it happen,
 * so no staff tap exists to hang a notification on - the same shape as the
 * red hour above. The masseuse used to find these only by opening his
 * board. This sweep announces each answered form once, as the spaRequest
 * event, so his phone buzzes within the hour instead.
 *
 * Send once: the /spaalerts/<booking> marker is written before the send,
 * the alertArrivals order, so a crash cannot buzz forever. The marker
 * means ANNOUNCED, never checked: a booking whose form is still
 * unanswered stays unmarked and is read again next sweep, or a guest
 * answering on day three would never be announced at all. An ask already
 * answered at the desk needs no announcement - the record born from the
 * form says so - and is skipped without a read. /spaalerts is not named
 * in rules.json, so it falls to the $other catch-all like /invites: no
 * rules change.
 *
 * Hourly, gated by the sweptAt stamp rather than per wake: wakes can be
 * minutes apart, the reads below cost about one per unanswered booking,
 * and an ask lands days before its massage, so within-the-hour is prompt.
 * 45 days of stays in ONE filtered read, keyed on the date - the
 * send-invites bound, the furthest out a form can exist - rather than a
 * read per day, which would spend the whole subrequest budget on nothing.
 */
const SPA_SWEEP_MS = 55 * 60 * 1000;
const INVITE_WINDOW_DAYS = 45;

async function announceSpaAsks(env) {
  const seen = await db(env, "/spaalerts", "GET") || {};
  if (seen.sweptAt && Date.now() - Date.parse(seen.sweptAt) < SPA_SWEEP_MS)
    return [];
  await db(env, "/spaalerts/sweptAt", "PUT", new Date().toISOString());
  const today = DATE_AT_RESORT.format(new Date());
  const end = DATE_AT_RESORT.format(
    new Date(Date.now() + INVITE_WINDOW_DAYS * 24 * 60 * 60 * 1000));
  const t = await idToken(env);
  const r = await fetch(DB + "/stays.json?orderBy=" +
    encodeURIComponent('"$key"') + "&startAt=" + encodeURIComponent('"' + today + '"') +
    "&endAt=" + encodeURIComponent('"' + end + '"') + "&auth=" + t);
  const stays = r.ok ? await r.json() : null;
  const spa = await db(env, "/spa", "GET") || {};
  /* First villa seen wins, the boards' own rule for a moved guest. The
     window is re-filtered here because the mock database - and a Firebase
     asked without an index - may hand back more dates than asked for. */
  const byId = {};
  for (const d of Object.keys(stays || {}).sort()) {
    if (d < today || d > end) continue;
    for (const v in stays[d]) {
      const e = stays[d][v];
      const id2 = (e && typeof e === "object") ? e.id : e;
      if (id2 && !byId[id2]) byId[id2] = String(v);
    }
  }
  const sent = [];
  for (const id2 of Object.keys(byId)) {
    if (seen[id2]) continue;
    const answered = Object.keys(spa[id2] || {}).some((tid) =>
      spa[id2][tid] && spa[id2][tid].source === "prearrival");
    if (answered) continue;
    let pre = null;
    try { pre = await db(env, "/bookings/" + id2 + "/prearrival", "GET"); }
    catch (e) { continue; }
    if (!pre || pre.wellness !== true) continue;
    await db(env, "/spaalerts/" + id2, "PUT", { at: new Date().toISOString() });
    try {
      await fetch(PUSH_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken: await idToken(env),
                               event: "spaRequest", villa: byId[id2] }) });
    } catch (e) {}
    sent.push(id2);
  }
  return sent;
}

/* Zapier field names vary with how the Zap is mapped, so each value is looked
   for under several plausible keys rather than one. Mapping in Zapier to any
   of these works; mapping to something else does not, which is why the list
   is here where it can be read rather than in a doc that drifts. */
/* A Mews identifier is a GUID. Zapier's event key is 32 hex characters with no
   dashes, and the two are easy to mix up in a field mapping. */
function isGuid(v) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    .test(String(v || ""));
}

/* The first candidate that is actually a GUID. Falls back to the first one
   present so the caller can report what arrived, which is then refused with a
   message rather than stored as a new booking. */
/* ── coercion to what the rules will accept ────────────────────────────
   The database validates every field it knows about, and one wrong type
   refuses the WHOLE write, not the offending field. So a single unexpected
   value from Zapier costs the entire reservation, and the error that comes
   back says only "Permission denied", which reads like a credentials problem
   and sends whoever is debugging it to the wrong place entirely. That is
   exactly what happened on 18 Aug: check-ins were failing with 401 and the
   sync account was blameless.

   Zapier does not promise types. The same field arrives as a string on one
   trigger and a number on the next, and a field that is normally a GUID can
   arrive as an object when Mews nests it. So nothing is trusted: every value
   is coerced to what the rule expects, or dropped.

   Dropped, not guessed. A number where a name should be is not a name, and
   writing "123" as somebody's first name to satisfy a validator would put a
   lie on the arrivals board. Null deletes the key, which is honest: we do not
   know, rather than we know this.                                          */
function asText(v, max) {
  if (typeof v === "string") return v.length > max ? v.slice(0, max) : v;
  /* A number is a reasonable text value for identifiers and phone numbers,
     which Mews and Zapier both send either way round. */
  if (typeof v === "number" && Number.isFinite(v)) {
    const s = String(v);
    return s.length > max ? s.slice(0, max) : s;
  }
  return null;
}

function asCount(v, min, max) {
  const n = typeof v === "number" ? v
          : (typeof v === "string" && v.trim() !== "") ? Number(v)
          : NaN;
  if (!Number.isFinite(n)) return null;
  if (n < min || n > max) return null;
  return n;
}

/* villa validates as a short string OR a number, so either is passed through
   and anything else becomes null. */
function asVilla(v) {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  return asText(v, 10);
}

/* bookingNumber validates as string or number with no length bound. */
function asNumberOrText(v) {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  return asText(v, 120);
}

function pickGuid(o, names) {
  for (const n of names) {
    if (isGuid(o[n])) return o[n];
  }
  return pick(o, names);
}

function pick(o, names) {
  for (const n of names) {
    if (o[n] !== undefined && o[n] !== null && o[n] !== "") return o[n];
  }
  return null;
}

/* Zapier sends this two ways depending on how the Zap maps it: a real nested
   array under `companions`, or flattened keys like "Companions 1 First Name".
   Both are read, because which one arrives is a choice made in a Zap editor
   and not something this code can see. */
function companionNames(p) {
  const out = [];
  const arr = p && p.companions;
  if (Array.isArray(arr)) {
    for (const c of arr) {
      if (!c || typeof c !== "object") continue;
      const f = pick(c, ["FirstName", "First Name", "first_name", "firstName"]);
      const l = pick(c, ["LastName", "Last Name", "last_name", "lastName"]);
      const n = [f, l].filter(Boolean).join(" ").trim();
      if (n) out.push(n);
    }
  }
  for (let i = 0; i < 8; i++) {
    const f = pick(p, ["Companions " + i + " First Name",
                       "companions_" + i + "_first_name"]);
    const l = pick(p, ["Companions " + i + " Last Name",
                       "companions_" + i + "_last_name"]);
    const n = [f, l].filter(Boolean).join(" ").trim();
    if (n) out.push(n);
  }
  return out;
}

/* The first companion who is NOT the guest already named on the reservation.
   Index 0 was Erik Anders in the run this was written against, and Erik Anders
   was also the reservation's own guest, so taking index 1 would have been
   right that day and wrong the day a booking arrives the other way round. */
function companionName(p) {
  const mine = [pick(p, ["FirstName", "first_name", "firstName", "CustomerFirstName"]),
                pick(p, ["LastName", "last_name", "lastName", "CustomerLastName"])]
                 .filter(Boolean).join(" ").trim().toLowerCase();
  const seen = {};
  for (const n of companionNames(p)) {
    const k = n.toLowerCase();
    if (k === mine || seen[k]) continue;   /* the booker, or a duplicate */
    seen[k] = true;
    return n;
  }
  return null;
}

function readReservation(p) {
  return {
    /* By shape, not by name, because the name is not consistent.

       Measured from three Zapier triggers on 17 Aug:
         New reservation  the reservation GUID arrives as  Id      (no MewsId)
         Modification     the reservation GUID arrives as  MewsId  (Id is
                          Zapier's own 32 character event key)
         Cancellation     the reservation GUID arrives as  Id

       So no single field name is right, and picking the first one present gets
       modifications wrong. Every Mews identifier is a GUID with dashes and
       Zapier's key is 32 hex characters without, so the shape settles it.

       Keying on Zapier's key was the cause of one guest appearing in three
       villas at once, and of a move never clearing the villa it left.

       Id2 joined the list 1 Sep, LAST so a real Id or MewsId outranks it.
       The live Zap serialises a second id row under that key, and on a new
       reservation's first event it was the only key carrying the GUID -
       Mews Id does not exist until the first modification - so every new
       booking 400'd once, invisibly, and waited for its next touch to
       exist. Shape still rules: a non GUID under Id2 is refused below. */
    id:      pickGuid(p, ["MewsId", "Mews Id", "mews_id", "mewsId",
                          "Id", "id", "ReservationId", "reservation_id", "bookingId",
                          "Id2", "Id 2"]),
    first:   pick(p, ["FirstName", "first_name", "firstName", "CustomerFirstName"]),
    last:    pick(p, ["LastName", "last_name", "lastName", "CustomerLastName"]),
    phone:   pick(p, ["Phone", "phone", "PhoneNumber", "phone_number", "CustomerPhone"]),
    arrive:  dkey(pick(p, ["StartUtc", "start_utc", "ArrivalUtc", "arrive", "CheckInDate"])),
    depart:  dkey(pick(p, ["EndUtc", "end_utc", "DepartureUtc", "depart", "CheckOutDate"])),
    /* String, always. Mews may send 3 or "3" depending on the mapping, and a
       number here compares unequal to the stored string, which makes every
       event look like a villa move and churn the index for nothing. */
    villa:   (function(v){ return v === null ? null : String(v); })(
               pick(p, ["ResourceName", "resource_name", "SpaceName", "RoomNumber", "villa", "room"])),
    state:   String(pick(p, ["State", "state", "Status", "status"]) || "confirmed").toLowerCase(),
    /* Mews' own last-changed stamp, not ours. Webhook delivery is not ordered,
       so this is the only way to tell a late old event from a new one. */
    /* UpdateUtc without the d is included because that is what the Zap was
       mapped to, and a silently missing update stamp turns the late event
       guard off without any visible sign. */
    updated: pick(p, ["UpdatedUtc", "UpdateUtc", "updated_utc", "UpdatedAt",
                      "LastUpdateUtc", "updated"]),

    /* Carried through but not acted on. Mews sends them, storing them is free,
       and the alternative is discovering later that a year of bookings lack a
       field nobody thought to keep. */
    /* The reservation number staff see in Mews, 1159 in the 17 Aug run. Number
       first, because BookingId is the group's number rather than this
       reservation's, and the number on the screen is what somebody will read
       out over the phone. Not used as a key: a GUID is guaranteed unique and a
       sequential number is only unique per property. */
    bookingNumber: pick(p, ["Number", "ConfirmationNumber", "BookingId"]),
    groupId:       pick(p, ["GroupId", "ReservationGroupId"]),
    /* The person, as opposed to the stay. A reservation id changes every time
       somebody books; the customer id does not, so it is the only handle on
       "this is the same guest as last March", and stage 6 needs it to write a
       dietary back to the profile rather than to one night.

       Stored now because it costs nothing now. Backfilling it later means
       replaying every reservation event that has ever fired, and Zapier does
       not keep them. Read by shape as well as name for the same reason as the
       reservation id: the field is CustomerId on the reservation trigger and
       AccountId on some others, and one of them is the wrong person.        */
    /* The second guest. Confirmed against a real Zap run on 19 Aug rather
       than guessed: companions is an ARRAY, index 0 is the guest whose name
       is already on the reservation, and the names are split into First Name
       and Last Name.

       Which index holds the companion is NOT assumed. Every companion is read
       and the one matching the reservation's own guest is dropped, so a
       booking where the companion happens to come first still works. That
       costs nothing and removes the only guess left in it. */
    companion:     companionName(p),
    /* Whatever a receptionist typed into Mews. Read for the first time on
       19 Aug: it was being discarded, so the two systems held different facts
       about the same guest and neither showed the other's. */
    mewsNote:      pick(p, ["Notes", "notes", "Note", "note",
                            "GuestNotes", "guest_notes", "CustomerNotes"]),
    customerId:    pickGuid(p, ["CustomerId", "customer_id", "CustomerID",
                                "AccountId", "customerId"]),
    /* The Mews rate, as words. Exactly ONE flag rides on it: Luxury Escapes,
       matched in RATE_FLAG in nala-shared.js - matched THERE and not here, so
       the rule lives once and this Worker stays a courier. Every other flag
       is created by an admin on Flag Settings and ticked by hand at the desk.
       The owner's ruling, confirmed 28 Aug.

       This comment used to name Breakfast included as automatic too, and
       pointed at a BOOKING_FLAGS that has never existed in this codebase.
       Nothing read it, so nothing broke; what it cost was a session spent
       working out how a breakfast flag had "switched itself on" for a
       Luxury Escapes booking. It had not. An admin had ticked it.

       Matched on the rate's WORDS, not on a code. Nothing here reads a rate
       code, and a payload that carried one in place of the name would drop
       the pill silently - no error, just a booking that stops wearing it.
       Which key the Zap maps it under has not been seen live, hence the
       spread; RateId is a GUID and useless to a human, so only the name is
       kept. */
    rate:          pick(p, ["RateName", "Rate Name", "rate_name", "rateName",
                            "RatePlanName", "Rate", "rate"]),
    adults:        pick(p, ["AdultCount", "adults"]),
    children:      pick(p, ["ChildCount", "children"])

    /* NotesText, NotesType, Companions0Notes and SpaceState were read here and
       written into /bookings/<id>/pms. They are no longer.

       /bookings/<id> is readable by anyone holding the id, deliberately, so
       that a guest can open a pre-arrival link without signing in. The notes
       fields are free text written by reception, about the guest, for staff.
       Nobody typing one in Mews expects the guest to read it, and the
       pre-arrival SMS carries exactly the id needed to. One forwarded message
       was the whole exposure.

       Dropping them rather than moving them to a node behind auth, because
       nothing reads them: stage 6 writes notes TO Mews from the app, it never
       reads them back. Storing staff free text next to a public link earned
       nothing. If a later stage does need them, give them their own node with
       an auth rule, and do the rules first.

       SpaceState went with them. It was stored while being explicitly never
       used, which is the worst side of the trade: no benefit, some exposure. */
  };
}

/* The app has seventeen villas, keyed "1" to "17" everywhere: /hk/<date>/<villa>,
   roomguests, and now /stays. Mews sends whatever the space is called, and the
   Zap maps Space Name, which nobody here controls.

   An unrecognised name is not written to /stays. It would create a key no board
   ever reads, so the guest would be invisible while every log line said the
   sync succeeded, which is the failure that is hardest to notice. The booking
   still lands under /bookings, and the response names the rejected value so it
   shows up in the Zap history instead of nowhere. */
const VILLAS = 17;
function knownVilla(v) {
  if (v === null || v === undefined) return false;
  return /^\d+$/.test(String(v)) && +v >= 1 && +v <= VILLAS;
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") return new Response("POST only", { status: 405 });

    /* The shared secret may arrive as a header or as a query parameter,
       because Zapier makes one easier than the other depending on the action
       chosen, and being strict here only produces a silent failure later. */
    /* Both sides trimmed. Copying a secret into a dashboard very often carries
       a trailing newline, which is invisible and makes an identical looking
       pair compare unequal. */
    const url = new URL(request.url);
    const want  = (env.ZAP_SECRET || "").trim();
    const given = (request.headers.get("x-nala-secret") ||
                   url.searchParams.get("secret") || "").trim();
    if (!want || given !== want) {
      /* Lengths only. They say whether the secret is missing, truncated or
         simply different, and they cannot be used to reconstruct it. */
      return new Response(JSON.stringify({
        error: "secret rejected",
        configured: !!want,
        configuredLength: want.length,
        receivedLength: given.length
      }), { status: 401, headers: { "Content-Type": "application/json" } });
    }

    let payload;
    try { payload = await request.json(); }
    catch (e) { return new Response("bad json", { status: 400 }); }

    const r = readReservation(payload);
    /* The keys that DID arrive, so the Zap history shows which mapping went
       missing. Keys only, never values: values are guest data and this reply
       lands in a dashboard other people read. */
    if (!r.id) return new Response(JSON.stringify({
      ok: false, error: "no reservation id in payload",
      receivedKeys: Object.keys(payload || {}).slice(0, 32)
    }), { status: 400, headers: { "Content-Type": "application/json" } });
    /* Refused rather than stored. A non GUID here means the Zap is mapping
       Zapier's own event key instead of the Mews reservation id, and storing it
       would create a fresh booking on every event, which is exactly the bug
       this check exists to prevent recurring. */
    if (!isGuid(r.id)) {
      return new Response(JSON.stringify({
        ok: false, error: "reservation id is not a Mews GUID",
        received: String(r.id).slice(0, 40),
        hint: "send both Id and MewsId from the Zap; the Worker takes whichever is a GUID"
      }), { status: 400, headers: { "Content-Type": "application/json" } });
    }

    try {
      /* Read what is already stored before writing, because a reservation that
         moved villa or changed dates leaves index entries behind under the OLD
         values. Without this a moved guest appears in two villas and the board
         is wrong in the way that is hardest to notice: it looks plausible. */
      let prev = null;
      try { prev = await db(env, "/bookings/" + r.id + "/pms", "GET"); }
      catch (e) { prev = null; }

      /* An event that Mews stamped earlier than what we already hold is a late
         delivery, not a change. Applying it would quietly undo a villa move
         and look like the sync inventing things. Nothing is written. */
      if (prev && prev.updated && r.updated && r.updated < prev.updated) {
        return new Response(JSON.stringify({ ok: true, id: r.id, skipped: "stale event" }),
                            { headers: { "Content-Type": "application/json" } });
      }

      const stale = prev ? nights(prev.arrive, prev.depart) : [];

      const cancelled = r.state.indexOf("cancel") > -1;

      /* A later event with a bad villa must not erase what a good earlier one
         wrote. An unrecognised villa on a NEW booking writes no nights and
         says so, which is right: there is nothing to lose. The same value on
         a MODIFICATION of a booking whose villa WAS recognised fed the
         clear-by-looking pass below an empty "fresh" list, so every night the
         reservation held was deleted, none rewritten, and the reply was still
         ok: a name change with the villa unmapped removed the room from every
         board with the only trace a field in a Zap history nobody reads.
         Seen live 3 Sep. Refused whole instead - a 400 lands in the Zap
         history as an error, nothing is written, and the mapping gets fixed
         once, loudly, rather than destroying index entries quietly. */
      if (!cancelled && !knownVilla(r.villa) && prev && knownVilla(prev.villa)) {
        return new Response(JSON.stringify({
          ok: false, error: "unrecognised villa on a booking that had one",
          received: String(r.villa).slice(0, 40),
          held: String(prev.villa),
          hint: "map the space name into this trigger; nothing was changed"
        }), { status: 400, headers: { "Content-Type": "application/json" } });
      }

      /* A cancellation for a booking we have never seen clears nothing, and
         until now said so nowhere: the reply was a cheerful ok and the guest
         stayed on the board.

         The likely cause is an id mismatch. The cancellation trigger in Zapier
         has no MewsId field, only Id, so it only works if that Id is the SAME
         GUID as the reservation trigger's Mews Id. If it is a cancellation
         event id instead, nothing links the two and every cancellation lands
         here. Reported rather than swallowed, so the Zap history shows it. */
      const unknownCancel = cancelled && !prev;
      /* An unrecognised villa is treated as having no nights at all: the
         booking is recorded, the index is left alone rather than filled with a
         key nothing reads, and any nights this reservation previously held are
         still cleared below. */
      const fresh = (cancelled || !knownVilla(r.villa)) ? [] : nights(r.arrive, r.depart);

      /* Clear by looking, not by remembering.
      
         The first version deleted only the villa recorded in `prev`. That is a
         guess dressed as a fact: if prev is missing, or was written wrong, or
         the guest was moved twice between polls, the abandoned night is never
         touched and the same guest appears in two villas at once. It cost an
         evening and three copies of one booking across villas 13, 14 and 15.

         So instead: for every date this booking could touch, read what is
         actually there and delete any entry claiming to be THIS reservation
         that should not be. It is self healing, it fixes damage done before it
         existed, and it costs one read per date on an event that fires a few
         times a day.

         It cannot fix a booking that was cancelled and recreated in Mews. That
         is a different reservation id, so nothing links the two, and the old
         one only clears when its own cancellation arrives. */
      const window = stale.concat(fresh)
        .filter(function(d, i, a){ return a.indexOf(d) === i; })
        .sort();
      let cleared = 0;
      for (const d of window) {
        let day = null;
        try { day = await db(env, "/stays/" + d, "GET"); } catch (e) { day = null; }
        for (const v in (day || {})) {
          const entry = day[v];
          /* Tolerates the older shape, where the value was the id on its own. */
          const heldBy = (entry && typeof entry === "object") ? entry.id : entry;
          if (heldBy !== r.id) continue;
          const keep = !cancelled && String(v) === String(r.villa) && fresh.indexOf(d) > -1;
          if (!keep) { await db(env, "/stays/" + d + "/" + v, "DELETE"); cleared++; }
        }
      }

      const pmsPatch = {
        /* Every value coerced to what the rule expects. See asText above for
           why nothing here is trusted and why a bad value becomes null rather
           than a guess. The lengths match rules.json exactly: a value trimmed
           to 120 here is a value the database will accept, and a value trimmed
           to the wrong length is the same outage in a quieter form. */
        first: asText(r.first, 120), last: asText(r.last, 120),
        phone: asText(r.phone, 40),
        arrive: asText(r.arrive, 40), depart: asText(r.depart, 40),
        villa: asVilla(r.villa),
        state: cancelled ? "cancelled" : "confirmed",
        /* Mews has more states than we act on (Optional, Started, Processed).
           Only cancellation changes what we do, but the raw value is kept
           rather than discarded: the next question about this data will be
           easier to answer with it than without it. */
        companion: asText(r.companion, 120),
        mewsState: asText(r.state, 30),
        bookingNumber: asNumberOrText(r.bookingNumber),
        groupId: asText(r.groupId, 64),
        /* On the booking and not on the nights. A night is read by the boards
           twenty times an hour and none of them care who the person is; the
           write back to Mews happens once per booking and does. Copying it
           into every night would be fourteen copies of a fact used nowhere. */
        customerId: asText(r.customerId, 64),
        adults: asCount(r.adults, 0, 40), children: asCount(r.children, 0, 40),
        /* Explicit nulls, not omissions. A PATCH that simply stops sending a
           field leaves the old value sitting there, so every booking synced
           before today would keep the notes this change exists to remove.
           Null deletes the key, which makes the fix retroactive on the next
           event for each booking rather than only on new ones. */
        /* Still cleared from /bookings, and now for a reason rather than by
           omission: /bookings is readable by anybody holding a pre-arrival
           link, so a note about a guest must never be written there. The Mews
           note goes to /internal instead, below. */
        notes: null, notesType: null, spaceState: null, guestNotes: null,
        updated: asText(r.updated, 40),
        syncedAt: new Date().toISOString()
      };
      /* The rate, only when the Zap sent one that coerces to text - an
         omission, not an explicit null like the notes above. Those nulls
         REMOVE fields on purpose; the rate is a field the triggers carry
         unevenly, and a modification mapped without it must not delete what
         the new-reservation event stored, or the breakfast pill vanishes
         from the Service Sheet the first time the guest changes anything.
         Coerced BEFORE the test for the same reason: a Rate mapped as a
         nested object coerces to null, and null here is a deletion. */
      const rateText = asText(r.rate, 120);
      if (rateText !== null) pmsPatch.rate = rateText;
      await db(env, "/bookings/" + r.id + "/pms", "PATCH", pmsPatch);

      /* The summary is duplicated into every night rather than stored once
         with the nights pointing at it. A board reads one date and needs the
         guest for each villa: with a pointer that is one request per villa, so
         a full house would cost eighteen where roomguests costs fourteen, and
         the boards were deliberately taken from nineteen requests to four.
         Writes happen per reservation event, reads happen every twenty seconds
         on five phones, so the duplication is paid in the cheap direction. */
      const summary = {
        /* Coerced for the same reason as the booking write, and it matters
           more here: a night refused is a guest missing from the arrivals
           board and the reservation sheet, with nothing on screen to say so. */
        id: asText(r.id, 64),
        first: asText(r.first, 120), last: asText(r.last, 120),
        phone: asText(r.phone, 40),
        companion: asText(r.companion, 120),
        arrive: asText(r.arrive, 40), depart: asText(r.depart, 40),
        adults: asCount(r.adults, 0, 40),
        /* One party can hold several villas: a family booking two of them is
           two reservations under one group, and each gets its own id. Without
           the group id on the night, the boards see two unrelated guests who
           happen to share a surname, and would seat them apart.

           It does NOT tell a two villa booking from a guest who was moved.
           Both look like one group across two villas with overlapping dates.
           Only a cancellation separates them, which is why the cancellation
           feed matters more than any of this. */
        groupId: asText(r.groupId, 64),
        /* Carried so staff can cross-check a booking against Mews without
           opening it. It is the only identifier here a human can read. */
        number: asNumberOrText(r.bookingNumber),
        /* Carried into every night so the app can tell a staff decision made
           against THIS version of the booking from one made before Mews last
           changed it. Without it, a villa staff marked vacant either sticks
           forever or is undone on the next poll, and neither is what was
           asked for. */
        updated: asText(r.updated, 40)
      };
      /* The Mews note, once. Written to its own staff-only node, and only
         when nothing is there: a manager's correction has to survive the next
         event for that booking, and Mews sends the whole reservation every
         time. So this seeds the record and never overwrites it.

         Kept in its own field, apart from the edited one, so the original is
         still readable after somebody rewrites it. */
      if (r.mewsNote) {
        let had = null;
        try { had = await db(env, "/internal/" + r.id + "/fromMews", "GET"); }
        catch (e) { had = null; }
        if (!had) {
          await db(env, "/internal/" + r.id, "PATCH",
                   { fromMews: asText(r.mewsNote, 2000) });
        }
      }

      /* A returning guest should not be asked again. The dietary is kept
         against the Mews customer, which outlives any one booking, so a
         booking seen for the first time is seeded from it.

         Only when the booking has no pre-arrival answers of its own: `at` is
         set the moment a guest or the desk touches the form, and seeding over
         that would replace what somebody just said with what they said last
         year. */
      if (r.customerId && !cancelled) {
        let started = null;
        try { started = await db(env, "/bookings/" + r.id + "/prearrival/at", "GET"); }
        catch (e) { started = null; }
        if (!started) {
          let known = null;
          try { known = await db(env, "/guests/" + r.customerId, "GET"); }
          catch (e) { known = null; }
          if (known && (known.diets || known.dnote)) {
            await db(env, "/bookings/" + r.id + "/prearrival", "PATCH",
                     { diets: Array.isArray(known.diets) ? known.diets : [],
                       dnote: asText(known.dnote, 500) || "" });
          }
        }
      }

      for (const d of fresh) {
        await db(env, "/stays/" + d + "/" + r.villa, "PUT", summary);
      }

      /* A Mews change under a massage, the owner's ask of 27 Aug: the
         booking a live treatment hangs on was cancelled, or its dates
         moved out from under the day somebody chose. One read; declined
         records are past caring. The spaStay event is fired once per
         Mews event, no marker - a cancellation is one event, and a buzz
         repeated by a Zapier retry collapses on the phone under its tag.
         The departure DAY itself is bookable - a morning massage before
         checkout, stayDays' own rule - so the stay runs arrival through
         departure date inclusive. */
      let spaTouched = false;
      try {
        const treatments = await db(env, "/spa/" + r.id, "GET");
        for (const tid in (treatments || {})) {
          const t2 = treatments[tid];
          if (!t2 || typeof t2 !== "object") continue;
          if (t2.status !== "requested" && t2.status !== "suggested" &&
              t2.status !== "booked") continue;
          if (cancelled) { spaTouched = true; break; }
          const day = t2.day || t2.reqDay;
          if (day && (day < dkey(r.arrive) || day > dkey(r.depart))) {
            spaTouched = true; break;
          }
        }
      } catch (e) {}
      if (spaTouched) {
        try {
          await fetch(PUSH_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ idToken: await idToken(env),
                                   event: "spaStay",
                                   villa: String(r.villa || "") }) });
        } catch (e) {}
      }

      return new Response(JSON.stringify({
        ok: true, id: r.id, villa: r.villa,
        state: cancelled ? "cancelled" : "confirmed",
        nights: fresh.length, cleared: cleared,
        /* Named so a mismatch is visible in the Zap history rather than
           looking like a success. */
        unknownCancellation: unknownCancel || undefined,
        /* Named rather than silent. A space Mews calls something the app does
           not recognise is a mapping problem, and this is where it surfaces. */
        unknownVilla: (!cancelled && !knownVilla(r.villa)) ? String(r.villa) : undefined
      }), { headers: { "Content-Type": "application/json" } });

    } catch (e) {
      /* A 500 makes Zapier retry, which is what should happen: a booking that
         failed to land is worse than one that lands twice, since every write
         here is idempotent. */
      TOKEN = null;
      /* "Permission denied" from the database means one of two very different
         things, and the message alone cannot tell them apart. Either the sync
         account is not signed in or has lost its role, which is a credentials
         problem, or every credential is fine and one field in the write failed
         validation, which refuses the whole write.

         On 18 Aug that ambiguity cost an evening: check-ins were failing with
         401 and the sync login was blameless. So the two are separated here.
         Whoever reads this in a Zap alert should not have to guess. */
      let msg = e.message;
      if (/Permission denied/i.test(msg)) {
        let who = null;
        try {
          const key = String(env.SYNC_EMAIL || "").toLowerCase().replace(/\./g, ",");
          who = await db(env, "/staff/" + key + "/role", "GET");
        } catch (probe) { who = "unreadable"; }
        msg += who === "sync" || who === "admin" || who === "staff"
          ? " | the sync account is signed in and holds the role '" + who
            + "', so this is NOT a credentials problem: a field in the write"
            + " failed validation, and one bad field refuses the whole write."
            + " Compare the payload against rules.json."
          : " | the sync account's role reads '" + String(who) + "'."
            + " It must be 'sync' at /staff/<email with dots as commas>."
            + " This IS a credentials or staff record problem.";
      }
      return new Response("sync failed: " + msg, { status: 500 });
    }
  },

  /* The cron wake. Kept to a dispatcher so the trigger can host more than
     one job: the parked sync heartbeat wants exactly this wake, and adding
     it later is one more waitUntil line, not a redesign. */
  async scheduled(event, env, ctx) {
    ctx.waitUntil(alertArrivals(env).catch(function (e) {
      /* A failed sweep must not look like a quiet one in the logs. */
      console.log("arriving sweep failed: " + e.message);
    }));
    ctx.waitUntil(announceSpaAsks(env).catch(function (e) {
      console.log("spa ask sweep failed: " + e.message);
    }));
  }
};
