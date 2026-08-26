/* What the phone actually shows for each payload the push Worker sends.
 *
 * The Worker composes the payload and is not in this repo, so this loads the
 * real sw.js and throws known payload shapes at it. The shape that matters
 * was read off a real lock screen, 26 Aug: title "Nala Villas", the villa and
 * event in the body. iOS then adds "from Nala Villas" itself, so the bold
 * line said the app's name twice and the fact was in the small print.
 *
 * The promotion rule under test: a payload whose title is missing or is just
 * a name for the app hands the headline to the body. A payload with a real
 * title keeps it, which is how the Worker takes this job back the day it
 * learns to send one.
 *
 *     node tests/sw_test.js
 */
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'sw.js'), 'utf8');

/* The service worker global scope, reduced to what sw.js touches. Handlers
   land in `handlers`, banners land in `shown`, and each case boots a fresh
   copy so nothing leaks between them. */
function boot() {
  const handlers = {};
  const shown = [];
  const self = {
    addEventListener: function (name, fn) { handlers[name] = fn; },
    skipWaiting: function () {},
    clients: {
      claim: function () {},
      matchAll: function () { return Promise.resolve([]); },
      openWindow: function () { return Promise.resolve(); }
    },
    registration: {
      showNotification: function (title, opts) {
        shown.push({ title: title, opts: opts });
        return Promise.resolve();
      }
    }
  };
  new Function('self', src)(self);
  return { handlers: handlers, shown: shown };
}

/* Dispatch one push. `payload` is what event.data.json() returns; PARSE_FAIL
   makes it throw, the way a non JSON push does; undefined is a push with no
   data at all. */
const PARSE_FAIL = {};
function push(payload) {
  const env = boot();
  env.handlers.push({
    data: payload === undefined ? null : {
      json: function () {
        if (payload === PARSE_FAIL) throw new Error('bad json');
        return payload;
      }
    },
    waitUntil: function () {}
  });
  return env.shown[0];
}

let P = 0, F = 0;
function ck(name, cond) {
  console.log((cond ? 'PASS ' : 'FAIL ') + name);
  cond ? P++ : F++;
}

/* The Worker's shape as observed. The fact must be the headline. */
let n = push({ title: 'Nala Villas', body: 'Villa 9 - possibly available', tag: 'v9' });
ck('the app-name title hands the headline to the body',
   n.title === 'Villa 9 - possibly available');
ck('and the body does not repeat it underneath', !n.opts.body);
ck('the tag survives the promotion', n.opts.tag === 'v9');

n = push({ body: 'Villa 11 - cleaned' });
ck('a payload with no title at all promotes the body too',
   n.title === 'Villa 11 - cleaned');

n = push({ title: 'Nala', body: 'Villa 3 - departed' });
ck('the old fallback name is promoted past as well',
   n.title === 'Villa 3 - departed');

/* A real title is the Worker doing this job itself. Leave it alone. */
n = push({ title: 'Villa 9 - cleaned', body: 'by Maria, 10:20' });
ck('a payload with a real title keeps it', n.title === 'Villa 9 - cleaned');
ck('and keeps its body', n.opts.body === 'by Maria, 10:20');

/* iOS shows every push, so a broken payload must still put something
   sensible on screen rather than an empty banner. */
n = push(PARSE_FAIL);
ck('a payload that fails to parse still shows the fallback',
   n.title === 'Nala' && n.opts.body === 'A villa has changed.');

n = push(undefined);
ck('a push with no data at all still shows the fallback',
   n.title === 'Nala' && n.opts.body === 'A villa has changed.');

n = push({ title: 'Nala Villas' });
ck('an app-name title with no body falls back rather than going blank',
   n.title === 'Nala Villas' && n.opts.body === 'A villa has changed.');

/* The defaults the boards rely on, pinned so the promotion cannot cost them. */
n = push({ body: 'Villa 2 - serviced' });
ck('an untagged banner still collapses under the shared tag', n.opts.tag === 'nala');
ck('tapping still lands on the Cleans board by default',
   n.opts.data && n.opts.data.url === '/cleaners.html');

console.log('RESULT: ' + P + ' passed, ' + F + ' failed');
process.exit(F ? 1 : 0);
