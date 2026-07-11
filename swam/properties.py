import re
from pathlib import Path
from.import paths,savedata
CALL_RE=re.compile(r"property\s*\.\s*(slider|checkbox|text)\s*\(")
class Prop:
 def __init__(self,kind,label,default,minimum=None,maximum=None,step=None):
  self.kind=kind
  self.label=label
  self.default=default
  self.minimum=minimum
  self.maximum=maximum
  self.step=step
  self.spans=[]
  self.saved_path=None
  self.saved_scale=1.0
  self.saved_value=None
 def clamp(self,value):
  if self.kind=="checkbox":
   if isinstance(value,str):
    return value.strip().lower()in("true","1","on","yes")
   return bool(value)
  if self.kind=="text":
   return str(value)
  try:
   v=float(value)
  except(TypeError,ValueError):
   raise SystemExit(f"'{self.label}' is a slider - it needs a number between "f"{_num(self.minimum)} and {_num(self.maximum)}, "f"not {value!r}")
  if self.step:
   v=self.minimum+round((v-self.minimum)/self.step)*self.step
  v=max(self.minimum,min(self.maximum,v))
  return round(v,10)
def _split_args(text:str,open_paren:int):
 depth,i,quote=1,open_paren+1,None
 start,spans=i,[]
 while i<len(text):
  c=text[i]
  if quote:
   if c=="\\":
    i+=1
   elif c==quote:
    quote=None
  elif c in"'\"":
   quote=c
  elif c in"([{":
   depth+=1
  elif c in")]}":
   depth-=1
   if depth==0:
    spans.append((start,i))
    return spans,i
  elif c==","and depth==1:
   spans.append((start,i))
   start=i+1
  i+=1
 return None,None
def _value(raw:str):
 s=raw.strip()
 if len(s)>=2 and s[0]in"'\""and s[-1]==s[0]:
  s=s[1:-1]
 low=s.strip().lower()
 if low=="true":
  return True
 if low=="false":
  return False
 try:
  return float(s)
 except ValueError:
  return s
def _num(v)->str:
 f=float(v)
 return str(int(f))if f==int(f)else repr(f)
def parse_schema(text:str)->list[Prop]:
 props:dict[str,Prop]={}
 for m in CALL_RE.finditer(text):
  open_paren=text.index("(",m.end()-1)
  spans,close=_split_args(text,open_paren)
  if spans is None or not spans:
   continue
  kind=m.group(1)
  args=[_value(text[a:b])for a,b in spans]
  label=args[0]
  if not isinstance(label,str):
   continue
  try:
   if kind=="slider":
    if len(args)>=5:
     mn,mx,st,df=args[1],args[2],args[3],args[4]
    elif len(args)==4:
     mn,mx,st,df=args[1],args[2],1.0,args[3]
    else:
     continue
    p=Prop("slider",label,float(df),float(mn),float(mx),float(st))
   elif kind=="checkbox":
    df=args[1]if len(args)>1 else False
    p=Prop("checkbox",label,df is True)
   else:
    p=Prop("text",label,str(args[1])if len(args)>1 else"")
  except(TypeError,ValueError):
   continue
  p=props.setdefault(label,p)
  if p.kind==kind:
   p.spans.append((m.start(),spans,close))
 _trace_savedata(text,props)
 return list(props.values())
def _call_span_at(props,pos):
 for p in props.values():
  for call_start,spans,close in p.spans:
   if call_start<=pos<=close:
    return p,call_start,close
 return None,None,None
def _var_names(text:str,props)->dict[str,tuple]:
 out={}
 for p in props.values():
  for call_start,spans,close in p.spans:
   head=text[:call_start]
   m=re.search(r"(?:local\s+)?([A-Za-z_]\w*)\s*=\s*$",head)
   if m and m.group(1)!="g_savedata":
    scale=_scale_after(text,close)
    out[m.group(1)]=(p,scale)
 return out
def _scale_after(text:str,close:int)->float:
 scale=1.0
 for f in re.match(r"(\s*\*\s*[\d.]+)*",text[close+1:]).group(0).split("*"):
  f=f.strip()
  if f:
   scale*=float(f)
 return scale
def _trace_savedata(text:str,props:dict)->None:
 m=re.search(r"g_savedata\s*=\s*{",text)
 if not m:
  return
 spans,close=_split_args(text,m.end()-1)
 if spans is None:
  return
 variables=_var_names(text,props)
 _trace_table(text,spans,(),variables,props,m.end())
def _trace_table(text,entry_spans,path,variables,props,table_start):
 index=0
 for a,b in entry_spans:
  entry=text[a:b]
  if not entry.strip():
   continue
  km=re.match(r'\s*(?:([A-Za-z_]\w*)|\[\s*"([^"]*)"\s*\])\s*=\s*',entry)
  if km:
   key=km.group(1)or km.group(2)
   expr_at=a+km.end()
  else:
   index+=1
   key,expr_at=index,a+len(entry)-len(entry.lstrip())
  expr=text[expr_at:b].strip()
  tm=re.match(r"{",expr)
  if tm:
   sub_spans,_=_split_args(text,expr_at+expr.index("{"))
   if sub_spans:
    _trace_table(text,sub_spans,path+(key,),variables,props,expr_at)
   continue
  p,call_start,close=_call_span_at(props,expr_at)
  if p and expr_at<=call_start<b:
   p.saved_path=path+(key,)
   p.saved_scale=_scale_after(text,close)
   continue
  vm=re.match(r"([A-Za-z_]\w*)((?:\s*\*\s*[\d.]+)*)\s*$",expr)
  if vm and vm.group(1)in variables:
   p,scale=variables[vm.group(1)]
   for f in vm.group(2).split("*"):
    f=f.strip()
    if f:
     scale*=float(f)
   p.saved_path=path+(key,)
   p.saved_scale=scale
def _default_edits(text:str,p:Prop,value)->list[tuple]:
 edits=[]
 for call_start,spans,close in p.spans:
  a,b=spans[-1]
  raw=text[a:b]
  bare=raw.strip()
  quoted=bare[:1]in"'\""
  if p.kind=="checkbox":
   new="true"if value else"false"
  elif p.kind=="text":
   new=str(value).replace("\\","\\\\").replace('"','\\"')
   quoted=True
  else:
   new=_num(value)
  if quoted:
   q=bare[0]if bare[:1]in"'\""else'"'
   new=q+new+q
  pad_l=raw[:len(raw)-len(raw.lstrip())]
  edits.append((a,b,pad_l+new))
 return edits
def _apply_edits(text:str,edits:list[tuple])->str:
 for a,b,new in sorted(edits,key=lambda e:e[0],reverse=True):
  text=text[:a]+new+text[b:]
 return text
def _rewrite_default(text:str,p:Prop,value)->str:
 return _apply_edits(text,_default_edits(text,p,value))
def local_script(addon_name:str)->Path:
 p=paths.sw_root()/"data"/"missions"/addon_name/"script.lua"
 if not p.is_file():
  raise SystemExit(f"no local copy of '{addon_name}' (data/missions) - settings can ""only be edited on addons whose files live there. Addons attached ""straight from the workshop folder keep their files read-only ""under Steam's control")
 return p
def read(save:Path,addon_name:str,scene)->list[Prop]:
 script=local_script(addon_name)
 text=script.read_text(encoding="utf-8",errors="replace")
 props=parse_schema(text)
 if not props:
  return props
 sid=_script_id(scene,addon_name)
 if sid is not None:
  sd=save/"script_data"/f"{sid}.xml"
  if sd.is_file():
   data=savedata.load_file(sd)
   for p in props:
    if p.saved_path is None:
     continue
    node=data
    for key in p.saved_path:
     if not isinstance(node,dict)or key not in node:
      node=None
      break
     node=node[key]
    if isinstance(node,(int,float))and p.kind=="slider":
     p.saved_value=node/p.saved_scale
    elif isinstance(node,bool)and p.kind=="checkbox":
     p.saved_value=node
    elif isinstance(node,str)and p.kind=="text":
     p.saved_value=node
 return props
def _script_id(scene,addon_name:str):
 target=f"data/missions/{addon_name}"
 for s in scene.list_scripts():
  if s["path"]==target:
   return s["script_id"]
 return None
def apply(save:Path,addon_name:str,scene,changes:dict[str,object])->tuple[list[str],dict]:
 script=local_script(addon_name)
 text=script.read_text(encoding="utf-8",errors="replace")
 props={p.label:p for p in parse_schema(text)}
 report=[]
 unknown=[k for k in changes if k not in props]
 if unknown:
  raise SystemExit("no such setting: "+"; ".join(unknown))
 sid=_script_id(scene,addon_name)
 sd=save/"script_data"/f"{sid}.xml"if sid is not None else None
 data=savedata.load_file(sd)if sd and sd.is_file()else None
 stored=0
 applied={}
 edits=[]
 for label,raw in changes.items():
  p=props[label]
  value=p.clamp(raw)
  applied[label]=value
  edits+=_default_edits(text,p,value)
  if data is not None and p.saved_path is not None:
   node=data
   for key in p.saved_path[:-1]:
    if not isinstance(node.get(key),dict):
     node=None
     break
    node=node[key]
   if node is not None and p.saved_path[-1]in node:
    node[p.saved_path[-1]]=(value*p.saved_scale if p.kind=="slider"else value)
    stored+=1
    continue
  report.append(f"'{label}': stored addon state not located - the new "f"value takes effect where the addon reads it fresh "f"(fresh installs always do)")
 original=script.read_bytes()
 text=_apply_edits(text,edits)
 try:
  with open(script,"w",encoding="utf-8",newline="")as f:
   f.write(text)
  report.insert(0,f"defaults updated in {script}")
  if stored and data is not None:
   savedata.save_file(sd,data)
   report.insert(1,f"{stored} value(s) updated in this save's state "f"({sd.name})")
 except BaseException:
  script.write_bytes(original)
  raise
 return report,applied
