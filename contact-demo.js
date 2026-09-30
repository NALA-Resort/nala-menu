/* Chat's demo: the real Chat and Tasks pages, with made-up
   guests, before Twilio exists. The owner, 29 Sep: "Maybe a demo
   environment is better?" - to try the whole flow without the live app.

   Entered as guest-contact.html?demo (or tasks.html?demo) and kept for the
   tab in sessionStorage, so moving between the two pages stays in it. In
   the demo NOTHING leaves the phone: there is no sign-in, the database is
   a copy held in the tab, the messenger is played here, and no guest can be
   reached. Leave demo forgets it all.

   Loaded by both pages after the Firebase scripts and before auth.js, so
   the demo's stand-ins are in place before anything signs in or reads. Off
   the demo it does nothing at all. */
(function(){
  var ON = 'nalaContactDemo', DBK = 'nalaContactDemoDB', WHOK = 'nalaContactDemoWho';
  var asked = /[?&]demo(=|&|$)/.test(location.search), on = asked;
  try {
    if (asked) sessionStorage.setItem(ON, '1');
    on = asked || sessionStorage.getItem(ON) === '1';
  } catch (e){}
  if (!on) return;
  window.NALA_DEMO = true;

  /* ── who is looking ─────────────────────────────────────────── */
  var PEOPLE = [
    { email:'desk@demo',  name:'Reception', role:'admin',        label:'Reception (sees everything)' },
    { email:'ray@demo',   name:'Ray',       role:'housekeeping', label:'Ray, Maintenance' },
    { email:'marco@demo', name:'Marco',     role:'chef',         label:'Marco, Kitchen' },
    { email:'freya@demo', name:'Freya',     role:'spa',          label:'Freya, Spa' },
    { email:'anna@demo',  name:'Anna',      role:'housekeeping', label:'Anna, Bar' }
  ];
  var WHO = PEOPLE[0];
  try {
    var w = sessionStorage.getItem(WHOK);
    PEOPLE.forEach(function(p){ if (p.email === w) WHO = p; });
  } catch (e){}

  /* ── the made-up resort, dated from today ───────────────────── */
  function day(n){
    var d = new Date(); d.setHours(12, 0, 0, 0); d.setDate(d.getDate() + n);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' +
           String(d.getDate()).padStart(2, '0');
  }
  function ago(mins){ return new Date(Date.now() - mins * 60000).toISOString(); }
  function seed(){
    /* Reply to guests switched on for housekeeping, as Settings would:
       Ray and Anna answer from their cards, Marco (a chef) only reads. */
    var t = { staff:{}, permissions:{ open:{ 'guest-contact':true, tasks:true },
                                      guestReply:{ housekeeping:true } },
              contactsettings:{ teams:{
                bar:{ members:{ 'anna@demo':true } }, kitchen:{ members:{ 'marco@demo':true } },
                housekeeping:{ members:{} }, maintenance:{ members:{ 'ray@demo':true } },
                spa:{ members:{ 'freya@demo':true } } } },
              stays:{}, contact:{}, contactmsgs:{}, contactnew:{}, tasks:{}, previnvites:{},
              invites:{}, spareminders:{}, spa:{},
              /* The Templates page's three sets, as its built-ins seed them
                 (templates.html), for Chat's Templates (30 Sep). */
              presmstemplates:{
                before:{ label:'Before you arrive', order:1, body:'Good afternoon. Ahead of your stay ' +
                  'with us, a few questions so everything is ready when you arrive. Nala Resort\n<form>' },
                nudge:{ label:'A gentle reminder', order:2, body:'A reminder, when you have a moment: a ' +
                  'few questions ahead of your stay, so everything is ready when you arrive. Nala Resort\n<form>' } },
              smstemplates:{
                ready:{ label:'Menu is ready', order:1, body:'Tonight\u2019s menu is ready. Nala Resort\n<menu>' },
                join:{ label:'Will you join us', order:2, body:'Good afternoon. Tonight\u2019s menu, and a ' +
                  'place to tell us if you will join us. Nala Resort\n<menu>' },
                reminder:{ label:'Reminder', order:3, body:'A reminder that we have not heard about dinner ' +
                  'tonight. The menu, and the link to answer, is below. Nala Resort\n<menu>' } },
              spasmstemplates:{
                remind:{ label:'Gentle reminder', order:1, body:'Hello <first>, a gentle reminder of your ' +
                  'booking with us:\n\n<booking>\n\nIf you need to change anything, just reply to this ' +
                  'message. Nala Resort' },
                short:{ label:'Short', order:2, body:'Hello <first>, a reminder of your booking:\n\n' +
                  '<booking>\n\nTo change it, just reply. Nala Resort' } },
              /* tonight's menu, published this afternoon, or just after
                 midnight when the demo is opened before three */
              menu:{ published:new Date(Math.max(new Date().setHours(0, 5, 0, 0), Date.now() - 3 * 3600000)).toISOString(),
                     bread:{ name:'Sourdough, cultured butter' }, entree:{ name:'Kingfish crudo' },
                     main:{ name:'Lamb shoulder, white beans' }, dessert:{ name:'Lemon tart' } } };
    PEOPLE.forEach(function(p){ t.staff[p.email] = { name:p.name, role:p.role }; });
    var BOOK = [
      ['b-sarah',  '7',  'Sarah', 'Whitfield', '+61412345678', -2, 3, 2],
      ['b-lucy',   '4',  'Lucy',  'Whitfield', '+61412345699', -2, 3, 2],
      ['b-priya',  '9',  'Priya', 'Sharma',    '+61411000009', -1, 4, 2],
      ['b-lea',    '12', 'Léa',   'Martin',    '+33612345678', -3, 2, 2],
      ['b-claire', '2',  'Claire','Donnelly',  '+61411000002', -4, 3, 2],
      ['b-nina',   '10', 'Nina',  'Brandt',    '+61400000088', -1, 2, 3],
      ['b-jonah',  '16', 'Jonah', 'Adeyemi',   '+61411000016',  0, 5, 2],
      ['b-hana',   '14', 'Hana',  'Sato',      '',             -2, 1, 1],
      ['b-james',  '5',  'James', 'Harrington','+61438220761',  4, 7, 2],
      ['b-robyn',  '11', 'Robyn', 'Carter',    '+61411000044', -6, -2, 2]
    ];
    BOOK.forEach(function(b){
      for (var n = b[5]; n < b[6]; n++){
        var k = day(n);
        (t.stays[k] = t.stays[k] || {})[b[1]] = { id:b[0], first:b[2], last:b[3], phone:b[4],
          arrive:day(b[5]), depart:day(b[6]), adults:b[7] };
      }
    });
    /* What the SMS pages sent (the owner, 30 Sep: "every outgoing and
       incoming message including dinner invitations and pre-arrival form"),
       as those pages' own records hold it: each guest's pre-arrival text
       five days out, and each night's dinner invitation at 4pm. */
    function at(n, h, m){ var d = new Date(); d.setDate(d.getDate() + n); d.setHours(h, m, 0, 0);
                          return d.toISOString(); }
    function tok(x){ for (var i = 0, v = 7; i < x.length; i++) v = (v * 31 + x.charCodeAt(i)) >>> 0;
                     return v.toString(36).slice(0, 6); }
    function sent(o){ return Object.assign({ status:'sent', by:'desk@demo', delivery:'delivered' }, o); }
    var LINK = 'https://menu.nalaresort.com/';
    BOOK.forEach(function(b){
      if (!b[4]) return;
      t.previnvites[b[0]] = sent({ sentAt:at(b[5] - 5, 15, 10), to:b[4], template:'before',
        body:'Good afternoon. Ahead of your stay with us, a few questions so everything is ready ' +
             'when you arrive. Nala Resort\n' + LINK + 'prearrival.html?t=' + tok(b[0]) });
      for (var n = b[5]; n < b[6] && Date.parse(at(n, 16, 2)) < Date.now(); n++)
        (t.invites[day(n)] = t.invites[day(n)] || {})[b[1]] = sent({ sentAt:at(n, 16, 2), to:b[4],
          body:'Good afternoon. Tonight\u2019s menu, and a place to tell us if you will join us. ' +
               'Nala Resort\n' + LINK + '?t=' + tok(b[0] + n) });
    });
    function thread(ck, o){ t.contact[ck] = Object.assign({ phone:'+' + ck }, o); }
    function msg(ck, id, o){ (t.contactmsgs[ck] = t.contactmsgs[ck] || {})[id] = o; }
    function fresh(ck, id){ (t.contactnew[ck] = t.contactnew[ck] || {})[id] = true; }
    function task(team, id, o){ (t.tasks[team] = t.tasks[team] || {})[id] = o; }

    /* Sarah, villa 7: a whole stay in one conversation */
    var S = '61412345678';
    msg(S, 'in-SMmassage', { dir:'in', ch:'wa', at:ago(3 * 1440 + 40),
      body:'Done! We arrive around 4pm. Could we book a couples massage for Sunday afternoon?',
      tasks:{ spa:'t0massage' }, sorted:{ by:'desk@demo', at:ago(3 * 1440 + 35) } });
    msg(S, 'odemo1', { dir:'out', ch:'wa', at:ago(3 * 1440 + 30), by:'desk@demo', kind:'staff',
      body:'Lovely, thank you Sarah. Sunday at 2pm is yours.', status:'read' });
    msg(S, 'in-SMthanks', { dir:'in', ch:'wa', at:ago(3 * 1440 + 28), body:'Thank you!',
      sorted:{ by:'desk@demo', at:ago(3 * 1440 + 20) } });
    msg(S, 'in-SMumbrella', { dir:'in', ch:'wa', at:ago(8),
      body:'The umbrella on our deck won’t close. Could someone take a look?',
      media:{ 0:{ url:'https://api.twilio.com/demo/umbrella', type:'image/svg+xml' } },
      tasks:{ maintenance:'t1umbrella' }, sorted:{ by:'desk@demo', at:ago(7) } });
    msg(S, 'odemo5', { dir:'out', ch:'wa', at:ago(7), by:'desk@demo', kind:'staff', status:'read',
      body:'So sorry about that! Ray from maintenance will be with you in ten minutes.' });
    msg(S, 'in-SMcandle', { dir:'in', ch:'wa', at:ago(6),
      body:'Also, it’s Tom’s 40th tonight! Any chance of a candle on his dessert?' });
    fresh(S, 'in-SMcandle');
    thread(S, { lastAt:ago(6), lastIn:ago(6), lastInCh:'wa', lastInWa:ago(6), dir:'in',
      preview:'Also, it’s Tom’s 40th tonight! Any chance of a candle on his dessert?',
      wa:{ on:true, by:'desk@demo', at:ago(7 * 1440) } });
    /* Her pre-arrival text went twice: the reminder is the record, and the
       first rides under earlier, as send-invites.js keeps it. */
    var first = t.previnvites['b-sarah'];
    t.previnvites['b-sarah'] = sent({ sentAt:at(-4, 9, 30), to:'+' + S, template:'nudge',
      body:'A reminder, when you have a moment: a few questions ahead of your stay, so everything ' +
           'is ready when you arrive. Nala Resort\n' + LINK + 'prearrival.html?t=' + tok('b-sarah'),
      earlier:[first] });
    /* the morning of her massage, and her answer to last night's menu,
       by SMS - which lands here once the everyday texts go by Twilio */
    t.spareminders['b-sarah'] = { t0massage: sent({ sentAt:at(-1, 8, 30), to:'+' + S,
      body:'Hello Sarah, a gentle reminder of your booking with us:\n\nCouples massage, 1 hour\n' +
           'Today at 2:00 pm\n\nIf you need to change anything, just reply to this message. Nala Resort' }) };
    msg(S, 'in-SMdinner', { dir:'in', ch:'sms', at:at(-1, 16, 14),
      body:'We\u2019d love to. Two of us at 7pm please!', sorted:{ by:'desk@demo', at:at(-1, 16, 20) } });
    task('spa', 't0massage', { ck:S, msg:'in-SMmassage', villa:'7', name:'Sarah Whitfield',
      text:'Could we book a couples massage for Sunday afternoon?', state:'done',
      at:ago(3 * 1440 + 35), by:'desk@demo', doneAt:ago(3 * 1440), doneBy:'freya@demo',
      doneDay:day(-3) });
    task('maintenance', 't1umbrella', { ck:S, msg:'in-SMumbrella', villa:'7', name:'Sarah Whitfield',
      text:'The umbrella on our deck won’t close. Could someone take a look?', state:'open',
      at:ago(7), by:'desk@demo' });

    /* Léa, villa 12, and a number on no booking: new, waiting to be sorted */
    var L = '33612345678';
    msg(L, 'in-SMpool', { dir:'in', ch:'wa', at:ago(33), body:'Bonjour! Is the pool heated?' });
    fresh(L, 'in-SMpool');
    thread(L, { lastAt:ago(33), lastIn:ago(33), lastInCh:'wa', lastInWa:ago(33), dir:'in',
      preview:'Bonjour! Is the pool heated?', profile:'Léa' });
    var U = '61423555019';
    msg(U, 'in-SMtable', { dir:'in', ch:'sms', at:ago(115),
      body:'Hi, is there a table for 4 at dinner tonight?' });
    fresh(U, 'in-SMtable');
    thread(U, { lastAt:ago(115), lastIn:ago(115), lastInCh:'sms', dir:'in',
      preview:'Hi, is there a table for 4 at dinner tonight?' });

    /* Priya, villa 9, and Nina, villa 10: sorted, a team's task open */
    var P = '61411000009';
    msg(P, 'in-SMgin', { dir:'in', ch:'wa', at:ago(15),
      body:'Could we get two gin and tonics at the pool?', tasks:{ bar:'t2gandt' },
      sorted:{ by:'desk@demo', at:ago(14) } });
    msg(P, 'odemo4', { dir:'out', ch:'wa', at:ago(13), by:'desk@demo', kind:'staff', status:'read',
      body:'Of course! Any gin you prefer, and where are you sitting?' });
    msg(P, 'in-SMgin2', { dir:'in', ch:'wa', at:ago(11),
      body:'Tanqueray with lime please. We\u2019re on the loungers by the pool steps.',
      sorted:{ by:'desk@demo', at:ago(10) } });
    thread(P, { lastAt:ago(11), lastIn:ago(11), lastInCh:'wa', lastInWa:ago(11), dir:'in',
      preview:'Tanqueray with lime please. We\u2019re on the loungers by the pool steps.' });
    /* her massage tomorrow morning, booked on the Spa board: Chat offers
       its reminder from Templates */
    t.spa['b-priya'] = { t7massage:{ status:'booked', day:day(1), time:'10:30', qty:1, dur:60,
                                     name:'Priya Sharma' } };
    task('bar', 't2gandt', { ck:P, msg:'in-SMgin', villa:'9', name:'Priya Sharma',
      text:'Could we get two gin and tonics at the pool?', state:'open', at:ago(14), by:'desk@demo',
      note:'Charge to villa 9', noteBy:'desk@demo', noteAt:ago(10) });
    var N = '61400000088';
    msg(N, 'in-SMcake', { dir:'in', ch:'sms', at:ago(5),
      body:'Could the kitchen do a gluten free birthday cake for tomorrow?',
      tasks:{ kitchen:'t5cake' }, sorted:{ by:'desk@demo', at:ago(4) } });
    thread(N, { lastAt:ago(5), lastIn:ago(5), lastInCh:'sms', dir:'in',
      preview:'Could the kitchen do a gluten free birthday cake for tomorrow?' });
    task('kitchen', 't5cake', { ck:N, msg:'in-SMcake', villa:'10', name:'Nina Brandt',
      text:'Could the kitchen do a gluten free birthday cake for tomorrow?', state:'open',
      at:ago(4), by:'desk@demo' });

    /* Lucy, villa 4: only we have written. Claire, villa 2: all done. */
    var Y = '61412345699';
    msg(Y, 'odemo2', { dir:'out', ch:'sms', at:ago(20), by:'desk@demo', kind:'staff', status:'delivered',
      body:'Good afternoon Lucy. Your late checkout is confirmed for 1pm on the day you leave.' });
    thread(Y, { lastAt:ago(20), lastOut:ago(20), dir:'out',
      preview:'Good afternoon Lucy. Your late checkout is confirmed for 1pm on the day you leave.' });
    var C = '61411000002';
    msg(C, 'in-SMtowels', { dir:'in', ch:'sms', at:ago(1440 + 60), body:'Could we get some fresh towels?',
      tasks:{ housekeeping:'t3towels' }, sorted:{ by:'desk@demo', at:ago(1440 + 55) } });
    msg(C, 'in-SMthanks2', { dir:'in', ch:'sms', at:ago(1440), body:'Perfect, thank you so much!',
      sorted:{ by:'desk@demo', at:ago(1440 - 5) } });
    thread(C, { lastAt:ago(1440), lastIn:ago(1440), lastInCh:'sms', dir:'in',
      preview:'Perfect, thank you so much!' });
    task('housekeeping', 't3towels', { ck:C, msg:'in-SMtowels', villa:'2', name:'Claire Donnelly',
      text:'Could we get some fresh towels?', state:'done', at:ago(1440 + 55), by:'desk@demo',
      doneAt:ago(1440 + 20), doneBy:'desk@demo', doneDay:day(-1) });

    /* James, villa 5, arriving in four days: asked for WhatsApp, and last
       wrote six days ago - past WhatsApp's 24 hours, so approved words only. */
    var J = '61438220761';
    msg(J, 'in-SMparking', { dir:'in', ch:'wa', at:ago(6 * 1440),
      body:'Looking forward to it! Is there parking for two cars?',
      sorted:{ by:'desk@demo', at:ago(6 * 1440 - 10) } });
    msg(J, 'odemo3', { dir:'out', ch:'wa', at:ago(6 * 1440 - 12), by:'desk@demo', kind:'staff',
      body:'Yes, two spaces beside villa 5. See you soon!', status:'read' });
    thread(J, { lastAt:ago(6 * 1440 - 12), lastIn:ago(6 * 1440), lastInCh:'wa',
      lastInWa:ago(6 * 1440), lastOut:ago(6 * 1440 - 12), dir:'out',
      preview:'Yes, two spaces beside villa 5. See you soon!',
      wa:{ on:true, by:'desk@demo', at:ago(6 * 1440) } });
    t.demoSeed = SEED;
    return t;
  }

  /* ── the tab's copy of the database ─────────────────────────── */
  var SEED = 5;   /* moved when the made-up guests change: a tab holding older ones starts again */
  var TREE = null;
  try { TREE = JSON.parse(sessionStorage.getItem(DBK) || 'null'); } catch (e){}
  if (!TREE || TREE.demoSeed !== SEED){ TREE = seed(); save(); }
  function save(){ try { sessionStorage.setItem(DBK, JSON.stringify(TREE)); } catch (e){} }
  function parts(p){ return String(p).split('/').filter(Boolean); }
  function get(p){
    var n = TREE;
    parts(p).forEach(function(k){ n = (n && typeof n === 'object') ? n[k] : undefined; });
    return n === undefined ? null : n;
  }
  function set(p, v){
    var ks = parts(p);
    if (!ks.length){ TREE = v || {}; return; }
    var n = TREE;
    for (var i = 0; i < ks.length - 1; i++){
      if (!n[ks[i]] || typeof n[ks[i]] !== 'object'){
        if (v === null) return;
        n[ks[i]] = {};
      }
      n = n[ks[i]];
    }
    if (v === null) delete n[ks[ks.length - 1]];
    else n[ks[ks.length - 1]] = JSON.parse(JSON.stringify(v));
    prune();
  }
  function update(p, o){ Object.keys(o || {}).forEach(function(k){ set(p + '/' + k, o[k]); }); }
  /* The database keeps no empty node, so neither does this. */
  function prune(){
    (function walk(n){
      Object.keys(n).forEach(function(k){
        if (n[k] && typeof n[k] === 'object'){
          walk(n[k]);
          if (!Object.keys(n[k]).length) delete n[k];
        }
      });
    })(TREE);
  }
  /* A read with the database's query words: shallow, orderBy a child or the
     key, startAt, endAt, equalTo - the ones these two pages ask. */
  function query(node, q){
    if (!node || typeof node !== 'object') return node;
    if (q.get('shallow') === 'true'){
      var s = {}; Object.keys(node).forEach(function(k){ s[k] = true; }); return s;
    }
    if (!q.get('orderBy')) return node;
    var ob = JSON.parse(q.get('orderBy')), out = {};
    var J = function(x){ return q.has(x) ? JSON.parse(q.get(x)) : undefined; };
    var sa = J('startAt'), ea = J('endAt'), eq = J('equalTo');
    Object.keys(node).forEach(function(k){
      var v = ob === '$key' ? k : (node[k] && typeof node[k] === 'object' ? node[k][ob] : undefined);
      if (eq !== undefined && v !== eq) return;
      if (sa !== undefined && !(v != null && v >= sa)) return;
      if (ea !== undefined && !(v != null && v <= ea)) return;
      out[k] = node[k];
    });
    return Object.keys(out).length ? out : null;
  }
  function answer(status, body){
    return Promise.resolve(new Response(JSON.stringify(body === undefined ? null : body),
      { status:status, headers:{ 'Content-Type':'application/json' } }));
  }
  function database(u, o){
    var rest = u.split('firebasedatabase.app')[1] || '/';
    var path = rest.split('?')[0].replace(/\.json$/, '');
    var q = new URLSearchParams(rest.split('?')[1] || '');
    var m = ((o && o.method) || 'GET').toUpperCase();
    var body = o && o.body != null ? JSON.parse(o.body) : null;
    if (m === 'GET') return answer(200, query(get(path), q));
    if (m === 'PUT') set(path, body);
    else if (m === 'PATCH'){
      /* at the root, each key is a path: the page's one-write sort */
      if (!parts(path).length) Object.keys(body || {}).forEach(function(k){ set(k, body[k]); });
      else update(path, body);
    } else if (m === 'DELETE') set(path, null);
    save();
    return answer(200, body);
  }

  /* ── the messenger, played here ──────────────────────────────── */
  function bookingOf(ck){
    var stays = TREE.stays || {}, best = null;
    Object.keys(stays).forEach(function(d){
      Object.keys(stays[d]).forEach(function(v){
        var s = stays[d][v];
        if (s && contactKey(s.phone) === ck) best = s;
      });
    });
    return best;
  }
  var UMBRELLA = '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="420" viewBox="0 0 420 420">' +
    '<rect width="420" height="420" fill="#C9C3B7"/><rect y="300" width="420" height="120" fill="#B5AE9F"/>' +
    '<path d="M60 210 Q210 60 360 210 Z" fill="#F9F7F4" stroke="#8A8375" stroke-width="4"/>' +
    '<line x1="210" y1="130" x2="250" y2="330" stroke="#6F695E" stroke-width="8"/>' +
    '<text x="210" y="395" font-family="sans-serif" font-size="22" text-anchor="middle" fill="#4D493F">' +
    'A demo photo</text></svg>';
  function messenger(o){
    var b = {};
    try { b = JSON.parse((o && o.body) || '{}'); } catch (e){}
    if (b.kind === 'hello') return answer(200, { test:false, wa:true, buzz:false, ready:true });
    /* The setup check (30 Sep): the demo's is all working, so Chat shows none. */
    if (b.kind === 'check') return answer(200, { check:[
      { key:'twilio', ok:true, say:'Twilio accepts the Account SID and the Auth Token.' },
      { key:'webhook', ok:true, say:'Twilio hands the number\u2019s texts to Chat.' },
      { key:'login', ok:true, say:'The Chat Worker signs in.' },
      { key:'test', ok:null, say:'Test mode is off: Chat can message any guest.' } ] });
    if (b.kind === 'media')
      return Promise.resolve(new Response(new Blob([UMBRELLA], { type:'image/svg+xml' }),
        { status:200, headers:{ 'Content-Type':'image/svg+xml' } }));
    if (b.kind === 'tasklog' || b.kind === 'taskmedia'){
      /* As the Worker's door: a team's task, from its request until Done,
         for the desk or a login on that team. */
      var excerpt = function(team, id){
        var set = ((TREE.contactsettings || {}).teams || {})[team] || {};
        var member = !!(set.members && set.members[WHO.email] === true);
        if (!can(WHO.role, 'editBookings') && !member) return null;
        var task = get('/tasks/' + team + '/' + id); if (!task) return null;
        var msgs = get('/contactmsgs/' + task.ck) || {}, src = msgs[task.msg];
        var from = Date.parse((src && src.at) || task.at) || 0;
        var until = task.state === 'done' && task.doneAt ? Date.parse(task.doneAt) : Infinity;
        var ids = Object.keys(msgs).filter(function(k){
          var a = Date.parse(msgs[k].at), m = msgs[k];
          var theirs = m.dir === 'in' && m.tasks && Object.keys(m.tasks).length && !m.tasks[team];
          return a >= from && a <= until && !theirs;
        }).sort(function(x, y){ return Date.parse(msgs[x].at) - Date.parse(msgs[y].at); });
        return { msgs:msgs, ids:ids, task:task };
      };
      if (b.kind === 'tasklog'){
        var logs = {}, routes = {};
        (b.tasks || []).forEach(function(it){
          var x = excerpt(String(it.team), String(it.t)); if (!x) return;
          if (can(WHO.role, 'guestReply') && x.task.state === 'open')
            routes[it.team + '/' + it.t] = contactChannel(get('/contact/' + x.task.ck) || {}, Date.now());
          logs[it.team + '/' + it.t] = x.ids.map(function(k){
            var m = x.msgs[k];
            return { id:k, dir:m.dir, ch:m.ch, body:m.body || '', at:m.at,
                     by:m.dir === 'out' ? (m.by || '') : '', photos:m.media ? Object.keys(m.media).length : 0 };
          });
        });
        return answer(200, { logs:logs, routes:routes });
      }
      var tx = excerpt(String(b.team), String(b.t));
      if (!tx) return answer(403, { error:'not one of this login\u2019s tasks' });
      if (tx.ids.indexOf(String(b.m)) < 0 || !tx.msgs[b.m].media) return answer(404, { error:'no such photo' });
      return Promise.resolve(new Response(new Blob([UMBRELLA], { type:'image/svg+xml' }),
        { status:200, headers:{ 'Content-Type':'image/svg+xml' } }));
    }
    /* Delete (30 Sep): the admin's, as the Worker does it - the message and
       its New mark go, and the thread is re-read from what is left. */
    if (b.kind === 'delete'){
      if (normaliseRole(WHO.role) !== 'admin') return answer(403, { error:'Only the admin may delete a message' });
      var dk = String(b.ck || ''), dm = String(b.m || '');
      if (!get('/contactmsgs/' + dk + '/' + dm)) return answer(404, { error:'That message is not there' });
      set('/contactmsgs/' + dk + '/' + dm, null); set('/contactnew/' + dk + '/' + dm, null);
      var left = get('/contactmsgs/' + dk) || {}, all = Object.keys(left).map(function(k){ return left[k]; })
        .sort(function(x, y){ return Date.parse(x.at) - Date.parse(y.at); });
      var last = all[all.length - 1], ins = all.filter(function(x){ return x.dir === 'in'; });
      var lin = ins[ins.length - 1], lwa = ins.filter(function(x){ return x.ch === 'wa'; }).pop();
      var lout = all.filter(function(x){ return x.dir === 'out'; }).pop();
      update('/contact/' + dk, { lastAt: last ? last.at : null, dir: last ? last.dir : null,
        preview: last ? String(last.body || (last.media ? 'Photo' : '')).replace(/\s+/g, ' ').slice(0, 120) : null,
        lastIn: lin ? lin.at : null, lastInCh: lin ? lin.ch : null, lastInWa: lwa ? lwa.at : null,
        lastOut: lout ? lout.at : null });
      save();
      return answer(200, { deleted: dm });
    }
    if (b.kind !== 'send') return answer(400, { error:'unknown kind' });
    /* As the Worker: a reply only from a role Settings lets reply, and a
       login that is not the desk only to the guest of its own open task. */
    if (!can(WHO.role, 'guestReply'))
      return answer(403, { error:'Replying to guests is switched off for this login. An admin can ' +
                                 'switch it on in Settings, General, Roles.' });
    var ck = String(b.ck || '');
    if (!can(WHO.role, 'editBookings')){
      var mine = (((TREE.contactsettings || {}).teams || {})[b.team] || {}).members || {};
      var tk = mine[WHO.email] === true && get('/tasks/' + b.team + '/' + b.t);
      if (!tk || tk.state !== 'open') return answer(403, { error:'That is not an open task of this login\u2019s teams' });
      if (b.template) return answer(400, { error:'An approved message goes from Chat' });
      ck = String(tk.ck);
    }
    var t = get('/contact/' + ck) || {};
    if (t.optout) return answer(409, { error:'This guest texted STOP. Nothing can be sent until they text START.' });
    var route = contactChannel(t, Date.now()).ch, ch, text;
    if (b.template){
      if (!waAgreed(t)) return answer(409, { error:'This guest has not asked for WhatsApp: send an SMS instead' });
      var bk = bookingOf(ck) || {};
      text = contactTemplateText(b.template, bk.first, bk.arrive); ch = 'wa';
    } else {
      text = String(b.text || '').trim();
      if (!text) return answer(400, { error:'bad message' });
      if (b.via === 'sms') ch = 'sms';
      else if (route === 'watpl')
        return answer(409, { window:'closed', error:'More than 24 hours since this guest last wrote ' +
          'on WhatsApp: choose an approved message, or send an SMS' });
      else ch = route === 'wa' ? 'wa' : 'sms';
    }
    var id = 'odemo' + Date.now().toString(36), at = new Date().toISOString();
    var rec = { dir:'out', ch:ch, body:text, at:at, by:WHO.email,
                kind:b.template ? 'template' : 'staff', status:'sent' };
    if (b.template) rec.tpl = b.template;
    set('/contactmsgs/' + ck + '/' + id, rec);
    update('/contact/' + ck, { phone:'+' + ck, lastAt:at, lastOut:at, dir:'out',
                               preview:text.replace(/\s+/g, ' ').slice(0, 120) });
    save();
    /* the handset's receipts, as they would come */
    setTimeout(function(){ set('/contactmsgs/' + ck + '/' + id + '/status', 'delivered'); save(); }, 3000);
    if (ch === 'wa') setTimeout(function(){ set('/contactmsgs/' + ck + '/' + id + '/status', 'read'); save(); }, 9000);
    return answer(200, { id:id, ch:ch, status:'sent', test:false });
  }

  /* The SMS pages' sender (worker/send-invites.js), played here for Chat's
     Templates (30 Sep): the form, tonight's menu and a spa reminder, each
     recorded where its own page reads it, the text before kept under
     earlier as the Worker keeps it. */
  function sender(o){
    var b = {};
    try { b = JSON.parse((o && o.body) || '{}'); } catch (e){}
    if (!can(WHO.role, 'editBookings')) return answer(403, { error:'this login may not send invitations' });
    var text = String(b.body || '');
    if (!text.trim()) return answer(400, { error:'bad message' });
    var results = {}, now = new Date().toISOString();
    function tok(){ return Math.random().toString(36).slice(2, 8); }
    function record(path, rec){
      var prev = get(path);
      if (prev && prev.sentAt && prev.status === 'sent'){
        var was = Object.assign({}, prev); delete was.earlier;
        var older = prev.earlier ? Object.keys(prev.earlier).map(function(k){ return prev.earlier[k]; }) : [];
        rec.earlier = [was].concat(older).slice(0, 5);
      }
      set(path, rec);
      setTimeout(function(){ set(path + '/delivery', 'delivered'); save(); }, 3000);
    }
    function one(key, path, stay, bodyText, extra){
      var phone = normalisePhone((stay && stay.phone) || '');
      if (!phone){ results[key] = { status:'failed', error:'no phone number on the booking' }; return; }
      record(path, Object.assign({ sentAt:now, template:b.template || '', by:WHO.email, status:'sent',
                                   to:phone, body:bodyText, error:'' }, extra || {}));
      results[key] = { status:'sent' };
    }
    function stayOf(id){
      var stays = TREE.stays || {}, found = null;
      Object.keys(stays).forEach(function(d){ Object.keys(stays[d]).forEach(function(v){
        if (stays[d][v] && stays[d][v].id === id) found = stays[d][v]; }); });
      return found;
    }
    var fill = function(link){
      return /<(form|menu|link)>/.test(text) ? text.replace(/<(form|menu|link)>/, link) : text + '\n' + link;
    };
    if (b.kind === 'pre'){
      (b.bookings || []).forEach(function(id){
        var st = stayOf(id);
        if (!st){ results[id] = { status:'failed', error:'no such booking in Mews' }; return; }
        one(id, '/previnvites/' + id, st, fill('https://menu.nalaresort.com/prearrival.html?t=' + tok()),
            { arrive:st.arrive });
      });
    } else if (b.kind === 'spa'){
      (b.treatments || []).forEach(function(tr){
        var key = tr.b + '/' + tr.t, rec = get('/spa/' + tr.b + '/' + tr.t), st = stayOf(tr.b);
        if (!rec || rec.status !== 'booked'){ results[key] = { status:'failed', error:'not a booked treatment' }; return; }
        var prev = get('/spareminders/' + tr.b + '/' + tr.t);
        one(key, '/spareminders/' + tr.b + '/' + tr.t, st, spaReminderText(text, st && st.first, rec, prev),
            { day:rec.day, time:rec.time || '', qty:rec.qty === 2 ? 2 : 1, dur:+rec.dur || 0 });
      });
    } else if (b.kind == null){
      var m = get('/menu');
      if (!menuLive(m)) return answer(409, { error:'no menu is published for tonight' });
      (b.villas || []).forEach(function(v){
        var st = ((TREE.stays || {})[b.date] || {})[v];
        if (!st){ results[v] = { status:'failed', error:'no booking in this villa tonight' }; return; }
        one(String(v), '/invites/' + b.date + '/' + v, st, fill('https://menu.nalaresort.com/?t=' + tok()));
      });
    } else return answer(400, { error:'not in the demo' });
    save();
    return answer(200, { results:results });
  }

  /* A guest writing in, as the Worker files it when Twilio hands it over. */
  function arrive(ck, ch, text){
    var at = new Date().toISOString(), id = 'in-SMdemo' + Date.now().toString(36);
    set('/contactmsgs/' + ck + '/' + id, { dir:'in', ch:ch, body:text, at:at });
    set('/contactnew/' + ck + '/' + id, true);
    var o = { phone:'+' + ck, lastAt:at, lastIn:at, lastInCh:ch, dir:'in',
              preview:text.replace(/\s+/g, ' ').slice(0, 120) };
    if (ch === 'wa'){ o.lastInWa = at; o.waBad = null; }
    update('/contact/' + ck, o);
    save();
  }

  /* ── nothing leaves: the database and the messengers are answered here ── */
  var realFetch = window.fetch;
  window.fetch = function(u, o){
    var s = String(u && u.url ? u.url : u);
    if (s.indexOf('firebasedatabase.app') > -1) return database(s, o);
    if (s.indexOf('nala-contact.') > -1) return messenger(o);
    if (s.indexOf('nala-invites.') > -1) return sender(o);
    if (s.indexOf('workers.dev') > -1) return answer(200, {});
    return realFetch.apply(this, arguments);
  };

  /* A signed-in stand-in for Firebase: auth.js settles on it, and the pages
     read WHO as the login. The demo's pages send a login who may not open
     one to the other, not to a board outside the demo. */
  function signedIn(cb, withToken){
    setTimeout(function(){
      if (typeof homeFor === 'function')
        window.homeFor = function(role){ return can(role, 'editBookings') ? 'guest-contact.html' : 'tasks.html'; };
      var u = { email:WHO.email };
      if (withToken) u.getIdToken = function(){ return Promise.resolve('demo'); };
      cb(u);
    }, 10);
  }
  var AUTH = {
    onIdTokenChanged:function(cb){ signedIn(cb, true); return function(){}; },
    onAuthStateChanged:function(cb){ signedIn(cb, false); return function(){}; },
    signOut:function(){ return Promise.resolve(); },
    setPersistence:function(){ return Promise.resolve(); },
    signInWithEmailAndPassword:function(){ return Promise.reject(new Error('demo')); }
  };
  window.firebase = { apps:[1], initializeApp:function(){}, app:function(){ return {}; },
                      auth:function(){ return AUTH; } };
  window.firebase.auth.Auth = { Persistence:{ LOCAL:'local', SESSION:'session', NONE:'none' } };

  /* ── the demo's bar ─────────────────────────────────────────── */
  var LINES = ['Could we get more towels please?', 'The air-con in the bedroom isn’t working.',
               'Could we book a table for dinner tonight at 7?', 'Two glasses of champagne to the deck please!',
               'What time is checkout?', 'Is there a spare phone charger at reception?'];
  function esc(t){
    return String(t == null ? '' : t).replace(/[&<>"']/g, function(c){
      return { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]; });
  }
  function guests(){
    var seen = {}, out = [], stays = TREE.stays || {};
    Object.keys(stays).sort().forEach(function(d){
      Object.keys(stays[d]).forEach(function(v){
        var s = stays[d][v], ck = s && contactKey(s.phone);
        if (!ck || seen[ck]) return;
        seen[ck] = true;
        out.push({ ck:ck, label:'Villa ' + v + ' · ' + s.first + ' ' + s.last });
      });
    });
    out.sort(function(a, b){ return a.label.localeCompare(b.label, undefined, { numeric:true }); });
    out.push({ ck:'61499000123', label:'A number on no booking' });
    return out;
  }
  function say(t){
    var n = document.getElementById('demoSay'); if (!n) return;
    n.textContent = t; clearTimeout(say.t);
    say.t = setTimeout(function(){ n.textContent = ''; }, 4000);
  }
  function redraw(){
    if (typeof window.refresh === 'function') window.refresh();
    else if (typeof window.load === 'function') window.load();
  }
  function bar(){
    var css = document.createElement('style');
    css.textContent =
      '#demoBar{margin:0 0 14px;padding:10px 12px;border-radius:8px;background:var(--amber,#F6EAD5);' +
      'border:1px solid var(--amberb,#C29A55);color:#8A6A2F;font-size:var(--t2,14px);line-height:1.45}' +
      '#demoBar b{font-weight:600}#demoBar .row{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}' +
      '#demoBar button,#demoBar select,#demoBar input{font:inherit;font-size:var(--t2,14px);' +
      'min-height:40px;border-radius:8px;border:1px solid var(--amberb,#C29A55);background:#fff;' +
      'color:#1C1C1A;padding:0 10px;max-width:100%}' +
      '#demoBar .full{flex:1 1 100%}#demoBar #demoWrite{display:none}' +
      /* the menu holds the demo's two pages and nothing that would leave it */
      '#navDrop a:not([href^="guest-contact.html"]):not([href^="tasks.html"]),' +
      '#navDrop .navgroup{display:none!important}' +
      '#demoBar #demoWrite.on{display:flex}#demoSay{min-height:1em;margin-top:6px}';
    document.head.appendChild(css);
    var d = document.createElement('div');
    d.id = 'demoBar';
    d.innerHTML =
      '<b>Demo:</b> made-up guests. Nothing here reaches the live app or a guest.' +
      '<div class="row"><button id="demoGuest" type="button">A guest writes</button>' +
      '<select id="demoWho" aria-label="Look as">' + PEOPLE.map(function(p){
        return '<option value="' + p.email + '"' + (p === WHO ? ' selected' : '') + '>' +
               esc(p.label) + '</option>'; }).join('') + '</select>' +
      '<button id="demoReset" type="button">Start again</button>' +
      '<button id="demoLeave" type="button">Leave demo</button></div>' +
      '<div class="row" id="demoWrite"><select id="demoFrom" class="full" aria-label="Which guest">' +
      guests().map(function(g){ return '<option value="' + g.ck + '">' + esc(g.label) + '</option>'; }).join('') +
      '</select><select id="demoCh" aria-label="How they write"><option value="wa">on WhatsApp</option>' +
      '<option value="sms">by SMS</option></select>' +
      '<input id="demoText" class="full" aria-label="What they write">' +
      '<button id="demoSend" type="button">It arrives</button></div><div id="demoSay"></div>';
    var wrap = document.querySelector('.wrap') || document.body;
    wrap.insertBefore(d, wrap.firstChild);
    var n = 0;
    document.getElementById('demoGuest').onclick = function(){
      var w = document.getElementById('demoWrite');
      w.classList.toggle('on');
      if (w.classList.contains('on')) document.getElementById('demoText').value = LINES[n++ % LINES.length];
    };
    document.getElementById('demoSend').onclick = function(){
      var ck = document.getElementById('demoFrom').value, text = document.getElementById('demoText').value.trim();
      if (!text) return say('Write something for them to send.');
      arrive(ck, document.getElementById('demoCh').value, text);
      document.getElementById('demoText').value = LINES[n++ % LINES.length];
      say('It has arrived: New, waiting to be sorted.');
      redraw();
    };
    document.getElementById('demoWho').onchange = function(){
      try { sessionStorage.setItem(WHOK, this.value); } catch (e){}
      var p = PEOPLE.filter(function(x){ return x.email === this.value; }, this)[0];
      location.href = (p && p.role === 'admin') ? 'guest-contact.html' : 'tasks.html';
    };
    document.getElementById('demoReset').onclick = function(){
      TREE = seed(); save(); say('Started again.'); redraw();
    };
    document.getElementById('demoLeave').onclick = function(){
      try { [ON, DBK, WHOK].forEach(function(k){ sessionStorage.removeItem(k); }); } catch (e){}
      location.href = 'pages.html';
    };
  }
  /* Only these two pages are in the demo: a link anywhere else would leave
     it for the live app, so it is stopped and said. */
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a[href]'); if (!a) return;
    var h = (a.getAttribute('href') || '').split('?')[0].split('#')[0];
    if (!h || h === 'guest-contact.html' || h === 'tasks.html') return;
    e.preventDefault(); e.stopPropagation();
    say('Only Chat and Tasks are in the demo.');
  }, true);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bar);
  else bar();
})();
