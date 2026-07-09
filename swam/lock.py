import hashlib
import json
import time
from pathlib import Path
from.paths import SWAM_DATA
def lock_path(save_name:str)->Path:
 return SWAM_DATA/"locks"/f"{save_name}.json"
def load(save_name:str)->dict:
 p=lock_path(save_name)
 if p.is_file():
  return json.loads(p.read_text(encoding="utf-8"))
 return{"version":1,"save":save_name,"addons":{}}
def store(save_name:str,data:dict)->None:
 p=lock_path(save_name)
 p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_suffix(".json.tmp")
 tmp.write_text(json.dumps(data,ensure_ascii=False,indent=1),encoding="utf-8")
 tmp.replace(p)
def file_hash(path:Path)->str:
 return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
def addon_record(name:str,playlist_value:str,scripted:bool,playlist_hash:str)->dict:
 return{"name":name,"playlist_value":playlist_value,"scripted":scripted,"playlist_hash":playlist_hash,"installed_at":time.strftime("%Y-%m-%d %H:%M:%S"),"script_id":None,"spawned":[],}
