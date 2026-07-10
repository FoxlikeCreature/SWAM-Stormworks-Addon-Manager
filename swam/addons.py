import re
import shutil
from pathlib import Path
from.import paths
class AddonRef:
 def __init__(self,disk_path:Path):
  self.disk_path=disk_path
  pl=disk_path/"playlist.xml"
  if not pl.is_file():
   raise SystemExit(f"no playlist.xml: {disk_path}")
  m=re.search(r'<playlist [^>]*name="([^"]*)"',pl.read_text(errors="replace"))
  if not m:
   raise SystemExit(f"playlist.xml has no name attribute: {pl}")
  self.name=m.group(1)
 @property
 def scripted(self)->bool:
  s=self.disk_path/"script.lua"
  return s.is_file()and len(s.read_bytes().strip())>0
 @property
 def playlist_value(self)->str:
  return f"data/missions/{self.name}"
 def init_risk(self)->str|None:
  s=self.disk_path/"script.lua"
  if not s.is_file():
   return None
  text=s.read_text(errors="replace")
  has_top_init=bool(re.search(r"^g_savedata\s*=",text,re.M))
  uses_guard="is_world_create"in text
  if uses_guard and not has_top_init:
   return("this addon initializes only under is_world_create - in an ""existing save that never runs, so the addon may misbehave ""or crash. Check its behaviour after adding")
  if uses_guard:
   return("this addon has world-creation-only actions - they will be ""skipped (the companion spawns its env locations instead)")
  return None
 def local_dir(self)->Path:
  return paths.sw_root()/"data"/"missions"/self.name
def resolve_addon(ident:str)->AddonRef:
 p=Path(ident).expanduser()
 if p.is_dir():
  if(p/"playlist.xml").is_file():
   return AddonRef(p)
  if(p/"playlist"/"playlist.xml").is_file():
   return AddonRef(p/"playlist")
 if ident.isdigit():
  ws=paths.find_workshop_item(ident)
  if ws is not None and(ws/"playlist"/"playlist.xml").is_file():
   return AddonRef(ws/"playlist")
 local=paths.sw_root()/"data"/"missions"/ident
 if(local/"playlist.xml").is_file():
  return AddonRef(local)
 raise SystemExit(f"addon not found: {ident}\n"f"(tried: path, workshop id, name in data/missions)")
def find_script_entry(scene,addon_name:str,playlist_value:str):
 for s in scene.list_scripts():
  p=s["path"]
  if p==playlist_value:
   return True,p
  if s["store"]==3:
   wine=p.replace("\\","/")
   if wine.rstrip("/").endswith(f"/{addon_name}/playlist"):
    return True,p
   disk=paths.game_path_to_disk(p)
   if disk and(disk/"playlist.xml").is_file():
    m=re.search(r'<playlist [^>]*name="([^"]*)"',(disk/"playlist.xml").read_text(errors="replace"))
    if m and m.group(1)==addon_name:
     return True,p
 return False,None
def find_workshop_source(addon_name:str)->AddonRef|None:
 for ws in paths.workshop_dirs():
  for d in ws.iterdir():
   pl=d/"playlist"/"playlist.xml"
   if pl.is_file():
    m=re.search(r'<playlist [^>]*name="([^"]*)"',pl.read_text(errors="replace"))
    if m and m.group(1)==addon_name:
     return AddonRef(d/"playlist")
 return None
def dir_digest(folder:Path)->str:
 import hashlib
 h=hashlib.sha256()
 for f in sorted(folder.rglob("*")):
  if f.is_file():
   h.update(str(f.relative_to(folder)).encode())
   h.update(f.read_bytes())
 return h.hexdigest()[:16]
def update_available(rec:dict,name:str)->bool:
 src=find_workshop_source(name)
 if src is None:
  return False
 src_digest=dir_digest(src.disk_path)
 known=rec.get("source_digest")
 if known is not None:
  return src_digest!=known
 local_dir=paths.sw_root()/"data"/"missions"/name
 return local_dir.is_dir()and src_digest!=dir_digest(local_dir)
def local_playlist_changed(rec:dict,name:str)->bool:
 from.import lock
 pl=paths.sw_root()/"data"/"missions"/name/"playlist.xml"
 known=rec.get("playlist_hash")
 return known is not None and pl.is_file()and lock.file_hash(pl)!=known
def install_files(ref:AddonRef)->Path:
 dest=ref.local_dir()
 if ref.disk_path==dest:
  return dest
 if dest.exists():
  if(dest/"playlist.xml").read_bytes()==(ref.disk_path/"playlist.xml").read_bytes():
   return dest
  raise SystemExit(f"{dest} already holds a DIFFERENT version of this "f"addon - sort it out manually, refusing to overwrite")
 shutil.copytree(ref.disk_path,dest)
 return dest
