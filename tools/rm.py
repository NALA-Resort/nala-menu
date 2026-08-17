# Removes paths from main. push.py builds a tree from the files it is given on
# top of the existing one, so it can add and update but never delete: anything
# it is not told about simply stays. That gap let a duplicate test suite sit on
# main after it had been deleted locally and the deletion looked published.
#
#   python3 rm.py "commit message" path [path...]
import json, base64, urllib.request, os, sys

TOKEN = open('/home/claude/.ghtoken').read().strip()
REPO  = "NALA-Resort/nala-menu"
API   = "https://api.github.com/repos/" + REPO

MSG   = sys.argv[1]
PATHS = sys.argv[2:]
if not PATHS:
    sys.exit("nothing to remove")

def call(path, data=None, method=None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(data).encode() if data else None,
        method=method or ("POST" if data else "GET"),
        headers={"Authorization": "token " + TOKEN,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "nala-rm",
                 "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))

head = call("/git/ref/heads/main")["object"]["sha"]
base = call("/git/commits/" + head)["tree"]["sha"]

# A null sha on a blob entry is how the Git API says "remove this path".
tree = call("/git/trees", {
    "base_tree": base,
    "tree": [{"path": p, "mode": "100644", "type": "blob", "sha": None}
             for p in PATHS]})["sha"]

commit = call("/git/commits", {"message": MSG, "tree": tree, "parents": [head]})["sha"]
call("/git/refs/heads/main", {"sha": commit}, method="PATCH")
print("REMOVED", ", ".join(PATHS), "->", commit[:7])
