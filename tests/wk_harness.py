import gi, json, threading, http.server, socketserver, os, sys, datetime
gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1')
from gi.repository import Gtk, WebKit2, GLib
os.chdir('/home/claude/nala')

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
httpd=socketserver.TCPServer(("",8963),Q)
threading.Thread(target=httpd.serve_forever,daemon=True).start()

now=datetime.datetime.now().astimezone(); today=now.strftime("%Y-%m-%d")
rg={str(n):{"name":"G%d"%n,"departs":(now+datetime.timedelta(days=2)).strftime("%Y-%m-%d")} for n in [1,2,3,4,5,9,14,15]}
BOOT = """
window.firebase={initializeApp:function(){},auth:function(){return {
  onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'staff@x',getIdToken:function(){return Promise.resolve('T');}});},20);},
  onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'staff@x'});},25);},signOut:function(){}};}};
(function(){
  var RG=%s, TODAY='%s';
  window.fetch=function(u,o){
    u=String(u);
    function j(x){return Promise.resolve(new Response(JSON.stringify(x),{status:200,headers:{'Content-Type':'application/json'}}));}
    if(u.indexOf('menu.json')>-1) return Promise.resolve(new Response('',{status:404}));
    if(u.indexOf('firebasedatabase.app')>-1){
      if(u.indexOf('/roomguests/'+TODAY)>-1) return j(RG);
      if(u.indexOf('/roomguests/')>-1) return j(null);
      return j({});
    }
    return Promise.reject(new Error('blocked '+u));
  };
})();
""" % (json.dumps(rg), today)

MEASURE = """(function(){
  var vw=window.innerWidth, se=document.scrollingElement;
  function q(s){var e=document.querySelector(s); if(!e) return null;
    var r=e.getBoundingClientRect(); return [Math.round(r.left),Math.round(r.right),Math.round(r.width)];}
  var out={vw:vw, scrollW:se.scrollWidth,
    wrap:q('.wrap'), sec:q('.sec'), rooms:q('.rooms'), tile1:q('.rooms .room'),
    stats:q('.stats'), stat3:q('#tileAwait'), daterow:q('.daterow'), date:q('.daterow .date'),
    tiles:document.querySelectorAll('.rooms .room').length, off:[]};
  var all=document.querySelectorAll('body *');
  for (var i=0;i<all.length;i++){ var r=all[i].getBoundingClientRect();
    if(r.width>0 && (r.left<-1 || r.right>vw+1))
      out.off.push(all[i].tagName+'.'+String(all[i].className).slice(0,34)+' L'+Math.round(r.left)+' R'+Math.round(r.right));}
  return JSON.stringify(out);})();"""

ctx = WebKit2.WebContext.new_ephemeral()
ucm = WebKit2.UserContentManager()
ucm.add_script(WebKit2.UserScript.new(BOOT, WebKit2.UserContentInjectedFrames.TOP_FRAME,
               WebKit2.UserScriptInjectionTime.START, None, None))
view = WebKit2.WebView.new_with_user_content_manager(ucm)
view.get_settings().set_enable_developer_extras(False)
win = Gtk.OffscreenWindow()
win.set_default_size(390, 844)
win.add(view); win.show_all()
view.set_size_request(390,844)

def measured(view, res):
    try:
        v = view.evaluate_javascript_finish(res)
        print("MEASURE:", v.to_string())
    except Exception as e:
        print("EVALFAIL:", e)
    Gtk.main_quit()

def later():
    view.evaluate_javascript(MEASURE, -1, None, None, None, measured)
    return False

def loaded(view, ev):
    if ev == WebKit2.LoadEvent.FINISHED:
        GLib.timeout_add(1800, later)

view.connect("load-changed", loaded)
view.load_uri("http://localhost:8963/tally.html")
GLib.timeout_add(15000, Gtk.main_quit)
Gtk.main()
httpd.shutdown()
