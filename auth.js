/* Nala staff sign-in layer.
   Include AFTER firebase-app-compat.js and firebase-auth-compat.js,
   BEFORE the page's own script. It:
   1. queues every Realtime Database fetch until a staff login exists,
   2. appends the login token to every database request,
   3. shows a full-screen sign-in when logged out.                     */
(function(){
  var CFG = {
    apiKey: "AIzaSyA0zAzL-zfPivrIRhY_ip8BABjuYVMlzqI",
    authDomain: "nala-menu.firebaseapp.com",
    databaseURL: "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app",
    projectId: "nala-menu",
    storageBucket: "nala-menu.firebasestorage.app",
    messagingSenderId: "1079369772100",
    appId: "1:1079369772100:web:56be2a37c04e49a7a6e011"
  };

  window.__idToken = null;
  var settled = false;      // becomes true once signed in with a token
  var pending = [];         // queued database fetches while logged out

  var _fetch = window.fetch;
  function realFetch(u, o){
    if (window.__idToken){
      u += (u.indexOf('?') > -1 ? '&' : '?') + 'auth=' + window.__idToken;
    }
    return _fetch.call(window, u, o);
  }
  window.fetch = function(u, o){
    if (typeof u === 'string' && u.indexOf('firebasedatabase.app') > -1){
      if (!settled){
        return new Promise(function(res){ pending.push(function(){ res(realFetch(u, o)); }); });
      }
      return realFetch(u, o);
    }
    return _fetch.call(this, u, o);
  };
  function flush(){ var q = pending; pending = []; q.forEach(function(f){ try{ f(); }catch(e){} }); }

  /* ── sign-in helpers ─────────────────────────────────── */
  var SDK_URLS = ['https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js',
                  'https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js'];
  function canSignIn(){
    try { return typeof firebase !== 'undefined' && typeof firebase.auth === 'function'
                 && typeof firebase.auth().signInWithEmailAndPassword === 'function'; }
    catch (e){ return false; }
  }
  function loadScript(url, cb){
    var t = document.createElement('script');
    t.src = url; t.async = false;
    t.onload = function(){ cb(); }; t.onerror = function(){ cb(); };
    (document.head || document.documentElement).appendChild(t);
  }
  function recoverSDK(done){
    var i = 0, finished = false;
    var bail = setTimeout(function(){ if (!finished){ finished = true; done(); } }, 8000);
    (function next(){
      if (i >= SDK_URLS.length){
        try { firebase.initializeApp(CFG); } catch (e){ /* already initialised */ }
        if (!finished){ finished = true; clearTimeout(bail); done(); }
        return;
      }
      loadScript(SDK_URLS[i++] + '?r=' + Date.now(), next);
    })();
  }
  function trySignIn(e, p, btn, err, fail){
    var pr;
    try { pr = firebase.auth().signInWithEmailAndPassword(e, p); }
    catch (ex){ fail('Could not start sign-in - reload the page.'); return; }
    if (!pr || !pr.then){ fail('Could not start sign-in - reload the page.'); return; }
    pr.then(function(){ btn.disabled = false; })
      .catch(function(ex){
        var c = (ex && ex.code) || '';
        fail(
          c.indexOf('network') > -1 ? 'No connection - try again.' :
          c.indexOf('too-many') > -1 ? 'Too many attempts - wait a minute.' :
          'Wrong email or password.');
      });
  }

  /* ── overlay ─────────────────────────────────────────── */
  var OV = null, formShown = false;
  function css(el, s){ for (var k in s) el.style[k] = s[k]; }
  function makeOverlay(){
    if (OV) return;
    OV = document.createElement('div');
    css(OV, { position:'fixed', inset:'0', background:'#F9F7F4', zIndex:'9999',
              display:'flex', alignItems:'center', justifyContent:'center',
              fontFamily:'Helvetica,Arial,sans-serif' });
    OV.innerHTML = '<div id="nalaAuthBox" style="width:82%;max-width:320px;text-align:center;"></div>';
    (document.body || document.documentElement).appendChild(OV);
  }
  function showForm(msg){
    makeOverlay(); formShown = true;
    css(OV, { alignItems:'center', justifyContent:'center' });
    if (!OV.querySelector('#nalaAuthBox')){
      OV.innerHTML = '<div id="nalaAuthBox" style="width:82%;max-width:320px;text-align:center;"></div>';
    }
    var b = OV.querySelector('#nalaAuthBox');
    b.innerHTML =
      '<div style="font-size:11px;letter-spacing:.35em;color:#999990;margin-bottom:26px;">N A L A</div>'+
      '<input id="naEmail" type="email" placeholder="Email" autocomplete="username" style="width:100%;box-sizing:border-box;padding:13px 12px;margin-bottom:10px;border:1px solid #E0E0DA;border-radius:6px;font-size:15px;background:#fff;color:#1C1C1A;">'+
      '<input id="naPass" type="password" placeholder="Password" autocomplete="current-password" style="width:100%;box-sizing:border-box;padding:13px 12px;margin-bottom:14px;border:1px solid #E0E0DA;border-radius:6px;font-size:15px;background:#fff;color:#1C1C1A;">'+
      '<button id="naGo" style="width:100%;padding:14px;background:#1C1C1A;color:#fff;border:0;border-radius:6px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;cursor:pointer;">Sign in</button>'+
      '<div id="naErr" style="color:#A8321E;font-size:12px;margin-top:12px;min-height:15px;">'+(msg||'')+'</div>';
    var go = function(){
      var e = document.getElementById('naEmail').value.trim();
      var p = document.getElementById('naPass').value;
      var err = document.getElementById('naErr');
      var btn = document.getElementById('naGo');
      function fail(msg){ btn.disabled = false; err.textContent = msg; }
      if (!e || !p){ err.textContent = 'Enter the email and password.'; return; }
      err.textContent = '';
      btn.disabled = true;
      /* If auth-compat never arrived, the sign-in method does not exist and the
         tap used to die here leaving a dead grey button. Fetch the script and
         try again; whatever happens, the button comes back with a message.  */
      if (canSignIn()){ trySignIn(e, p, btn, err, fail); return; }
      err.textContent = 'Starting sign-in service...';
      recoverSDK(function(){
        if (!canSignIn()){ fail('Sign-in service did not load - check the connection and reload.'); return; }
        wireAuth();
        err.textContent = '';
        trySignIn(e, p, btn, err, fail);
      });
    };
    document.getElementById('naGo').onclick = go;
    document.getElementById('naPass').onkeydown = function(ev){ if (ev.key === 'Enter') go(); };
  }
  /* ── passcode pad ────────────────────────────────────────
     The default way in. A 6 digit code IS the credential: the account is
     <code>@staff.nala with the same six digits as the password. Six because
     Firebase rejects passwords under six characters, so a four digit code
     cannot be one at all.

     Layout is fixed on purpose. The slots sit 162px from the top and the
     keypad hard against the bottom in EVERY state, so a message appearing
     never moves the thing a thumb is aiming at. The message zone between
     them holds the slack and never falls below 52px.                    */
  var PAD_ATTEMPTS = 0, PAD_LOCKED = false;
  var CODE_LEN = 6, PAD_DOMAIN = '@staff.nala';

  function padDigitsOf(el){ return el.getAttribute('data-code') || ''; }

  function showPad(msg){
    makeOverlay(); formShown = true;
    css(OV, { alignItems:'stretch', justifyContent:'flex-start' });
    var keys = ['1','2','3','4','5','6','7','8','9','','0','back'];
    var slots = '', i;
    for (i = 0; i < CODE_LEN; i++){
      slots += '<div class="naSlot" style="width:51px;height:56px;border:1px solid #1C1C1A;'+
               'border-radius:9px;background:#fff;display:flex;align-items:center;'+
               'justify-content:center;"><span style="width:9px;height:9px;border-radius:50%;'+
               'background:#1C1C1A;display:none;"></span></div>';
    }
    var pad = '';
    for (i = 0; i < keys.length; i++){
      var k = keys[i];
      if (k === ''){ pad += '<div></div>'; continue; }
      if (k === 'back'){
        /* the icon alone, no border and no fill: it is not one of the digits.
           The tap area is still the whole key.                            */
        pad += '<button class="naKey" data-k="back" aria-label="Delete" style="height:58px;'+
               'border:0;background:transparent;display:flex;align-items:center;'+
               'justify-content:center;cursor:pointer;-webkit-tap-highlight-color:transparent;">'+
               '<span style="font-size:24px;line-height:1;color:#1C1C1A;">&#9003;</span></button>';
        continue;
      }
      pad += '<button class="naKey" data-k="'+k+'" style="height:58px;border:1px solid #E0E0DA;'+
             'background:#fff;border-radius:9px;font-size:20px;color:#1C1C1A;cursor:pointer;'+
             'font-family:inherit;-webkit-tap-highlight-color:transparent;">'+k+'</button>';
    }
    OV.innerHTML =
      '<div id="nalaPad" data-code="" style="flex:1;display:flex;flex-direction:column;'+
      'padding:100px 22px 22px;box-sizing:border-box;width:100%;">'+
        '<div id="naMark" style="font-size:11px;letter-spacing:.35em;color:#999990;'+
          'text-align:center;line-height:14px;margin-bottom:22px;'+
          '-webkit-user-select:none;user-select:none;cursor:default;">N A L A</div>'+
        '<div style="font-size:10px;letter-spacing:.18em;color:#999990;text-align:center;'+
          'text-transform:uppercase;line-height:12px;margin-bottom:14px;">Staff passcode</div>'+
        '<div id="naSlots" style="display:flex;gap:8px;justify-content:space-between;">'+slots+'</div>'+
        '<div id="naPadMsg" style="flex:1;min-height:52px;display:flex;align-items:center;'+
          'justify-content:center;text-align:center;color:#A8321E;font-size:13px;'+
          'line-height:1.4;padding:14px 0;">'+(msg||'')+'</div>'+
        '<div id="naKeys" style="display:grid;grid-template-columns:repeat(3,1fr);gap:21px;">'+pad+'</div>'+
      '</div>';

    var padEl = document.getElementById('nalaPad');
    var msgEl = document.getElementById('naPadMsg');
    var slotEls = OV.querySelectorAll('.naSlot');

    function paint(){
      var code = padDigitsOf(padEl);
      for (var j = 0; j < slotEls.length; j++){
        slotEls[j].firstChild.style.display = j < code.length ? 'block' : 'none';
      }
    }
    function setErr(t, red){
      msgEl.textContent = t || '';
      for (var j = 0; j < slotEls.length; j++){
        slotEls[j].style.borderColor = red ? '#A8321E' : '#1C1C1A';
      }
    }
    function clearCode(){ padEl.setAttribute('data-code', ''); paint(); }

    function submit(){
      var code = padDigitsOf(padEl);
      setErr('');
      function fail(t){
        PAD_ATTEMPTS++;
        setErr(t, true);
        clearCode();
        if (PAD_ATTEMPTS >= 5) lock();
      }
      if (!canSignIn()){
        setErr('Starting sign-in service...');
        recoverSDK(function(){
          if (!canSignIn()){ setErr('Sign-in service did not load - check the connection and reload.', true); clearCode(); return; }
          wireAuth(); setErr(''); doSignIn(code, fail);
        });
        return;
      }
      doSignIn(code, fail);
    }
    function doSignIn(code, fail){
      var pr;
      try { pr = firebase.auth().signInWithEmailAndPassword(code + PAD_DOMAIN, code); }
      catch (ex){ fail('Could not start sign-in - reload the page.'); return; }
      if (!pr || !pr.then){ fail('Could not start sign-in - reload the page.'); return; }
      pr.then(function(){ PAD_ATTEMPTS = 0; })
        .catch(function(ex){
          var c = (ex && ex.code) || '';
          fail(c.indexOf('network') > -1 ? 'No connection - try again.' :
               c.indexOf('too-many') > -1 ? 'Too many attempts - wait a minute.' :
               'Wrong passcode.');
        });
    }
    function lock(){
      PAD_LOCKED = true;
      setErr('Too many attempts - wait a minute.', true);
      setTimeout(function(){ PAD_LOCKED = false; PAD_ATTEMPTS = 0; setErr(''); }, 60000);
    }

    function press(k){
      if (PAD_LOCKED) return;
      var code = padDigitsOf(padEl);
      if (k === 'back'){
        padEl.setAttribute('data-code', code.slice(0, -1)); paint(); return;
      }
      if (code.length >= CODE_LEN) return;
      code += k;
      padEl.setAttribute('data-code', code);
      setErr('');
      paint();
      if (code.length === CODE_LEN) submit();   /* no button: the sixth press is the submit */
    }
    var keyEls = OV.querySelectorAll('.naKey');
    for (i = 0; i < keyEls.length; i++){
      (function(b){ b.onclick = function(){ press(b.getAttribute('data-k')); }; })(keyEls[i]);
    }

    /* The email form is the fallback door, kept behind a long press on the
       wordmark so it is out of the way without being gone. It is the only
       way in for an address that can receive a password reset.          */
    var mark = document.getElementById('naMark'), held = null;
    function holdStart(){ held = setTimeout(function(){ held = null; showForm(); }, 600); }
    function holdEnd(){ if (held){ clearTimeout(held); held = null; } }
    mark.addEventListener('mousedown', holdStart);
    mark.addEventListener('touchstart', holdStart, {passive:true});
    ['mouseup','mouseleave','touchend','touchcancel'].forEach(function(ev){
      mark.addEventListener(ev, holdEnd);
    });
    window.__NALA_PAD_EMAIL = function(){ showForm(); };   /* tests and recovery */
    paint();
  }

  function removeOverlay(){
    if (OV && OV.parentNode) OV.parentNode.removeChild(OV);
    OV = null; formShown = false;
  }

  /* ── auth wiring ─────────────────────────────────────── */
  if (typeof firebase === 'undefined'){
    makeOverlay();
    OV.querySelector('#nalaAuthBox').innerHTML =
      '<div style="color:#A8321E;font-size:13px;">Could not load the sign-in service.<br>Check the connection and refresh.</div>';
    return;
  }
  firebase.initializeApp(CFG);

  makeOverlay();                 // instant cream cover, no content flash
  setTimeout(function(){         // if no cached login materialises, show the pad
    if (!settled && !formShown) showPad();
  }, 500);

  /* The wiring below is unchanged. It is wrapped so that if auth-compat did
     not arrive, the throw does not kill the rest of this file - and so the
     same wiring can be run again if the script is recovered later.        */
  var wired = false;
  function wireAuth(){
    if (wired) return true;
    try {
      firebase.auth().onIdTokenChanged(function(user){
        if (user){
          user.getIdToken().then(function(t){
            window.__idToken = t;
            if (!settled){ settled = true; removeOverlay(); flush(); }
          });
        } else {
          window.__idToken = null;
          if (settled){            // signed out mid-session
            settled = false;
            showPad('Signed out - sign in to continue.');
          } else if (document.readyState !== 'loading' || document.body){
            showPad();
          }
        }
      });
      wired = true;
    } catch (e){ wired = false; }
    return wired;
  }
  wireAuth();

  window.NALA_SIGNOUT = function(){ try { firebase.auth().signOut(); } catch(e){} };
})();
