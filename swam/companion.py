import shutil
import sys
from pathlib import Path
from.import paths,savedata
from.scene import Scene
NAME="SWAM Companion"
PLAYLIST_VALUE=f"data/missions/{NAME}"
def _companion_src()->Path:
 if getattr(sys,"frozen",False):
  return Path(sys._MEIPASS)/"swam"/"companion"
 return Path(__file__).resolve().parent/"companion"
SRC=_companion_src()
def installed_dir()->Path:
 return paths.sw_root()/"data"/"missions"/NAME
def install_files()->None:
 dest=installed_dir()
 if not dest.exists():
  shutil.copytree(SRC,dest)
  return
 for src in SRC.iterdir():
  if src.is_file():
   shutil.copy2(src,dest/src.name)
def _names_companion(value:str)->bool:
 import re
 if value==PLAYLIST_VALUE:
  return True
 disk=paths.game_path_to_disk(value)
 if disk is None:
  return False
 pl=disk/"playlist.xml"
 if not pl.is_file():
  pl=disk/"playlist"/"playlist.xml"
 if not pl.is_file():
  return False
 m=re.search(r'<playlist [^>]*name="([^"]*)"',pl.read_text(errors="replace"))
 return bool(m and m.group(1)==NAME)
def script_entry(scene:Scene)->dict|None:
 for s in scene.list_scripts():
  if s["path"]==PLAYLIST_VALUE or(s["store"]==3 and _names_companion(s["path"])):
   return s
 return None
def playlist_value(scene:Scene)->str|None:
 for v in scene.list_playlists():
  if v==PLAYLIST_VALUE or _names_companion(v):
   return v
 return None
def script_id(scene:Scene)->int|None:
 s=script_entry(scene)
 return s["script_id"]if s else None
def is_installed(scene:Scene)->bool:
 return script_id(scene)is not None
def install_into_scene(scene:Scene)->int:
 if PLAYLIST_VALUE not in scene.list_playlists():
  scene.add_playlist(PLAYLIST_VALUE)
 return scene.add_script(PLAYLIST_VALUE)
def _data_file(save_path:Path,sid:int)->Path:
 return save_path/"script_data"/f"{sid}.xml"
def load_data(save_path:Path,sid:int)->dict:
 f=_data_file(save_path,sid)
 if f.is_file():
  return savedata.load_file(f)
 return{}
def drop_pending(data:dict,action:str,addon:str)->int:
 tasks=data.get("tasks")or{}
 report=data.get("report")or{}
 doomed=[n for n,t in tasks.items()if isinstance(t,dict)and t.get("action")==action and t.get("addon")==addon and n not in report]
 for n in doomed:
  del tasks[n]
 return len(doomed)
def queue_task(save_path:Path,sid:int,task:dict)->int:
 data=load_data(save_path,sid)
 data.setdefault("journal",{})
 data.setdefault("report",{})
 tasks=data.setdefault("tasks",{})
 dropped=drop_pending(data,task.get("action"),task.get("addon"))
 if task.get("action")=="despawn":
  dropped+=drop_pending(data,"spawn_env",task.get("addon"))
 if dropped:
  print(f"dropped {dropped} queued task(s) the game had not executed ""yet - they are superseded by this one")
 n=max((k for k in tasks if isinstance(k,int)),default=0)+1
 tasks[n]=task
 savedata.save_file(_data_file(save_path,sid),data)
 return n
def cancel_pending(save_path:Path,sid:int,addon:str)->int:
 data=load_data(save_path,sid)
 dropped=drop_pending(data,"spawn_env",addon)+drop_pending(data,"despawn",addon)
 if dropped:
  savedata.save_file(_data_file(save_path,sid),data)
 return dropped
def journal(save_path:Path,sid:int)->dict:
 return load_data(save_path,sid).get("journal",{})
def reports(save_path:Path,sid:int)->dict:
 return load_data(save_path,sid).get("report",{})
