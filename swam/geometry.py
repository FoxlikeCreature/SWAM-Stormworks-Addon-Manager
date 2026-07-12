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
VEHICLE_COMPONENT="3"
ZONE_COMPONENT="10"
_SIG_CACHE:dict[tuple,dict]={}
def _by_type(playlist_xml:Path)->dict[str,set]:
 try:
  key=(str(playlist_xml),playlist_xml.stat().st_mtime_ns)
 except OSError:
  key=None
 if key is not None and key in _SIG_CACHE:
  return _SIG_CACHE[key]
 sigs=_read_signatures(playlist_xml)
 if key is not None:
  _SIG_CACHE[key]=sigs
 return sigs
def playlist_signatures(playlist_xml:Path,kind:str="vehicle")->set[tuple]:
 by_type=_by_type(playlist_xml)
 if kind=="vehicle":
  return set(by_type.get(VEHICLE_COMPONENT,()))
 out:set[tuple]=set()
 for t,sigs in by_type.items():
  if t not in(VEHICLE_COMPONENT,ZONE_COMPONENT):
   out|=sigs
 return out
def _read_signatures(playlist_xml:Path)->dict[str,set]:
 whole=playlist_xml.read_text(errors="replace")
 sigs:dict[str,set]={}
 for l in re.finditer(r"<l ([^>]*)>(.*?)</l>",whole,re.S):
  head,text=l.group(1),l.group(2)
  tile=re.search(r'tile="([^"]*)"',head)
  if not tile or not tile.group(1):
   continue
  for c in re.finditer(r'<c component_type="(\d+)"[^>]*>(.*?)</c>',text,re.S):
   ctype,body=c.group(1),c.group(2)
   tr=re.search(r"<spawn_transform ([^/]*)/>",body)
   if not tr:
    continue
   a=dict(re.findall(r'(\d+)="([-\d.eE]+)"',tr.group(1)))
   if"30"not in a:
    continue
   m={f"{r}{c2}":float(a.get(f"{r}{c2}",1.0 if r==c2 else 0.0))for r in range(4)for c2 in range(4)}
   off={"x":0.0,"y":0.0,"z":0.0}
   om=re.search(r"<spawn_local_offset ([^/]*)/>",body)
   if om:
    off.update({k:float(v)for k,v in re.findall(r'([xyz])="([-\d.eE]+)"',om.group(1))})
   ox,oy,oz=off["x"],off["y"],off["z"]
   x=ox*m["00"]+oy*m["10"]+oz*m["20"]+m["30"]
   y=ox*m["01"]+oy*m["11"]+oz*m["21"]+m["31"]
   z=ox*m["02"]+oy*m["12"]+oz*m["22"]+m["32"]
   sigs.setdefault(ctype,set()).add(_sig(x,y,z))
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
def scene_objects(scene_text:str)->list[dict]:
 out=[]
 for m in re.finditer(r"<object ([^>]*)>(.*?)</object>",scene_text,re.S):
  attrs=dict(re.findall(r'(\w+)="([^"]*)"',m.group(1)))
  tr=re.search(r"<transform ([^/]*)/>",m.group(2))
  if not tr or"id"not in attrs:
   continue
  a=dict(re.findall(r'(\d+)="([-\d.eE]+)"',tr.group(1)))
  if"30"not in a:
   continue
  out.append({"id":int(attrs["id"]),"attested":attrs.get("is_mission")=="true","pos":(float(a["30"]),float(a.get("31",0)),float(a.get("32",0)))})
 return out
def match_objects(scene_text:str,target:set,tolerance:float=TOLERANCE,owned_elsewhere:set|None=None)->tuple[list[int],list[str]]:
 owned_elsewhere=owned_elsewhere or set()
 warnings=[]
 claims:dict[tuple,list[int]]={}
 for o in scene_objects(scene_text):
  sig=_sig(*o["pos"])
  near=[t for t in target if _dist(t,sig)<=tolerance]
  if not near:
   continue
  if o["id"]in owned_elsewhere:
   warnings.append(f"object {o['id']} sits on a spawn point but the "f"journal says another addon spawned it - leaving it alone")
   continue
  if not o["attested"]:
   warnings.append(f"object {o['id']} sits on a spawn point but the game "f"does not mark it as addon-spawned - leaving it alone")
   continue
  claims.setdefault(min(near,key=lambda t:_dist(t,_sig(*o["pos"]))),[]).append(o["id"])
 oids=[]
 for t,ids in claims.items():
  oids.extend(ids)
 return oids,warnings
def addon_attested(scene_text:str)->set[int]:
 ok=set()
 for m in re.finditer(r'<vehicle id="(\d+)"([^>]*)>(.*?)</vehicle>',scene_text,re.S):
  attrs=m.group(2)
  if(('is_mission="true"'in attrs or"addon_tags="in attrs)and re.search(r"<authors\s*/>",m.group(3))):
   ok.add(int(m.group(1)))
 return ok
def _is(value:str,addon_name:str)->bool:
 from.import addons
 return addons.playlist_name(value)==addon_name or value.rsplit("/",1)[-1]==addon_name
def addon_dir(addon_name:str,active_playlists:list[str]):
 from.import addons
 for v in active_playlists:
  if _is(v,addon_name):
   d=addons.playlist_dir(v)
   if d is not None:
    return d
 local=paths.sw_root()/"data"/"missions"/addon_name
 return local if(local/"playlist.xml").is_file()else None
def match(scene_text:str,addon_name:str,active_playlists:list[str],tolerance:float=TOLERANCE,owned_elsewhere:set|None=None,target_playlist:Path|None=None)->tuple[list[int],list[str]]:
 warnings=[]
 owned_elsewhere=owned_elsewhere or set()
 if target_playlist is None:
  target_dir=addon_dir(addon_name,active_playlists)
  if target_dir is None:
   raise SystemExit(f"no playlist.xml found for '{addon_name}' - without its files "f"there is nothing to match the structures against")
  target_playlist=target_dir/"playlist.xml"
 from.import addons
 target=playlist_signatures(target_playlist,"vehicle")
 others:set[tuple]=set()
 for v in active_playlists:
  if _is(v,addon_name):
   continue
  d=addons.playlist_dir(v)
  if d is not None:
   others|=playlist_signatures(d/"playlist.xml","vehicle")
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
  if any(v in owned_elsewhere for v in g["vehicles"]):
   warnings.append(f"group {g['group_id']} sits on a spawn point of "f"'{addon_name}', but the companion's journal says another "f"addon spawned it - leaving it alone")
   continue
  if not all(v in attested for v in g["vehicles"]):
   warnings.append(f"group {g['group_id']} sits on a spawn point "f"but the game does not mark it as addon-spawned "f"- leaving it alone")
   continue
  claims.setdefault(min(near,key=lambda t:_dist(t,g["sig"])),[]).append(g)
 vids=[]
 for t,groups in claims.items():
  if len(groups)>1:
   warnings.append(f"{len(groups)} vehicle groups sit on the same "f"spawn point - ambiguous, leaving them alone")
   continue
  vids.extend(groups[0]["vehicles"])
 return vids,warnings
def match_all(scene_text:str,addon_name:str,active_playlists:list[str],tolerance:float=TOLERANCE,owned_elsewhere:set|None=None,target_playlist:Path|None=None)->tuple[list[int],list[int],list[str]]:
 from.import addons
 vids,warns=match(scene_text,addon_name,active_playlists,tolerance,owned_elsewhere,target_playlist)
 if target_playlist is None:
  target_dir=addon_dir(addon_name,active_playlists)
  if target_dir is None:
   return vids,[],warns
  target_playlist=target_dir/"playlist.xml"
 target=playlist_signatures(target_playlist,"object")
 others:set[tuple]=set()
 for v in active_playlists:
  if _is(v,addon_name):
   continue
  d=addons.playlist_dir(v)
  if d is not None:
   others|=playlist_signatures(d/"playlist.xml","object")
 target-={t for t in target if any(_dist(t,o)<=tolerance for o in others)}
 oids,owarns=match_objects(scene_text,target,tolerance,owned_elsewhere)
 return vids,oids,warns+owarns
