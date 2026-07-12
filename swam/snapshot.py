from pathlib import Path
from.import paths
def _dir(save_name:str)->Path:
 return paths.SWAM_DATA/"world"/save_name
def _file(save_name:str,addon_name:str)->Path:
 safe=addon_name.replace("/","_").replace("\\","_")
 return _dir(save_name)/f"{safe}.xml"
def recorded(save_name:str,addon_name:str)->Path|None:
 f=_file(save_name,addon_name)
 return f if f.is_file()else None
def record(save_name:str,addon_name:str,addon_dir:Path)->None:
 src=addon_dir/"playlist.xml"
 if not src.is_file():
  return
 f=_file(save_name,addon_name)
 f.parent.mkdir(parents=True,exist_ok=True)
 f.write_bytes(src.read_bytes())
def sync(save_name:str,playlists:list[str])->None:
 from.import addons
 for v in playlists:
  name=addons.playlist_name(v)
  if name is None or recorded(save_name,name)is not None:
   continue
  d=addons.playlist_dir(v)
  if d is not None:
   record(save_name,name,d)
def edited(save_name:str,addon_name:str,addon_dir:Path)->bool:
 f=recorded(save_name,addon_name)
 src=addon_dir/"playlist.xml"
 if f is None or not src.is_file():
  return False
 return f.read_bytes()!=src.read_bytes()
