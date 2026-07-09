import os
import subprocess
import sys
_PROC_NAMES=("stormworks64","stormworks")
def game_running()->bool:
 if sys.platform=="win32":
  try:
   out=subprocess.run(["tasklist","/FO","CSV","/NH"],capture_output=True,text=True,errors="ignore",timeout=10).stdout.lower()
   return any(name in out for name in _PROC_NAMES)
  except(OSError,subprocess.SubprocessError):
   return False
 try:
  for pid in os.listdir("/proc"):
   if not pid.isdigit():
    continue
   try:
    with open(f"/proc/{pid}/comm")as f:
     comm=f.read().strip().lower()
    if comm.startswith("stormworks"):
     return True
   except OSError:
    continue
 except OSError:
  pass
 return False
def ensure_game_closed()->None:
 if os.environ.get("SWAM_IGNORE_RUNNING")=="1":
  return
 if game_running():
  raise SystemExit("Stormworks is running - close the game first.\n""Edits made now would be overwritten the next time the game ""saves. (Override: SWAM_IGNORE_RUNNING=1)")
