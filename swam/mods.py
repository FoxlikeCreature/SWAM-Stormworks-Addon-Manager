import re
from pathlib import Path
from.import paths
class ModRef:
 def __init__(self,mod_id:str,disk_path:Path,wine_path:str,source:str):
  self.mod_id=mod_id
  self.disk_path=disk_path
  self.wine_path=wine_path
  self.source=source
 @property
 def name(self)->str:
  mod_xml=self.disk_path/"mod.xml"
  if mod_xml.is_file():
   m=re.search(r'<mod name="([^"]*)"',mod_xml.read_text(errors="replace"))
   if m:
    from.import addons
    return addons.xml_unescape(m.group(1))
  return f"<{self.mod_id}>"
 @property
 def has_tiles(self)->bool:
  return(self.disk_path/"data"/"tiles").is_dir()
def resolve_mod(ident:str)->ModRef:
 p=Path(ident).expanduser()
 if p.is_dir()and(p/"mod.xml").is_file():
  mod_id=p.name
  local=paths.local_mods_dir()/mod_id
  if p==local:
   return ModRef(mod_id,p,paths.local_mod_game_path(mod_id),"local")
  return ModRef(mod_id,p,paths.game_path_string(p),"workshop")
 if ident.isdigit():
  ws=paths.find_workshop_item(ident)
  if ws is not None and(ws/"mod.xml").is_file():
   return ModRef(ident,ws,paths.game_path_string(ws),"workshop")
  local=paths.local_mods_dir()/ident
  if(local/"mod.xml").is_file():
   return ModRef(ident,local,paths.local_mod_game_path(ident),"local")
  raise SystemExit(f"mod {ident} not found in workshop or data/mods "f"(if this is an addon, use add-addon/remove-addon)")
 raise SystemExit(f"neither an id nor a path to a mod: {ident}")
def match_installed(installed:list[str],ident:str)->str:
 hits=[w for w in installed if w==ident or w.replace("\\","/").rstrip("/").endswith("/"+ident)]
 if not hits:
  raise SystemExit(f"mod {ident} is not attached to this save")
 if len(hits)>1:
  raise SystemExit(f"ambiguous, several entries match: {hits}")
 return hits[0]
def describe_wine_path(wine_path:str)->str:
 mod_id=wine_path.replace("\\","/").rstrip("/").rsplit("/",1)[-1]
 for cand in([paths.local_mods_dir()/mod_id]+[d/mod_id for d in paths.workshop_dirs()]):
  if(cand/"mod.xml").is_file():
   m=re.search(r'<mod name="([^"]*)"',(cand/"mod.xml").read_text(errors="replace"))
   if m:
    from.import addons
    return f"{mod_id}  {addons.xml_unescape(m.group(1))}"
 return f"{mod_id}  <mod files not found on disk!>"
