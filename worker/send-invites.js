/* NALA invitations Worker
 *
 * invitations.html posts here to send tonight's menu link by SMS. This is the
 * only place the ClickSend credential exists: never in the browser and never
 * in this repo, which is public until SECURITY.md job 4.
 *
 * The page proposes; this Worker decides. A browser can be edited, and a
 * browser that can name any phone number and any message body is a browser
 * that can send anything to anyone on the resort's sender ID. So for every
 * villa asked for, the stay and dinner cell are re-read from the database
 * here, the phone number comes off that record, and the link is rebuilt from
 * it. Nothing the browser typed reaches ClickSend except the message words,
 * and those are refused if they contain a URL.
 *
 * NOT deployed by worker/wrangler.jsonc, which builds nala-mews-sync. This is
 * a second Worker: create it in the Cloudflare dashboard as `nala-invites`
 * (the page posts to nala-invites.ben-681.workers.dev), paste or deploy this
 * file, and set the secrets below in the dashboard, never in this repo.
 *
 * Secrets to set, exactly these names:
 *   CLICKSEND_USERNAME  the API username from the ClickSend dashboard
 *   CLICKSEND_API_KEY   the API key generated beside it
 *   CLICKSEND_FROM      the verified own number, as ClickSend shows it,
 *                       e.g. +61400000000. This is the Guest Touch mobile,
 *                       so replies land on that handset.
 *   FB_API_KEY          AIzaSyA0zAzL-zfPivrIRhY_ip8BABjuYVMlzqI
 *
 * And one step that is not a secret: menu.nalaresort.com has to be registered
 * at dashboard.clicksend.com/sms/website-registration before any message
 * carrying the link will send at all. ClickSend confirmed it on 23 Aug. An
 * unregistered domain fails on the first real send and looks like a bug in
 * the page.
 *
 * FB_API_KEY is a secret only for tidiness: Firebase web API keys are public
 * by design and this one is in auth.js in a public repo. The rules protect
 * the data, not the key.
 *
 * As of this commit no ClickSend account exists, the secrets are not set, and
 * the sandbox this was written in reaches neither ClickSend nor Cloudflare.
 * worker/invites-test.mjs checks the logic against stubs; nothing here has
 * been run against the real services.
 */

const DB = "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app";
const CLICKSEND = "https://rest.clicksend.com/v3/sms/send";

/* The same CORS answer for every response, because the caller is a browser on
   menu.nalaresort.com. The token is the credential; the origin is not. */
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};
const reply = (status, body) =>
  new Response(JSON.stringify(body), {
    status, headers: { "Content-Type": "application/json", ...CORS } });

/* ── the link, in ONE function ──────────────────────────────────
   The twin of inviteLink in invitations.html. Both parameters on purpose:
   the villa traps a room move, the booking id is the secret. The eventual
   short token per booking replaces this function and its twin, nothing else. */
function inviteLink(bookingId, villa) {
  return "https://menu.nalaresort.com/?b=" + encodeURIComponent(bookingId) +
         "&r=" + encodeURIComponent(villa);
}

/* ── a phone number a machine can dial ──────────────────────────
   The twin of normalisePhone in nala-shared.js, carried here because a Worker
   cannot import from the site. E.164 or nothing: 04..., +614... and 614...
   with the right digit count become +614XXXXXXXX, and everything else is
   refused rather than guessed at - an international number, a landline, a
   mobile with digits missing. worker/invites-test.mjs asserts this copy and
   the shared one against the same table, so they cannot drift apart quietly.
   Exported for exactly that test. */
export function normalisePhone(raw) {
  const s = String(raw == null ? "" : raw).replace(/[\s().\-]/g, "");
  if (/^04\d{8}$/.test(s))    return "+61" + s.slice(1);
  if (/^\+614\d{8}$/.test(s)) return s;
  if (/^614\d{8}$/.test(s))   return "+" + s;
  return null;
}

/* The same key /staff is filed under: every dot to a comma, globally. */
const emailKey = (e) => String(e || "").trim().toLowerCase().replace(/\./g, ",");

/* editBookings as the app decides it: the permission matrix wins where it has
   an explicit boolean opinion, the shipped defaults stand otherwise, and the
   manager is never overridable. Mirrors can() in nala-shared.js for the one
   permission this Worker cares about. */
function maySend(role, permissions) {
  role = role === "staff" ? "admin" : role;      /* the pre-rename records */
  if (role === "admin") return true;
  const row = permissions && permissions.editBookings;
  if (row && typeof row[role] === "boolean") return row[role];
  return role === "waiter";
}

/* A URL a human can retype is a URL that goes out wrong to fourteen guests at
   once. The page refuses these too; this is the copy that cannot be edited
   out of a browser. */
const bodyHasUrl = (s) => /(https?:\/\/|www\.)/i.test(s || "");

async function dbGet(path, idToken) {
  const r = await fetch(DB + path + ".json?auth=" + encodeURIComponent(idToken));
  if (!r.ok) throw new Error("db read refused: " + path);
  return r.json();
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (request.method !== "POST") return reply(405, { error: "POST only" });

    let body;
    try { body = await request.json(); }
    catch { return reply(400, { error: "not JSON" }); }

    const { idToken, date, villas, template } = body || {};
    const text = body && body.body;

    if (!idToken) return reply(401, { error: "no idToken" });
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date || ""))
      return reply(400, { error: "bad date" });
    /* Tonight only. The Worker's clock is UTC and the resort's is not, so
       "today" is anywhere within a day of UTC today: wide enough for every
       Australian offset, narrow enough that a written-out past date is
       refused rather than sent for. */
    const asked = Date.parse(date + "T00:00:00Z");
    if (Math.abs(asked - Date.now()) > 36 * 60 * 60 * 1000)
      return reply(400, { error: "not tonight" });
    if (!Array.isArray(villas) || !villas.length || villas.length > 17 ||
        !villas.every((v) => /^\d{1,2}$/.test(String(v))))
      return reply(400, { error: "bad villa list" });
    if (typeof text !== "string" || !text.trim() || text.length > 500)
      return reply(400, { error: "bad message" });
    if (bodyHasUrl(text))
      return reply(400, { error: "the message contains a URL; the link is added here, not typed" });

    /* 1. Verify the token. accounts:lookup checks the signature, the expiry
       and the project (the key is per project), and names the account, which
       becomes the `by` on every record: who pressed send, from the token, not
       from anything the browser claimed. */
    const look = await fetch(
      "https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=" + env.FB_API_KEY,
      { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idToken }) });
    const who = await look.json().catch(() => null);
    const email = look.ok && who && who.users && who.users[0] && who.users[0].email;
    if (!email) return reply(401, { error: "sign in again" });

    /* 2. The role may send. Same permission as the page: editBookings. */
    let staffRec, permissions;
    try {
      staffRec = await dbGet("/staff/" + emailKey(email), idToken);
      permissions = await dbGet("/permissions", idToken).catch(() => null);
    } catch {
      return reply(403, { error: "could not read the staff record" });
    }
    const role = staffRec && staffRec.role;
    if (!maySend(role, permissions))
      return reply(403, { error: "this login may not send invitations" });

    /* Backstop on the menu. The page owns the real test, the same one the
       guest page uses; this only stops an edited browser sending links to a
       placeholder. A menu node with no fresh publish stamp refuses the lot. */
    const menu = await fetch(DB + "/menu.json").then((r) => r.json()).catch(() => null);
    const pub = menu && menu.published ? Date.parse(menu.published) : NaN;
    if (!(menu && menu.main && menu.main.name) || isNaN(pub) ||
        Date.now() - pub > 24 * 60 * 60 * 1000)
      return reply(409, { error: "no menu is published for tonight" });

    /* 3 to 6. Per villa: re-read, rebuild, send, record, report. The record
       is written whether the send succeeded or not, because "what did we
       actually say to that guest" is the question that gets asked when a
       guest is confused, and `body` holds the answer after any edit. */
    const results = {};
    for (const v of villas.map(String)) {
      const rec = { sentAt: new Date().toISOString(), template: template || "",
                    by: email, status: "failed", to: "", body: "", error: "" };
      try {
        const stay = await dbGet("/stays/" + date + "/" + v, idToken);
        await dbGet("/dinner/" + date + "/" + v, idToken).catch(() => null);
        if (!stay || typeof stay !== "object" || !stay.id)
          throw new Error("no booking in this villa tonight");
        const raw = String(stay.phone || "").trim();
        if (!raw) throw new Error("no phone number on the booking");
        const phone = normalisePhone(raw);
        if (!phone)
          throw new Error("number cannot be normalised for sending: " + raw);
        rec.to = phone;
        const link = inviteLink(stay.id, v);
        rec.body = text.includes("<link>")
          ? text.replace("<link>", link)
          : text.replace(/\s*$/, "") + "\n" + link;

        const send = await fetch(CLICKSEND, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": "Basic " + btoa(
              (env.CLICKSEND_USERNAME || "").trim() + ":" +
              (env.CLICKSEND_API_KEY || "").trim()),
          },
          body: JSON.stringify({ messages: [{
            from: (env.CLICKSEND_FROM || "").trim(),
            to: phone, body: rec.body, source: "nala-menu" }],
            /* The owner's call, 24 Aug, after the first live send: no
               ClickSend shortener. The guest sees menu.nalaresort.com in the
               message, not a click.sy redirect, at the price of a second
               segment (the Mews GUID makes the link about seventy
               characters). If a shortener ever returns it is ours, or the
               short token per booking that replaces inviteLink wholesale.
               menu.nalaresort.com must still be registered at
               dashboard.clicksend.com/sms/website-registration, or a message
               carrying the link will not send at all. */
            shorten_urls: false }),
        });
        const out = await send.json().catch(() => null);
        const msg = out && out.data && out.data.messages && out.data.messages[0];
        if (send.ok && msg && msg.status === "SUCCESS") {
          rec.status = "sent";
          rec.providerId = msg.message_id || "";
          /* Kept verbatim, under one key, rather than picked apart: version
             one shows none of it, and guessing today which field the click
             statistics will hang off is how it turns out to be the one field
             that was dropped. */
          if (msg.short_urls || msg.shortened_urls || msg.url)
            rec.shortened = msg.short_urls || msg.shortened_urls || msg.url;
        } else {
          throw new Error((msg && msg.status) ||
                          (out && out.response_msg) || "ClickSend refused");
        }
      } catch (e) {
        rec.error = String((e && e.message) || e);
      }
      /* Written with the caller's own token, so the rules apply to the write
         exactly as they would from the page. A record that cannot be written
         is itself reported rather than swallowed: a send with no record is
         the deletion-that-looked-published mistake in a new coat. */
      try {
        const w = await fetch(
          DB + "/invites/" + date + "/" + v + ".json?auth=" + encodeURIComponent(idToken),
          { method: "PUT", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(rec) });
        if (!w.ok) throw new Error("record refused");
      } catch {
        rec.error = (rec.error ? rec.error + "; " : "") + "the record did not save";
        if (rec.status === "sent") rec.status = "sent-unrecorded";
      }
      results[v] = { status: rec.status, error: rec.error || undefined };
    }
    return reply(200, { results });
  },
};
