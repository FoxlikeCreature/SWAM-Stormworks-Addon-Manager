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
  bad=set(self.name)&set('<>:"/\\|?*')
  if bad or self.name!=self.name.strip()or self.name.endswith("."):
   raise SystemExit(f"the addon calls itself {self.name!r}, and that name cannot "f"become a folder under data/missions on Windows (leading or "f"trailing spaces, a trailing dot, or one of <>:\"/\\|?*).\n"f"Rename it in {pl} - both the name attribute and the folder - "f"and add it again")
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
 @property
 def source(self)->str:
  for ws in paths.workshop_dirs():
   try:
    self.disk_path.relative_to(ws)
    return"workshop"
   except ValueError:
    continue
  return"local"
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
def playlist_dir(value:str)->Path|None:
 if value.startswith("rom/"):
  from.import catalog
  for inst in catalog.game_install_dirs():
   d=inst/value
   if(d/"playlist.xml").is_file():
    return d
  return None
 if value.startswith("data/missions/"):
  d=paths.sw_root()/value
  return d if(d/"playlist.xml").is_file()else None
 disk=paths.game_path_to_disk(value)
 if disk is None:
  return None
 return disk if(disk/"playlist.xml").is_file()else None
def playlist_name(value:str)->str|None:
 if value.startswith("data/missions/"):
  return value.split("/",2)[2]
 d=playlist_dir(value)
 if d is None:
  return None
 pl=d/"playlist.xml"
 if not pl.is_file():
  return None
 m=re.search(r'<playlist [^>]*name="([^"]*)"',pl.read_text(errors="replace"))
 return m.group(1)if m else None
def attached_value(scene,addon_name:str)->str|None:
 direct=f"data/missions/{addon_name}"
 values=scene.list_playlists()
 if direct in values:
  return direct
 for v in values:
  if v.startswith("rom/data/missions/"):
   continue
  if playlist_name(v)==addon_name:
   return v
 return None
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
_WS_INDEX:dict[str,Path]|None=None
def workshop_index(refresh:bool=False)->dict[str,Path]:
 global _WS_INDEX
 if _WS_INDEX is None or refresh:
  index:dict[str,Path]={}
  for ws in paths.workshop_dirs():
   for d in ws.iterdir():
    pl=d/"playlist"/"playlist.xml"
    if pl.is_file():
     m=re.search(r'<playlist [^>]*name="([^"]*)"',pl.read_text(errors="replace"))
     if m and m.group(1)not in index:
      index[m.group(1)]=d/"playlist"
  _WS_INDEX=index
 return _WS_INDEX
def find_workshop_source(addon_name:str)->AddonRef|None:
 hit=workshop_index().get(addon_name)
 return AddonRef(hit)if hit else None
def dir_digest(folder:Path)->str:
 import hashlib
 h=hashlib.sha256()
 for f in sorted(folder.rglob("*")):
  if f.is_file():
   h.update(str(f.relative_to(folder)).encode())
   h.update(f.read_bytes())
 return h.hexdigest()[:16]
def world_digest(folder:Path)->str:
 import hashlib
 h=hashlib.sha256()
 for f in sorted(folder.rglob("*")):
  if f.is_file()and f.name!="script.lua":
   h.update(str(f.relative_to(folder)).encode())
   h.update(f.read_bytes())
 return h.hexdigest()[:16]
def workshop_source(rec:dict,name:str)->AddonRef|None:
 if rec.get("source")=="local":
  return None
 return find_workshop_source(name)
def update_available(rec:dict,name:str)->bool:
 src=workshop_source(rec,name)
 if src is None:
  return False
 src_digest=dir_digest(src.disk_path)
 known=rec.get("source_digest")
 if known is not None:
  return src_digest!=known
 local_dir=paths.sw_root()/"data"/"missions"/name
 return local_dir.is_dir()and src_digest!=dir_digest(local_dir)
def backfill(save_name:str)->None:
 from.import lock
 lk=lock.load(save_name)
 dirty=False
 for name,rec in lk["addons"].items():
  local_dir=paths.sw_root()/"data"/"missions"/name
  if not local_dir.is_dir():
   continue
  if rec.get("source")is None:
   rec["source"]="workshop"if find_workshop_source(name)else"local"
   dirty=True
  if rec.get("world_digest")is None:
   rec["world_digest"]=world_digest(local_dir)
   dirty=True
 if dirty:
  lock.store(save_name,lk)
def local_changed(rec:dict,name:str)->bool:
 local_dir=paths.sw_root()/"data"/"missions"/name
 known=rec.get("world_digest")
 if known is None or not local_dir.is_dir():
  return False
 return world_digest(local_dir)!=known
def install_files(ref:AddonRef)->Path:
 dest=ref.local_dir()
 if ref.disk_path==dest:
  return dest
 if dest.exists():
  if dir_digest(dest)==dir_digest(ref.disk_path):
   return dest
  raise SystemExit(f"{dest} already holds a DIFFERENT copy of '{ref.name}' "f"(its files do not match the source).\nAnother save may be "f"using it. Sort it out manually - refusing to overwrite")
 shutil.copytree(ref.disk_path,dest)
 return dest
