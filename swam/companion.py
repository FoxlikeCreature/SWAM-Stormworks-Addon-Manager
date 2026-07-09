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
 if dest.exists():
  shutil.copy2(SRC/"script.lua",dest/"script.lua")
  return
 shutil.copytree(SRC,dest)
def script_id(scene:Scene)->int|None:
 import re
 for s in scene.list_scripts():
  if s["path"]==PLAYLIST_VALUE:
   return s["script_id"]
  if s["store"]==3:
   disk=paths.game_path_to_disk(s["path"])
   if disk and(disk/"playlist.xml").is_file():
    m=re.search(r'<playlist [^>]*name="([^"]*)"',(disk/"playlist.xml").read_text(errors="replace"))
    if m and m.group(1)==NAME:
     return s["script_id"]
 return None
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
def queue_task(save_path:Path,sid:int,task:dict)->int:
 data=load_data(save_path,sid)
 tasks=data.setdefault("tasks",{})
 n=max((k for k in tasks if isinstance(k,int)),default=0)+1
 tasks[n]=task
 data.setdefault("journal",{})
 data.setdefault("report",{})
 savedata.save_file(_data_file(save_path,sid),data)
 return n
def journal(save_path:Path,sid:int)->dict:
 return load_data(save_path,sid).get("journal",{})
def reports(save_path:Path,sid:int)->dict:
 return load_data(save_path,sid).get("report",{})
