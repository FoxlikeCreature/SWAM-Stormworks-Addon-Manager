import re
from pathlib import Path
from.import lock,paths
from.scene import Scene
def run(save_path:Path)->list[str]:
 problems:list[str]=[]
 scene=Scene(save_path/"scene.xml")
 try:
  scene.verify()
 except SystemExit as e:
  problems.append(f"scene.xml: {e}")
 scripts=scene.list_scripts()
 playlists=scene.list_playlists()
 for s in scripts:
  if s["store"]!=4:
   continue
  folder=paths.sw_root()/s["path"]
  if not(folder/"playlist.xml").is_file():
   problems.append(f"addon from <s> is missing on disk: {s['path']}")
  if s["path"]not in playlists:
   problems.append(f"addon in <s> but not in active_playlists: {s['path']}")
 for v in playlists:
  if v.startswith("data/missions/"):
   if not(paths.sw_root()/v/"playlist.xml").is_file():
    problems.append(f"playlist missing on disk: {v}")
 ids={s["script_id"]for s in scripts}
 sd=save_path/"script_data"
 if sd.is_dir():
  for f in sd.glob("*.xml"):
   m=re.fullmatch(r"(\d+)\.xml",f.name)
   if m and int(m.group(1))not in ids:
    problems.append(f"orphaned script_data/{f.name} (no <s> with this id)")
 lk=lock.load(save_path.name)
 for name,rec in lk["addons"].items():
  if rec["playlist_value"]not in playlists:
   problems.append(f"lock: addon '{name}' is recorded as installed, "f"but there is no active_playlists entry")
  pl=paths.sw_root()/rec["playlist_value"]/"playlist.xml"
  if not pl.is_file():
   problems.append(f"lock: files of addon '{name}' disappeared from disk")
  elif lock.file_hash(pl)!=rec["playlist_hash"]:
   problems.append(f"lock: playlist.xml of addon '{name}' changed "f"after installation")
 return problems
