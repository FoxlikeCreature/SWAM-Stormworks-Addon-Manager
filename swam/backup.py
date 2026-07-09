import json
import shutil
import time
from pathlib import Path
from.paths import SWAM_DATA
KEEP_BACKUPS=5
def backups_root(save_name:str)->Path:
 return SWAM_DATA/"backups"/save_name
def make_backup(save_path:Path,operation:str)->Path:
 ts=time.strftime("%Y%m%d-%H%M%S")
 dest=backups_root(save_path.name)/ts
 dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists():
  dest=dest.with_name(dest.name+"-"+str(time.time_ns()%1000))
 shutil.copytree(save_path,dest)
 (dest.parent/f"{dest.name}.meta.json").write_text(json.dumps({"operation":operation,"save":str(save_path),"time":ts},ensure_ascii=False,indent=1))
 _prune(dest.parent)
 return dest
def _prune(root:Path)->None:
 dirs=sorted(d for d in root.iterdir()if d.is_dir())
 for old in dirs[:-KEEP_BACKUPS]:
  shutil.rmtree(old)
  meta=root/f"{old.name}.meta.json"
  if meta.exists():
   meta.unlink()
def list_backups(save_name:str)->list[dict]:
 root=backups_root(save_name)
 out=[]
 if root.is_dir():
  for d in sorted((d for d in root.iterdir()if d.is_dir()),reverse=True):
   meta=root/f"{d.name}.meta.json"
   op="?"
   if meta.is_file():
    try:
     op=json.loads(meta.read_text()).get("operation","?")
    except(OSError,ValueError):
     pass
   out.append({"path":d,"time":d.name,"operation":op})
 return out
def restore_backup(save_path:Path,backup:Path)->None:
 tmp=save_path.with_name(save_path.name+".swam-broken")
 save_path.rename(tmp)
 try:
  shutil.copytree(backup,save_path)
 except BaseException:
  if not save_path.exists():
   tmp.rename(save_path)
  raise
 shutil.rmtree(tmp)
class Transaction:
 def __init__(self,save_path:Path,operation:str,enabled:bool=True):
  self.save_path=save_path
  self.operation=operation
  self.enabled=enabled
  self.backup:Path|None=None
 def __enter__(self):
  from.guard import ensure_game_closed
  ensure_game_closed()
  if self.enabled:
   self.backup=make_backup(self.save_path,self.operation)
  return self
 def __exit__(self,exc_type,exc,tb):
  if exc_type is not None and self.backup is not None:
   restore_backup(self.save_path,self.backup)
   print(f"error - save restored from backup {self.backup}")
  return False
