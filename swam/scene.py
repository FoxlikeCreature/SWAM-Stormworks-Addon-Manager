import re
from pathlib import Path
class SceneError(SystemExit):
 pass
class Scene:
 def __init__(self,path:Path):
  self.path=path
  with open(path,encoding="utf-8",errors="strict",newline="")as f:
   self.text=f.read()
  self._orig=self.text
 @property
 def dirty(self)->bool:
  return self.text!=self._orig
 def _find_once(self,anchor:str,what:str)->int:
  first=self.text.find(anchor)
  if first==-1:
   raise SceneError(f"not found in scene.xml: {what}")
  if self.text.find(anchor,first+1)!=-1:
   raise SceneError(f"ambiguous anchor (occurs more than once): {what}")
  return first
 def list_mods(self)->list[str]:
  block=self._mods_block()
  return re.findall(r'<mod_path value="([^"]*)"/>',block)
 def _mods_block(self)->str:
  m=re.search(r"<active_mods>.*?</active_mods>|<active_mods/>",self.text,re.S)
  if not m:
   raise SceneError("<active_mods> section not found")
  return m.group(0)
 def add_mod(self,wine_path:str)->None:
  if wine_path in self.list_mods():
   raise SceneError(f"mod already attached: {wine_path}")
  entry=f'\t\t\t<mod_path value="{wine_path}"/>\n'
  if"<active_mods/>"in self.text:
   self._find_once("<active_mods/>","<active_mods/>")
   self.text=self.text.replace("<active_mods/>","<active_mods>\n"+entry+"\t\t</active_mods>",1)
  else:
   close="\t\t</active_mods>"
   self._find_once(close,"closing </active_mods>")
   self.text=self.text.replace(close,entry+close,1)
 def _collapse_if_empty(self,tag:str)->None:
  m=re.search(rf"<{tag}>\s*</{tag}>",self.text)
  if m:
   self.text=self.text[:m.start()]+f"<{tag}/>"+self.text[m.end():]
 def remove_mod(self,wine_path:str)->None:
  entry=f'\t\t\t<mod_path value="{wine_path}"/>\n'
  idx=self._find_once(entry,f"mod entry {wine_path}")
  self.text=self.text[:idx]+self.text[idx+len(entry):]
  self._collapse_if_empty("active_mods")
 def list_playlists(self)->list[str]:
  m=re.search(r"<active_playlists>.*?</active_playlists>",self.text,re.S)
  if not m:
   raise SceneError("<active_playlists> section not found")
  return re.findall(r'<playlist_name value="([^"]*)"/>',m.group(0))
 def add_playlist(self,value:str)->None:
  if value in self.list_playlists():
   raise SceneError(f"playlist already attached: {value}")
  close="\t\t</active_playlists>"
  self._find_once(close,"closing </active_playlists>")
  entry=f'\t\t\t<playlist_name value="{value}"/>\n'
  self.text=self.text.replace(close,entry+close,1)
 def remove_playlist(self,value:str)->None:
  entry=f'\t\t\t<playlist_name value="{value}"/>\n'
  idx=self._find_once(entry,f"playlist entry {value}")
  self.text=self.text[:idx]+self.text[idx+len(entry):]
 def list_scripts(self)->list[dict]:
  tail=self.text[self.text.rfind("<scripts>"):]
  out=[]
  for m in re.finditer(r'<s (?:script_id="(\d+)" )?store="(\d+)" path="([^"]+)"/>',tail):
   out.append({"script_id":int(m.group(1))if m.group(1)is not None else 0,"has_id":m.group(1)is not None,"store":int(m.group(2)),"path":m.group(3)})
  return out
 def next_script_id(self)->int:
  scripts=self.list_scripts()
  return max((s["script_id"]for s in scripts),default=-1)+1
 def add_script(self,path:str,store:int=4)->int:
  if any(s["path"]==path for s in self.list_scripts()):
   raise SceneError(f"script already attached: {path}")
  sid=self.next_script_id()
  close="\t\t</scripts>\n\t</scripts>"
  self._find_once(close,"closing tags of the scripts section")
  entry=f'\t\t\t<s script_id="{sid}" store="{store}" path="{path}"/>\n'
  self.text=self.text.replace(close,entry+close,1)
  return sid
 def remove_script(self,path:str)->int:
  recs=[s for s in self.list_scripts()if s["path"]==path]
  if not recs:
   raise SceneError(f"script not found: {path}")
  sid=recs[0]["script_id"]
  id_attr=f'script_id="{sid}" 'if recs[0]["has_id"]else""
  entry=(f'\t\t\t<s {id_attr}store="{recs[0]["store"]}" 'f'path="{path}"/>\n')
  idx=self._find_once(entry,f"<s> entry {path}")
  self.text=self.text[:idx]+self.text[idx+len(entry):]
  return sid
 def verify(self)->None:
  for tag in("active_mods","active_playlists","scripts","game_data","scene"):
   tags=re.findall(rf"<{tag}(?:\s[^>]*?)?(/?)>",self.text)
   opens=len([t for t in tags if t!="/"])
   closes=self.text.count(f"</{tag}>")
   if opens!=closes:
    raise SceneError(f"unbalanced <{tag}> tags: "f"{opens} opened, {closes} closed")
 def write(self)->None:
  self.verify()
  tmp=self.path.with_suffix(".xml.swam-tmp")
  with open(tmp,"w",encoding="utf-8",newline="")as f:
   f.write(self.text)
  tmp.replace(self.path)
 def diff(self)->str:
  import difflib
  return"".join(difflib.unified_diff(self._orig.splitlines(keepends=True),self.text.splitlines(keepends=True),fromfile="scene.xml (before)",tofile="scene.xml (after)",n=3))
