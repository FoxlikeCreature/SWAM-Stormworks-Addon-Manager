import json
import shutil
import time
from pathlib import Path
from.import paths
KEEP_BACKUPS=5
KEEP_PRE_RESTORE=3
def backups_root(save_name:str)->Path:
 return paths.SWAM_DATA/"backups"/save_name
def make_backup(save_path:Path,operation:str,keep:Path|None=None)->Path:
 ts=time.strftime("%Y%m%d-%H%M%S")
 root=backups_root(save_path.name)
 root.mkdir(parents=True,exist_ok=True)
 used=[d.name for d in root.iterdir()if d.is_dir()and d.name.startswith(ts)]
 if not used:
  dest=root/ts
 else:
  taken={int(n.split("-")[2])for n in used if n.count("-")==2 and n.split("-")[2].isdigit()}
  dest=root/f"{ts}-{max(taken,default=0)+1:03d}"
 need=_dir_size(save_path)
 free=shutil.disk_usage(root).free
 if free<need*1.1:
  raise SystemExit(f"not enough room for a backup of '{save_path.name}': it needs "f"about {need//(1024*1024)} MB, only {free//(1024*1024)} MB free "f"in {root}.\nFree some space, or point SWAM_DATA_DIR at another "f"disk, or re-run with --no-backup if you know what you are doing")
 try:
  shutil.copytree(save_path,dest)
 except BaseException as e:
  shutil.rmtree(dest,ignore_errors=True)
  raise SystemExit(f"the backup of '{save_path.name}' failed ({e}) - nothing was "f"changed. The half-written copy has been removed")
 (root/f"{dest.name}.meta.json").write_text(json.dumps({"operation":operation,"save":str(save_path),"time":dest.name},ensure_ascii=False,indent=1))
 _snapshot_lock(save_path.name,root/f"{dest.name}.lock.json")
 _prune(root,keep)
 return dest
def _dir_size(p:Path)->int:
 total=0
 for f in p.rglob("*"):
  try:
   if f.is_file():
    total+=f.stat().st_size
  except OSError:
   continue
 return total
def _snapshot_lock(save_name:str,dest:Path)->None:
 from.import lock
 src=lock.lock_path(save_name)
 if src.is_file():
  shutil.copy2(src,dest)
def _restore_lock(save_name:str,backup:Path)->None:
 from.import lock
 snap=backup.parent/f"{backup.name}.lock.json"
 target=lock.lock_path(save_name)
 if snap.is_file():
  target.parent.mkdir(parents=True,exist_ok=True)
  shutil.copy2(snap,target)
 elif target.is_file():
  target.unlink()
def _operation_of(root:Path,name:str)->str:
 meta=root/f"{name}.meta.json"
 if meta.is_file():
  try:
   return json.loads(meta.read_text()).get("operation","?")
  except(OSError,ValueError):
   pass
 return"?"
def _sorted_dirs(root:Path)->list[Path]:
 return sorted((d for d in root.iterdir()if d.is_dir()),key=lambda d:d.name)
def _prune(root:Path,keep:Path|None=None)->None:
 dirs=_sorted_dirs(root)
 protected={keep.resolve()}if keep else set()
 groups:dict[bool,list[Path]]={True:[],False:[]}
 for d in dirs:
  groups[_operation_of(root,d.name)=="pre-restore"].append(d)
 doomed=[]
 for is_restore,quota in((True,KEEP_PRE_RESTORE),(False,KEEP_BACKUPS)):
  doomed+=groups[is_restore][:-quota]if quota else groups[is_restore]
 for old in doomed:
  if old.resolve()in protected:
   continue
  shutil.rmtree(old)
  for side in(root/f"{old.name}.meta.json",root/f"{old.name}.lock.json"):
   if side.exists():
    side.unlink()
def list_backups(save_name:str)->list[dict]:
 root=backups_root(save_name)
 out=[]
 if root.is_dir():
  for d in reversed(_sorted_dirs(root)):
   if not(root/f"{d.name}.meta.json").is_file():
    continue
   out.append({"path":d,"time":d.name,"operation":_operation_of(root,d.name)})
 return out
def restore_backup(save_path:Path,backup:Path)->None:
 tmp=save_path.with_name(save_path.name+".swam-broken")
 if tmp.exists():
  shutil.rmtree(tmp)
 save_path.rename(tmp)
 try:
  shutil.copytree(backup,save_path)
 except BaseException:
  if save_path.exists():
   shutil.rmtree(save_path,ignore_errors=True)
  if not save_path.exists():
   tmp.rename(save_path)
  raise
 _restore_lock(save_path.name,backup)
 shutil.rmtree(tmp)
def _busy_path(save_name:str)->Path:
 return paths.SWAM_DATA/"locks"/f"{save_name}.busy"
def _alive(pid:int)->bool:
 import os
 if pid<=0:
  return False
 try:
  os.kill(pid,0)
 except ProcessLookupError:
  return False
 except PermissionError:
  return True
 except OSError:
  return True
 return True
def acquire(save_name:str)->Path:
 import os
 p=_busy_path(save_name)
 p.parent.mkdir(parents=True,exist_ok=True)
 try:
  fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
 except FileExistsError:
  try:
   holder=int(p.read_text().strip()or 0)
  except(OSError,ValueError):
   holder=0
  if _alive(holder)and holder!=os.getpid():
   raise SystemExit(f"another SWAM operation is working on '{save_name}' "f"(process {holder}). Wait for it to finish, or delete "f"{p} if that process is long gone")
  p.unlink(missing_ok=True)
  fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
 with os.fdopen(fd,"w")as f:
  f.write(str(os.getpid()))
 return p
def release(p:Path)->None:
 p.unlink(missing_ok=True)
class Transaction:
 def __init__(self,save_path:Path,operation:str,enabled:bool=True):
  self.save_path=save_path
  self.operation=operation
  self.enabled=enabled
  self.backup:Path|None=None
  self.busy:Path|None=None
 def __enter__(self):
  from.guard import ensure_game_closed
  ensure_game_closed()
  self.busy=acquire(self.save_path.name)
  try:
   if self.enabled:
    self.backup=make_backup(self.save_path,self.operation)
  except BaseException:
   release(self.busy)
   raise
  return self
 def __exit__(self,exc_type,exc,tb):
  try:
   if exc_type is not None and self.backup is not None:
    restore_backup(self.save_path,self.backup)
    print(f"error - save restored from backup {self.backup}")
  finally:
   if self.busy is not None:
    release(self.busy)
  return False
