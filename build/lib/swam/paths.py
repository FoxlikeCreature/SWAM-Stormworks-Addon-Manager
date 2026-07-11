import os
import re
import sys
from pathlib import Path
APP_ID=573090
IS_WINDOWS=sys.platform=="win32"
def _swam_data_dir()->Path:
 env=os.environ.get("SWAM_DATA_DIR")
 if env:
  return Path(env).expanduser()
 if IS_WINDOWS:
  base=os.environ.get("LOCALAPPDATA")
  if base:
   return Path(base)/"swam"
 return Path.home()/".local/share/swam"
SWAM_DATA=_swam_data_dir()
def steam_roots()->list[Path]:
 roots:list[Path]=[]
 if IS_WINDOWS:
  try:
   import winreg
   with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"SOFTWARE\WOW6432Node\Valve\Steam")as k:
    roots.append(Path(winreg.QueryValueEx(k,"InstallPath")[0]))
  except OSError:
   pass
  pf=os.environ.get("ProgramFiles(x86)",r"C:\Program Files (x86)")
  roots.append(Path(pf)/"Steam")
 else:
  home=Path.home()
  roots+=[home/".local/share/Steam",home/".steam/steam",home/".var/app/com.valvesoftware.Steam/.local/share/Steam",]
 return[r for i,r in enumerate(roots)if r.is_dir()and r not in roots[:i]]
def steam_libraries()->list[Path]:
 libs:list[Path]=[]
 for root in steam_roots():
  if root not in libs:
   libs.append(root)
  vdf=root/"steamapps"/"libraryfolders.vdf"
  if vdf.is_file():
   for m in re.finditer(r'"path"\s+"([^"]+)"',vdf.read_text(errors="replace")):
    p=Path(m.group(1).replace("\\\\","\\"))
    if p.is_dir()and p not in libs:
     libs.append(p)
 return libs
def _default_sw_root()->Path|None:
 if IS_WINDOWS:
  appdata=os.environ.get("APPDATA")
  if appdata and(Path(appdata)/"Stormworks").is_dir():
   return Path(appdata)/"Stormworks"
  return None
 for lib in steam_libraries():
  cand=(lib/"steamapps"/"compatdata"/str(APP_ID)/"pfx"/"drive_c"/"users"/"steamuser"/"Application Data"/"Stormworks")
  if cand.is_dir():
   return cand
 return None
def sw_root()->Path:
 env=os.environ.get("SWAM_SW_ROOT")
 if env:
  root=Path(env)
  if root.is_dir():
   return root
  raise SystemExit(f"SWAM_SW_ROOT points to a missing folder: {root}")
 root=_default_sw_root()
 if root is None:
  raise SystemExit("Stormworks data folder not found.\n""Set the SWAM_SW_ROOT environment variable to the folder that ""contains 'saves' and 'data'\n""(Windows: %APPDATA%\\Stormworks, Linux: inside the Proton prefix ""steamapps/compatdata/573090)")
 return root
def saves_dir()->Path:
 d=sw_root()/"saves"
 if not d.is_dir():
  raise SystemExit(f"no saves found: {d}\n""Has Stormworks been installed and run at least once on this ""computer? If the game lives in a non-standard place, set the ""SWAM_SW_ROOT environment variable.")
 return d
def save_dir(name:str)->Path:
 d=saves_dir()/name
 if not(d/"scene.xml").is_file():
  raise SystemExit(f"save not found or has no scene.xml: {d}")
 return d
def local_mods_dir()->Path:
 return sw_root()/"data"/"mods"
def workshop_dirs()->list[Path]:
 out=[]
 for lib in steam_libraries():
  d=lib/"steamapps"/"workshop"/"content"/str(APP_ID)
  if d.is_dir():
   out.append(d)
 return out
def find_workshop_item(item_id:str)->Path|None:
 for d in workshop_dirs():
  p=d/item_id
  if p.is_dir():
   return p
 return None
def game_path_string(path:Path)->str:
 if IS_WINDOWS:
  return str(path)
 return"Z:"+str(path).replace("/","\\")
def game_path_to_disk(game_path:str)->Path|None:
 norm=game_path.replace("\\","/")
 if IS_WINDOWS:
  return Path(norm)
 if norm[:2].upper()=="Z:":
  return Path(norm[2:])
 return None
def local_mod_game_path(mod_id:str)->str:
 if IS_WINDOWS:
  appdata=os.environ.get("APPDATA",r"C:\Users\?\AppData\Roaming")
  return f"{appdata}\\Stormworks\\data/mods/{mod_id}"
 return f"C:\\users\\steamuser\\AppData\\Roaming\\Stormworks\\data/mods/{mod_id}"
