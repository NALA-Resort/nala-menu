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
      if (!e || !p){ err.textContent = 'Enter the email and password.'; return; }
      err.textContent = '';
      document.getElementById('naGo').disabled = true;
      firebase.auth().signInWithEmailAndPassword(e, p)
        .catch(function(ex){
          document.getElementById('naGo').disabled = false;
          var c = (ex && ex.code) || '';
          err.textContent =
            c.indexOf('network') > -1 ? 'No connection - try again.' :
            c.indexOf('too-many') > -1 ? 'Too many attempts - wait a minute.' :
            'Wrong email or password.';
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
  if (typeof firebase === 'undefined'){
    makeOverlay();
    OV.querySelector('#nalaAuthBox').innerHTML =
      '<div style="color:#A8321E;font-size:13px;">Could not load the sign-in service.<br>Check the connection and refresh.</div>';
    return;
  }
  firebase.initializeApp(CFG);

  makeOverlay();                 // instant cream cover, no content flash
  setTimeout(function(){         // if no cached login materialises, show the form
    if (!settled && !formShown) showForm();
  }, 500);

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
        showForm('Signed out - sign in to continue.');
      } else if (document.readyState !== 'loading' || document.body){
        showForm();
      }
    }
  });

  window.NALA_SIGNOUT = function(){ firebase.auth().signOut(); };
})();
