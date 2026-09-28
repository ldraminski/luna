"""Buduje wszystkie workflowy Luny.

  python3 build_all.py            → oboe-*.json z config.local.json (do wdrożenia na własną instancję n8n; poza repo)
  python3 build_all.py --public   → workflows/*.json z config.example.json (publikowane w repo, do importu)
"""
import glob, json, os, shutil, subprocess, sys

here = os.path.dirname(os.path.abspath(__file__))
public = "--public" in sys.argv
env = dict(os.environ, **({"LUNA_CONFIG": "example"} if public else {}))
for b in sorted(glob.glob(os.path.join(here, "build_*.py"))):
    if b.endswith("build_all.py"): continue
    subprocess.run([sys.executable, b], cwd=here, env=env, check=True, stdout=subprocess.DEVNULL)
if public:
    out = os.path.join(here, "workflows"); os.makedirs(out, exist_ok=True)
    for f in sorted(glob.glob(os.path.join(here, "oboe-*.json"))):
        name = json.load(open(f))["name"]
        shutil.move(f, os.path.join(out, os.path.basename(f)))
        print("workflows/" + os.path.basename(f), "—", name)
else:
    print("\n".join(sorted(os.path.basename(f) for f in glob.glob(os.path.join(here, "oboe-*.json")))))
