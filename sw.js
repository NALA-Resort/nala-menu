/* Nala push service worker.

   This file handles notifications and NOTHING ELSE. There is deliberately no
   fetch handler and no caching: a service worker that caches would serve
   stale pages after a publish, and "clear your browser data" would become a
   permanent instruction. The ?v= versions on the shared files are the whole
   caching story on this site and this must not become a second one.

   It is inert until a phone subscribes from the Notifications toggle. */

var SW_VERSION = 1;

self.addEventListener('install', function(){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(self.clients.claim()); });

/* iOS shows every push: there is no silent delivery, so a push that fails to
   parse must still put something on screen or the phone buzzes with nothing
   behind it, which reads as a broken app.                                */
self.addEventListener('push', function(event){
  var d = {};
  try { d = event.data ? event.data.json() : {}; } catch (e){ d = {}; }

  var title = d.title || 'Nala';
  var body  = d.body  || 'A villa has changed.';
  var opts  = {
    body: body,
    icon: '/nala-icon.png',
    badge: '/nala-icon.png',
    tag: d.tag || 'nala',        /* same tag replaces, so ten marks are not ten banners */
    renotify: !!d.renotify,
    data: { url: d.url || '/cleaners.html' }
  };
  event.waitUntil(self.registration.showNotification(title, opts));
});

/* Tapping the banner should land on the board, and should reuse a window that
   is already open rather than stacking another one.                      */
self.addEventListener('notificationclick', function(event){
  event.notification.close();
  var target = (event.notification.data && event.notification.data.url) || '/cleaners.html';
  event.waitUntil(
    self.clients.matchAll({ type:'window', includeUncontrolled:true }).then(function(list){
      for (var i = 0; i < list.length; i++){
        if (list[i].url.indexOf(target) > -1 && 'focus' in list[i]) return list[i].focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
    })
  );
});
