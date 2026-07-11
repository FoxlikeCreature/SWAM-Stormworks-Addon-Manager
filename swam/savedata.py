import re
from pathlib import Path
from xml.sax.saxutils import unescape as _unescape
HEADER='<?xml version="1.0" encoding="UTF-8"?>\n'
def quoteattr(s:str)->str:
 return'"'+(s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;"))+'"'
def unescape(s:str)->str:
 return _unescape(s,{"&quot;":'"',"&#10;":"\n","&#9;":"\t","&#13;":"\r","&apos;":"'"})
def parse(text:str)->dict:
 m=re.search(r"<g_savedata>(.*)</g_savedata>",text,re.S)
 if not m:
  raise ValueError("no <g_savedata>")
 body,_=_parse_block(m.group(1))
 return body
def _parse_block(s:str)->tuple[dict,str]:
 out:dict={}
 var=re.search(r"<var/>|<var>(.*?)</var>",s,re.S)
 if var and var.group(1):
  for m in re.finditer(r"<v ([^>]*)/>",var.group(1)):
   attrs=dict(re.findall(r'(\w+)="([^"]*)"',m.group(1)))
   out[_key(attrs)]=_scalar(attrs)
 tbl_start=s.find("<table>")
 if tbl_start!=-1:
  inner=_extract(s,tbl_start,"table")
  pos=0
  while True:
   t=re.search(r"<t ([^>]*?)(/?)>",inner[pos:])
   if not t:
    break
   attrs=dict(re.findall(r'(\w+)="([^"]*)"',t.group(1)))
   key=_key(attrs)
   if t.group(2)=="/":
    out[key]={}
    pos+=t.end()
   else:
    sub=_extract(inner,pos+t.start(),"t")
    out[key],_=_parse_block(sub)
    pos=pos+t.start()+len(f"<t {t.group(1)}>")+len(sub)+len("</t>")
 return out,s
def _extract(s:str,open_at:int,tag:str)->str:
 start=s.index(">",open_at)+1
 if s[start-2]=="/":
  return""
 depth=1
 i=start
 tok_re=re.compile(rf"<{tag}(\s[^>]*)?>|</{tag}>")
 while depth:
  m=tok_re.search(s,i)
  if not m:
   raise ValueError(f"unbalanced <{tag}>")
  if m.group(0).startswith("</"):
   depth-=1
  elif not m.group(0).endswith("/>"):
   depth+=1
  i=m.end()
 return s[start:m.start()]
def _key(attrs:dict):
 name=attrs.get("name","")
 return int(name)if attrs.get("key_type")=="0"else unescape(name)
def _scalar(attrs:dict):
 v=attrs.get("value","")
 t=attrs.get("type")
 if t=="3":
  return v=="true"
 if t=="2":
  return unescape(v)
 return float(v)
def dump(data:dict)->str:
 return HEADER+"<g_savedata>\n"+_dump_block(data,1)+"</g_savedata>\n\n"
def _dump_block(d:dict,ind:int)->str:
 tabs="\t"*ind
 scalars={k:v for k,v in d.items()if not isinstance(v,dict)}
 tables={k:v for k,v in d.items()if isinstance(v,dict)}
 if scalars:
  var=tabs+"<var>\n"
  for k,v in scalars.items():
   var+=tabs+"\t"+_v_entry(k,v)+"\n"
  var+=tabs+"</var>\n"
 else:
  var=tabs+"<var/>\n"
 if tables:
  tbl=tabs+"<table>\n"
  for k,v in tables.items():
   ka=_key_attrs(k)
   tbl+=tabs+f"\t<t {ka}>\n"
   tbl+=_dump_block(v,ind+2)
   tbl+=tabs+"\t</t>\n"
  tbl+=tabs+"</table>\n"
 else:
  tbl=tabs+"<table/>\n"
 return var+tbl
def _key_attrs(k)->str:
 if isinstance(k,int):
  return f'key_type="0" name="{k}"'
 return f"name={quoteattr(str(k))}"
def _key_attrs_typed(k,t:str)->str:
 if isinstance(k,int):
  return f'key_type="0" type="{t}" name="{k}"'
 return f'type="{t}" name={quoteattr(str(k))}'
def _v_entry(k,v)->str:
 if isinstance(v,bool):
  return f'<v {_key_attrs_typed(k,"3")} value="{"true"if v else"false"}"/>'
 if isinstance(v,str):
  return f'<v {_key_attrs_typed(k,"2")} value={quoteattr(v)}/>'
 return f'<v {_key_attrs(k)} value="{_num(v)}"/>'
def _num(v)->str:
 f=float(v)
 return str(int(f))if f==int(f)else repr(f)
def load_file(path:Path)->dict:
 try:
  with open(path,encoding="utf-8",errors="strict",newline="")as f:
   return parse(f.read())
 except(ValueError,UnicodeDecodeError)as e:
  raise SystemExit(f"{path} is not readable as addon state ({e}).\nThe game probably ""crashed while writing it. Restore a backup of this save "f"(swam backups / swam restore), or delete the file if the addon ""may start from scratch")
def save_file(path:Path,data:dict)->None:
 tmp=path.with_suffix(".xml.swam-tmp")
 with open(tmp,"w",encoding="utf-8",newline="")as f:
  f.write(dump(data))
 tmp.replace(path)
