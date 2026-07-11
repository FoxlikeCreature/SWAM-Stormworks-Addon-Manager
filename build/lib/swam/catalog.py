import re
from pathlib import Path
from.import paths
class Item:
 def __init__(self,ident:str,name:str,image:Path|None,source:str,kind:str,folder:Path|None=None):
  self.ident=ident
  self.name=name
  self.image=image
  self.source=source
  self.kind=kind
  try:
   self.mtime=folder.stat().st_mtime if folder else 0.0
  except OSError:
   self.mtime=0.0
def _playlist_name(pl:Path)->str|None:
 m=re.search(r'<playlist [^>]*name="([^"]*)"',pl.read_text(errors="replace"))
 return m.group(1)if m else None
def _mod_name(mx:Path)->str|None:
 m=re.search(r'<mod name="([^"]*)"',mx.read_text(errors="replace"))
 return m.group(1)if m else None
def _find_preview(folder:Path)->Path|None:
 wanted=("workshop_preview.png","mod.png","preview.png","thumbnail.png")
 try:
  by_name={f.name.lower():f for f in folder.iterdir()if f.is_file()}
 except OSError:
  return None
 for cand in wanted:
  if cand in by_name:
   return by_name[cand]
 return None
def game_install_dirs()->list[Path]:
 out=[]
 for lib in paths.steam_libraries():
  d=lib/"steamapps"/"common"/"Stormworks"
  if d.is_dir():
   out.append(d)
 return out
def addons()->list[Item]:
 items:list[Item]=[]
 seen:set[str]=set()
 for ws in paths.workshop_dirs():
  for d in sorted(ws.iterdir()):
   pl=d/"playlist"/"playlist.xml"
   if not pl.is_file()or d.name in seen:
    continue
   name=_playlist_name(pl)
   if name:
    seen.add(d.name)
    items.append(Item(d.name,name,_find_preview(d),"workshop","addon",folder=d))
 missions=paths.sw_root()/"data"/"missions"
 if missions.is_dir():
  for d in sorted(missions.iterdir()):
   if(d/"playlist.xml").is_file():
    name=_playlist_name(d/"playlist.xml")or d.name
    items.append(Item(d.name,name,_find_preview(d),"local","addon",folder=d))
 for inst in game_install_dirs():
  rom=inst/"rom"/"data"/"missions"
  if rom.is_dir():
   for d in sorted(rom.iterdir()):
    if(d/"playlist.xml").is_file():
     name=_playlist_name(d/"playlist.xml")or d.name
     items.append(Item(str(d),name,_find_preview(d),"builtin","addon",folder=d))
   break
 return items
def mods()->list[Item]:
 items:list[Item]=[]
 seen:set[str]=set()
 for ws in paths.workshop_dirs():
  for d in sorted(ws.iterdir()):
   mx=d/"mod.xml"
   if not mx.is_file()or d.name in seen:
    continue
   name=_mod_name(mx)
   if name:
    seen.add(d.name)
    items.append(Item(d.name,name,_find_preview(d),"workshop","mod",folder=d))
 local=paths.local_mods_dir()
 if local.is_dir():
  for d in sorted(local.iterdir()):
   mx=d/"mod.xml"
   if mx.is_file():
    items.append(Item(d.name,_mod_name(mx)or d.name,_find_preview(d),"local","mod",folder=d))
 return items
