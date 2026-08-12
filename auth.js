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
      /* The button must never be able to die silently: if the sign-in service
         did not load, or the call throws for any reason, re-enable it and say
         what happened rather than leaving a dead grey button. */
      if (!canSignIn()){ fail('Sign-in service did not load - reload the page.'); return; }
      var pr;
      try { pr = firebase.auth().signInWithEmailAndPassword(e, p); }
      catch (ex){ fail('Sign-in service did not load - reload the page.'); return; }
      if (!pr || !pr.catch){ fail('Sign-in service did not load - reload the page.'); return; }
      pr.then(function(){ btn.disabled = false; })
        .catch(function(ex){
          var c = (ex && ex.code) || '';
          fail(
            c.indexOf('network') > -1 ? 'No connection - try again.' :
            c.indexOf('too-many') > -1 ? 'Too many attempts - wait a minute.' :
            'Wrong email or password.');
        });
    };
    document.getElementById('naGo').onclick = go;
    document.getElementById('naPass').onkeydown = function(ev){ if (ev.key === 'Enter') go(); };
  }
  function removeOverlay(){
    if (OV && OV.parentNode) OV.parentNode.removeChild(OV);
    OV = null; formShown = false;
  }

  /* ── auth wiring ─────────────────────────────────────── */
  /* app-compat gives us `firebase`, auth-compat gives us `firebase.auth`.
     Either can fail to arrive on a flaky connection; check for both. */
  function authObj(){
    try { return (typeof firebase !== 'undefined' && typeof firebase.auth === 'function')
                 ? firebase.auth() : null; }
    catch (e){ return null; }
  }
  function authReady(){ var a = authObj(); return !!(a && typeof a.onIdTokenChanged === 'function'); }
  function canSignIn(){ var a = authObj(); return !!(a && typeof a.signInWithEmailAndPassword === 'function'); }
  if (!authReady()){
    makeOverlay();
    OV.querySelector('#nalaAuthBox').innerHTML =
      '<div style="color:#A8321E;font-size:13px;line-height:1.5;">Could not load the sign-in service.<br>Check the connection, then reload.</div>'+
      '<button id="naReload" style="margin-top:18px;padding:14px 26px;background:#1C1C1A;color:#fff;border:0;border-radius:6px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;cursor:pointer;">Reload</button>';
    document.getElementById('naReload').onclick = function(){ location.reload(); };
    return;
  }
  firebase.initializeApp(CFG);

  makeOverlay();                 // instant cream cover, no content flash

  /* A device that has signed in before gets its session back from Firebase in
     under a second. Showing the form on a timer made it flash on every page
     change. So: if this device is known to have a login, wait for the token
     and never show the form on a timer; only a device with no remembered
     login gets the form, and a long safety net covers a stalled restore.   */
  var SEEN = 'nala_signed_in';
  function remember(v){ try{ v ? localStorage.setItem(SEEN,'1') : localStorage.removeItem(SEEN); }catch(e){} }
  var known = false; try{ known = localStorage.getItem(SEEN) === '1'; }catch(e){}

  setTimeout(function(){
    if (!settled && !formShown) showForm();
  }, known ? 8000 : 700);

  firebase.auth().onIdTokenChanged(function(user){
    if (user){
      user.getIdToken().then(function(t){
        window.__idToken = t;
        remember(true);
        if (!settled){ settled = true; removeOverlay(); flush(); }
      });
    } else {
      window.__idToken = null;
      remember(false);
      if (settled){            // signed out mid-session
        settled = false;
        showForm('Signed out - sign in to continue.');
      } else if (document.readyState !== 'loading' || document.body){
        showForm();
      }
    }
  });

  window.NALA_SIGNOUT = function(){ firebase.auth().signOut(); };
})();
