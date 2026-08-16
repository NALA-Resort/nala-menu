# Publishes one commit to main. Put a GitHub token with contents:write on the
# repo at /home/claude/.ghtoken first (no newline needed, it is stripped).
import json,base64,urllib.request,os
TOKEN=open('/home/claude/.ghtoken').read().strip()
REPO="NALA-Resort/nala-menu"; API="https://api.github.com/repos/"+REPO
# Edit these two, then run: python3 /home/claude/push.py
FILES=["README.md"]
MSG="Say what changed and why, in the imperative, no em dashes"
def call(path,data=None,method=None):
    req=urllib.request.Request(path if path.startswith("http") else API+path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization":"token "+TOKEN,"Accept":"application/vnd.github+json",
                 "Content-Type":"application/json","User-Agent":"nala-assistant"},
        method=method or ("POST" if data is not None else "GET"))
    return json.load(urllib.request.urlopen(req))
ref=call("/git/ref/heads/main"); base=ref["object"]["sha"]
basecommit=call("/git/commits/"+base)
tree=[]
for f in FILES:
    blob=call("/git/blobs",{"content":base64.b64encode(open(f,'rb').read()).decode(),"encoding":"base64"})
    tree.append({"path":f,"mode":"100644","type":"blob","sha":blob["sha"]})
    print("blob",f,blob["sha"][:8])
nt=call("/git/trees",{"base_tree":basecommit["tree"]["sha"],"tree":tree})
nc=call("/git/commits",{"message":MSG,"tree":nt["sha"],"parents":[base]})
upd=call("/git/refs/heads/main",{"sha":nc["sha"]},method="PATCH")
print("COMMIT",nc["sha"],"->",upd["object"]["sha"])
