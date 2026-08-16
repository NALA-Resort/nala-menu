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
   so /bookings joins to /hk/<date> and roomguests with no conversion. Mews
   sends ISO timestamps in UTC; only the date part is kept. */
function dkey(v) {
  if (!v) return null;
  const m = String(v).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? m[0] : null;
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

/* Zapier field names vary with how the Zap is mapped, so each value is looked
   for under several plausible keys rather than one. Mapping in Zapier to any
   of these works; mapping to something else does not, which is why the list
   is here where it can be read rather than in a doc that drifts. */
function pick(o, names) {
  for (const n of names) {
    if (o[n] !== undefined && o[n] !== null && o[n] !== "") return o[n];
  }
  return null;
}

function readReservation(p) {
  return {
    id:      pick(p, ["Id", "id", "ReservationId", "reservation_id", "bookingId"]),
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
    bookingNumber: pick(p, ["BookingId", "Number", "ConfirmationNumber"]),
    groupId:       pick(p, ["GroupId", "ReservationGroupId"]),
    adults:        pick(p, ["AdultCount", "adults"]),
    children:      pick(p, ["ChildCount", "children"]),
    notes:         pick(p, ["NotesText", "Notes"]),
    notesType:     pick(p, ["NotesType"]),
    /* Mews' own housekeeping state for the space. Recorded for interest only.
       It must never drive the Cleans board: that is /hk, it is ours, and two
       systems disagreeing about whether a villa is clean is worse than one. */
    spaceState:    pick(p, ["SpaceState"]),
    guestNotes:    pick(p, ["Companions0Notes", "CompanionNotes"])
  };
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
    if (!r.id) return new Response("no reservation id in payload", { status: 400 });

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
      const staleVilla = prev ? prev.villa : null;

      const cancelled = r.state.indexOf("cancel") > -1;
      const fresh = cancelled ? [] : nights(r.arrive, r.depart);

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
      for (const d of window) {
        let day = null;
        try { day = await db(env, "/stays/" + d, "GET"); } catch (e) { day = null; }
        for (const v in (day || {})) {
          const entry = day[v];
          /* Tolerates the older shape, where the value was the id on its own. */
          const heldBy = (entry && typeof entry === "object") ? entry.id : entry;
          if (heldBy !== r.id) continue;
          const keep = !cancelled && String(v) === String(r.villa) && fresh.indexOf(d) > -1;
          if (!keep) await db(env, "/stays/" + d + "/" + v, "DELETE");
        }
      }

      await db(env, "/bookings/" + r.id + "/pms", "PATCH", {
        first: r.first, last: r.last, phone: r.phone,
        arrive: r.arrive, depart: r.depart, villa: r.villa,
        state: cancelled ? "cancelled" : "confirmed",
        /* Mews has more states than we act on (Optional, Started, Processed).
           Only cancellation changes what we do, but the raw value is kept
           rather than discarded: the next question about this data will be
           easier to answer with it than without it. */
        mewsState: r.state,
        bookingNumber: r.bookingNumber, groupId: r.groupId,
        adults: r.adults, children: r.children,
        notes: r.notes, notesType: r.notesType,
        spaceState: r.spaceState, guestNotes: r.guestNotes,
        updated: r.updated || null,
        syncedAt: new Date().toISOString()
      });

      /* The summary is duplicated into every night rather than stored once
         with the nights pointing at it. A board reads one date and needs the
         guest for each villa: with a pointer that is one request per villa, so
         a full house would cost eighteen where roomguests costs fourteen, and
         the boards were deliberately taken from nineteen requests to four.
         Writes happen per reservation event, reads happen every twenty seconds
         on five phones, so the duplication is paid in the cheap direction. */
      const summary = {
        id: r.id, first: r.first, last: r.last, phone: r.phone,
        arrive: r.arrive, depart: r.depart, adults: r.adults
      };
      for (const d of fresh) {
        if (r.villa) await db(env, "/stays/" + d + "/" + r.villa, "PUT", summary);
      }

      return new Response(JSON.stringify({
        ok: true, id: r.id, villa: r.villa,
        state: cancelled ? "cancelled" : "confirmed",
        nights: fresh.length, cleared: stale.length
      }), { headers: { "Content-Type": "application/json" } });

    } catch (e) {
      /* A 500 makes Zapier retry, which is what should happen: a booking that
         failed to land is worse than one that lands twice, since every write
         here is idempotent. */
      TOKEN = null;
      return new Response("sync failed: " + e.message, { status: 500 });
    }
  }
};
