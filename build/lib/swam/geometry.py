import re
from pathlib import Path
from.import paths
TOLERANCE=1.5
def _sig(x:float,y:float,z:float)->tuple:
 return(x%1000,y,z%1000)
def _dist(a:tuple,b:tuple)->float:
 dx=min(abs(a[0]-b[0]),1000-abs(a[0]-b[0]))
 dy=abs(a[1]-b[1])
 dz=min(abs(a[2]-b[2]),1000-abs(a[2]-b[2]))
 return(dx*dx+dy*dy+dz*dz)**0.5
def playlist_signatures(playlist_xml:Path)->set[tuple]:
 text=playlist_xml.read_text(errors="replace")
 sigs=set()
 for c in re.finditer(r"<c [^>]*>(.*?)</c>",text,re.S):
  body=c.group(1)
  tr=re.search(r"<spawn_transform ([^/]*)/>",body)
  if not tr:
   continue
  a=dict(re.findall(r'(\d+)="([-\d.eE]+)"',tr.group(1)))
  if"30"not in a:
   continue
  off={"x":0.0,"y":0.0,"z":0.0}
  om=re.search(r"<spawn_local_offset ([^/]*)/>",body)
  if om:
   off.update({k:float(v)for k,v in re.findall(r'([xyz])="([-\d.eE]+)"',om.group(1))})
  sigs.add(_sig(float(a["30"])+off["x"],float(a.get("31",0))+off["y"],float(a.get("32",0))+off["z"]))
 return sigs
def scene_groups(scene_text:str)->list[dict]:
 i=scene_text.find("<vehicle_group_data")
 j=scene_text.find("</vehicle_group_data>")
 out=[]
 for m in re.finditer(r'<group id="(\d+)"[^>]*>(.*?)</group>',scene_text[i:j],re.S):
  body=m.group(2)
  tr=re.search(r"<initial_transform ([^/]*)/>",body)
  if not tr:
   continue
  a=dict(re.findall(r'(\d+)="([-\d.eE]+)"',tr.group(1)))
  if"30"not in a:
   continue
  vids=[int(v)for v in re.findall(r'<v value="(\d+)"/>',body)]
  out.append({"group_id":int(m.group(1)),"sig":_sig(float(a["30"]),float(a.get("31",0)),float(a.get("32",0))),"vehicles":vids})
 return out
def scene_vehicles(scene_text:str)->list[dict]:
 out=[]
 for m in re.finditer(r'<vehicle id="(\d+)" vehicle_group_id="(\d+)"' r'[^>]*>\s*<transform ([^/]*)/>',scene_text):
  a=dict(re.findall(r'(\d+)="([-\d.eE]+)"',m.group(3)))
  out.append({"id":int(m.group(1)),"group_id":int(m.group(2)),"pos":(float(a.get("30",0)),float(a.get("31",0)),float(a.get("32",0)))})
 return out
def addon_attested(scene_text:str)->set[int]:
 ok=set()
 for m in re.finditer(r'<vehicle id="(\d+)"([^>]*)>(.*?)</vehicle>',scene_text,re.S):
  attrs=m.group(2)
  if(('is_mission="true"'in attrs or"addon_tags="in attrs)and re.search(r"<authors\s*/>",m.group(3))):
   ok.add(int(m.group(1)))
 return ok
def match(scene_text:str,addon_name:str,active_playlists:list[str],tolerance:float=TOLERANCE)->tuple[list[int],list[str]]:
 from.import addons
 warnings=[]
 target_dir=None
 for v in active_playlists:
  if addons.playlist_name(v)==addon_name:
   target_dir=addons.playlist_dir(v)
   break
 if target_dir is None:
  local=paths.sw_root()/"data"/"missions"/addon_name
  if(local/"playlist.xml").is_file():
   target_dir=local
 if target_dir is None:
  raise SystemExit(f"no playlist.xml found for '{addon_name}' - without its files "f"there is nothing to match the structures against")
 target=playlist_signatures(target_dir/"playlist.xml")
 others:set[tuple]=set()
 for v in active_playlists:
  if addons.playlist_name(v)==addon_name:
   continue
  d=addons.playlist_dir(v)
  if d is not None:
   others|=playlist_signatures(d/"playlist.xml")
 contested={t for t in target if any(_dist(t,o)<=tolerance for o in others)}
 if contested:
  warnings.append(f"{len(contested)} signatures are shared with other "f"addons - leaving those structures alone")
  target-=contested
 attested=addon_attested(scene_text)
 claims:dict[tuple,list[dict]]={}
 for g in scene_groups(scene_text):
  near=[t for t in target if _dist(t,g["sig"])<=tolerance]
  if not near:
   continue
  if not all(v in attested for v in g["vehicles"]):
   warnings.append(f"group {g['group_id']} sits on a spawn point "f"but the game does not mark it as addon-spawned "f"- leaving it alone")
   continue
  if len(near)>1:
   warnings.append(f"group {g['group_id']} is near several of the "f"addon's spawn points - leaving it alone")
   continue
  claims.setdefault(near[0],[]).append(g)
 vids=[]
 for t,groups in claims.items():
  if len(groups)>1:
   warnings.append(f"{len(groups)} vehicle groups sit on the same "f"spawn point - ambiguous, leaving them alone")
   continue
  vids.extend(groups[0]["vehicles"])
 return vids,warnings
