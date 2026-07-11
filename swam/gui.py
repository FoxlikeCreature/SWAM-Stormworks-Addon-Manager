import contextlib
import io
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,ttk
from.import addons,catalog,companion,lock,mods,paths,properties,verify
from.backup import Transaction
from.scene import Scene
BG="#2a2a2e"
PANEL="#323237"
FIELD="#3a3a40"
FG="#e8e8ec"
MUTED="#9a9aa3"
ACCENT="#b44dff"
ACCENT_DIM="#8f3fd1"
ACCENT_SOFT="#4b2a66"
def apply_theme(root:tk.Tk)->None:
 style=ttk.Style(root)
 try:
  style.theme_use("clam")
 except tk.TclError:
  return
 root.configure(bg=BG)
 style.configure(".",background=BG,foreground=FG,fieldbackground=FIELD,troughcolor=PANEL,bordercolor=PANEL,lightcolor=BG,darkcolor=BG,focuscolor=ACCENT,selectbackground=ACCENT_SOFT,selectforeground=FG)
 style.configure("TButton",background=PANEL,foreground=FG,padding=(10,5),borderwidth=0)
 style.map("TButton",background=[("disabled",BG),("pressed",ACCENT_DIM),("active",ACCENT)],foreground=[("disabled",MUTED),("active","#ffffff")])
 style.configure("TCombobox",arrowcolor=ACCENT,padding=4)
 style.map("TCombobox",fieldbackground=[("readonly",FIELD)],foreground=[("readonly",FG)])
 root.option_add("*TCombobox*Listbox.background",PANEL)
 root.option_add("*TCombobox*Listbox.foreground",FG)
 root.option_add("*TCombobox*Listbox.selectBackground",ACCENT)
 root.option_add("*TCombobox*Listbox.selectForeground","#ffffff")
 root.option_add("*TCombobox*Listbox.borderWidth",0)
 root.option_add("*TCombobox*Listbox.highlightThickness",0)
 root.option_add("*TCombobox*Listbox.selectBorderWidth",0)
 root.option_add("*TCombobox*Listbox.activeStyle","none")
 style.configure("ComboboxPopdownFrame",background=PANEL,borderwidth=0,relief="flat")
 root.bind_class("TCombobox","<<ComboboxSelected>>",lambda e:e.widget.selection_clear(),add="+")
 root.bind_class("TCombobox","<FocusOut>",lambda e:e.widget.selection_clear(),add="+")
 style.configure("TEntry",padding=4,insertcolor=FG)
 style.configure("Treeview",background=PANEL,fieldbackground=PANEL,foreground=FG,rowheight=24,borderwidth=0)
 style.map("Treeview",background=[("selected",ACCENT)],foreground=[("selected","#ffffff")])
 style.configure("Treeview.Heading",background=BG,foreground=ACCENT,borderwidth=0,font=("TkDefaultFont",10,"bold"))
 style.map("Treeview.Heading",background=[("active",PANEL)])
 style.configure("Vertical.TScrollbar",background=ACCENT,troughcolor=PANEL,bordercolor=PANEL,lightcolor=ACCENT_DIM,darkcolor=ACCENT_DIM,gripcount=0,arrowcolor="#ffffff",borderwidth=0)
 style.map("Vertical.TScrollbar",background=[("pressed",ACCENT_DIM),("active",ACCENT)],lightcolor=[("pressed",ACCENT_DIM)],darkcolor=[("pressed",ACCENT_DIM)])
 style.configure("TNotebook",background=BG,borderwidth=0)
 style.configure("TNotebook.Tab",background=PANEL,foreground=MUTED,padding=(14,6),borderwidth=0)
 style.map("TNotebook.Tab",background=[("selected",ACCENT),("active",ACCENT_DIM)],foreground=[("selected","#ffffff"),("active","#ffffff")])
 style.configure("Muted.TLabel",foreground=MUTED)
 style.configure("Accent.TLabel",foreground=ACCENT,font=("TkDefaultFont",10,"bold"))
 style.configure("Good.TLabel",foreground="#4ade80",font=("TkDefaultFont",10,"bold"))
 style.configure("Bad.TLabel",foreground="#f87171",font=("TkDefaultFont",10,"bold"))
 style.configure("Accent.TButton",background=ACCENT,foreground="#ffffff",padding=(10,5),borderwidth=0)
 style.map("Accent.TButton",background=[("pressed",ACCENT_DIM),("active","#c86bff")])
def theme_popdown(cb:ttk.Combobox)->None:
 try:
  popdown=cb.tk.call("ttk::combobox::PopdownWindow",cb)
  cb.tk.call(str(popdown),"configure","-background",PANEL)
 except tk.TclError:
  pass
class Picker(tk.Toplevel):
 TILE_W=148
 THUMB_W=128
 COLS=4
 def __init__(self,root,kind:str,attached:set[str]):
  super().__init__(root)
  self.kind=kind
  self.attached=attached
  self.result:list[str]=[]
  self.selected:list[str]=[]
  self._tile_btns:dict[str,tk.Button]={}
  self._images:list[tk.PhotoImage]=[]
  self._built:set[str]=set()
  self.title("Add addon"if kind=="addon"else"Add mod")
  self.configure(bg=BG)
  self.geometry("700x560")
  self.transient(root)
  self.grab_set()
  items=catalog.addons()if kind=="addon"else catalog.mods()
  self.by_source:dict[str,list[catalog.Item]]={}
  for it in items:
   if it.name==companion.NAME:
    continue
   if it.source=="local"and(it.name in attached or it.ident in attached):
    continue
   self.by_source.setdefault(it.source,[]).append(it)
  bar=ttk.Frame(self,padding=(8,8,8,0))
  bar.pack(fill="x")
  self.sort_var=tk.StringVar(value="Newest first")
  sort_box=ttk.Combobox(bar,textvariable=self.sort_var,state="readonly",width=12,values=("Newest first","A-Z"))
  sort_box.pack(side="right")
  ttk.Label(bar,text="Sort:",style="Muted.TLabel").pack(side="right",padx=(0,4))
  sort_box.bind("<<ComboboxSelected>>",lambda e:self._rebuild())
  theme_popdown(sort_box)
  self.nb=ttk.Notebook(self)
  self.nb.pack(fill="both",expand=True,padx=8,pady=8)
  self.tabs:dict[str,tuple]={}
  for source,label in(("workshop","Workshop"),("local","Local"),("builtin","Built-in")):
   if source in self.by_source:
    self._make_tab(source,f"{label} ({len(self.by_source[source])})")
  self.nb.bind("<<NotebookTabChanged>>",lambda e:self._fill_current())
  manual=ttk.Frame(self,padding=(8,0,8,8))
  manual.pack(fill="x")
  ttk.Label(manual,text="Click tiles to select. Type to search, ""or enter a workshop id/path:",style="Muted.TLabel").pack(anchor="w")
  row=ttk.Frame(manual)
  row.pack(fill="x",pady=(2,0))
  self.var=tk.StringVar()
  self.var.trace_add("write",lambda*_:self._search_changed())
  self._search_job=None
  entry=ttk.Entry(row,textvariable=self.var)
  entry.pack(side="left",fill="x",expand=True)
  ttk.Button(row,text="Browse…",command=self._browse).pack(side="left",padx=(6,0))
  verb="Add"if kind=="addon"else"Add"
  self.confirm_btn=ttk.Button(row,text=f"{verb} selected (0)",style="Accent.TButton",command=self._confirm)
  self.confirm_btn.pack(side="left",padx=(6,0))
  self.confirm_btn.state(["disabled"])
  ttk.Button(row,text="Cancel",command=self.destroy).pack(side="left",padx=(6,0))
  entry.bind("<Return>",lambda e:self._confirm())
  self._fill_current()
  self.wait_window()
 def _search_changed(self):
  if self._search_job:
   self.after_cancel(self._search_job)
  self._search_job=self.after(200,self._rebuild)
  n=len(self.selected)
  self.confirm_btn.state(["!disabled"]if n or self.var.get().strip()else["disabled"])
 def _rebuild(self):
  self._search_job=None
  self._built.clear()
  self._fill_current()
 MAX_TILES=400
 def _visible_items(self,source:str)->list:
  items=self.by_source[source]
  query=self.var.get().strip().lower()
  if query:
   items=[i for i in items if query in i.name.lower()or query in i.ident.lower()]
  if self.sort_var.get()=="A-Z":
   items=sorted(items,key=lambda i:i.name.lower())
  else:
   items=sorted(items,key=lambda i:i.mtime,reverse=True)
  return items[:self.MAX_TILES]
 def _make_tab(self,source:str,label:str):
  outer=ttk.Frame(self.nb)
  self.nb.add(outer,text=label)
  canvas=tk.Canvas(outer,bg=BG,highlightthickness=0)
  vsb=ttk.Scrollbar(outer,orient="vertical",command=canvas.yview)
  inner=ttk.Frame(canvas)
  inner_id=canvas.create_window((0,0),window=inner,anchor="nw")
  canvas.configure(yscrollcommand=vsb.set)
  canvas.pack(side="left",fill="both",expand=True)
  vsb.pack(side="left",fill="y")
  inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
  canvas.bind("<Configure>",lambda e:canvas.itemconfigure(inner_id,width=e.width))
  canvas.bind_all("<Button-4>",lambda e:self._wheel(canvas,-1),add=True)
  canvas.bind_all("<Button-5>",lambda e:self._wheel(canvas,1),add=True)
  canvas.bind_all("<MouseWheel>",lambda e:self._wheel(canvas,-1 if e.delta>0 else 1),add=True)
  self.tabs[source]=(outer,inner,canvas)
 def _wheel(self,canvas,direction):
  if canvas.winfo_exists():
   canvas.yview_scroll(direction*2,"units")
 def _fill_current(self):
  idx=self.nb.index("current")if self.nb.tabs()else None
  if idx is None:
   return
  for source,(outer,inner,_c)in self.tabs.items():
   if str(outer)==self.nb.tabs()[idx]and source not in self._built:
    self._built.add(source)
    self._fill_grid(source,inner)
 def _fill_grid(self,source:str,inner:ttk.Frame):
  for w in inner.winfo_children():
   w.destroy()
  for col in range(self.COLS):
   inner.columnconfigure(col,weight=1)
  for i,it in enumerate(self._visible_items(source)):
   thumb=self._thumbnail(it.image)
   is_attached=it.name in self.attached or it.ident in self.attached
   text=it.name if len(it.name)<=40 else it.name[:38]+"…"
   if is_attached:
    text+="\n(already attached)"
   picked=it.ident in self.selected
   btn=tk.Button(inner,image=thumb,text=text,compound="top",wraplength=self.TILE_W-12,justify="center",bg=(ACCENT if picked else PANEL),fg=("#ffffff"if picked else(MUTED if is_attached else FG)),activebackground=ACCENT_SOFT,activeforeground="#ffffff",relief="flat",bd=0,padx=4,pady=6,cursor="hand2",state=("disabled"if is_attached else"normal"),disabledforeground=MUTED,command=lambda ident=it.ident:self._toggle(ident))
   btn.grid(row=i//self.COLS,column=i%self.COLS,padx=4,pady=4,sticky="nsew")
   self._tile_btns[it.ident]=btn
  self.update_idletasks()
 def _thumbnail(self,image:Path|None)->tk.PhotoImage:
  key=str(image)if image else"__placeholder__"
  if not hasattr(self,"_thumb_cache"):
   self._thumb_cache:dict[str,tk.PhotoImage]={}
  if key in self._thumb_cache:
   return self._thumb_cache[key]
  img=None
  if image is not None:
   try:
    img=tk.PhotoImage(file=str(image))
    factor=max(1,-(-img.width()//self.THUMB_W))
    if factor>1:
     img=img.subsample(factor,factor)
   except tk.TclError:
    img=None
  if img is None:
   img=self._placeholder()
  self._thumb_cache[key]=img
  self._images.append(img)
  return img
 def _placeholder(self)->tk.PhotoImage:
  w,h=self.THUMB_W,72
  ph=tk.PhotoImage(width=w,height=h)
  ph.put(FIELD,to=(0,0,w,h))
  cx,cy,r=w//2,h//2,14
  for dy in range(-r,r+1):
   half=r-abs(dy)
   ph.put(ACCENT,to=(cx-half,cy+dy,cx+half+1,cy+dy+1))
  r2=5
  for dy in range(-r2,r2+1):
   half=r2-abs(dy)
   ph.put(FIELD,to=(cx-half,cy+dy,cx+half+1,cy+dy+1))
  return ph
 def _toggle(self,ident:str):
  if ident in self.selected:
   self.selected.remove(ident)
  else:
   self.selected.append(ident)
  btn=self._tile_btns.get(ident)
  if btn is not None and btn.winfo_exists():
   on=ident in self.selected
   btn.configure(bg=ACCENT if on else PANEL,fg="#ffffff"if on else FG)
  n=len(self.selected)
  self.confirm_btn.configure(text=f"Add selected ({n})")
  self.confirm_btn.state(["!disabled"]if n or self.var.get().strip()else["disabled"])
 def _browse(self):
  d=filedialog.askdirectory(parent=self)
  if d:
   self.var.set(d)
 def _confirm(self):
  manual=self.var.get().strip()
  picked=list(self.selected)
  if manual and not picked:
   self.result=[manual]
  else:
   self.result=picked
  if self.result:
   self.destroy()
class App(ttk.Frame):
 def __init__(self,root:tk.Tk):
  super().__init__(root,padding=8)
  self.root=root
  root.title("SWAM - Stormworks Addon Manager")
  root.geometry("860x640")
  root.minsize(700,500)
  self.pack(fill="both",expand=True)
  self.log_queue:queue.Queue[str]=queue.Queue()
  self._updates_queue:queue.Queue[tuple]=queue.Queue()
  self.busy=False
  self._build()
  self._poll_log()
  self.refresh_saves()
 def _build(self):
  top=ttk.Frame(self)
  top.pack(fill="x")
  ttk.Label(top,text="Save:").pack(side="left")
  self.save_var=tk.StringVar()
  self.save_box=ttk.Combobox(top,textvariable=self.save_var,state="readonly",width=40)
  self.save_box.pack(side="left",padx=6)
  self.save_box.bind("<<ComboboxSelected>>",lambda e:self.refresh_items())
  theme_popdown(self.save_box)
  ttk.Button(top,text="Refresh",command=self.refresh_saves).pack(side="left")
  self.companion_lbl=ttk.Label(top,text="",style="Accent.TLabel")
  self.companion_lbl.pack(side="right")
  mid=ttk.Frame(self)
  mid.pack(fill="both",expand=True,pady=(8,0))
  cols=("kind","name","details")
  self.tree=ttk.Treeview(mid,columns=cols,show="headings",selectmode="extended")
  self.tree.heading("kind",text="Type")
  self.tree.heading("name",text="Name")
  self.tree.heading("details",text="Details")
  self.tree.column("kind",width=90,stretch=False)
  self.tree.column("name",width=380)
  self.tree.column("details",width=260)
  vsb=ttk.Scrollbar(mid,orient="vertical",command=self.tree.yview)
  self.tree.configure(yscrollcommand=vsb.set)
  self.tree.pack(side="left",fill="both",expand=True)
  vsb.pack(side="left",fill="y")
  self.tree.tag_configure("builtin",foreground="#9d8fc7")
  self.tree.tag_configure("companion",foreground="#4ade80")
  self.tree.tag_configure("update",foreground="#ffb454")
  self._update_check_running=False
  btns=ttk.Frame(self)
  btns.pack(fill="x",pady=8)
  self.buttons=[]
  for text,cmd in(("Add addon…",self.add_addon),("Add mod…",self.add_mod),("Remove selected",self.remove_selected),("Upgrade selected",self.upgrade_selected),("Settings…",self.addon_settings),("Remove marked…",self.remove_marked),("Install companion",self.install_companion),("Check integrity",self.run_verify),("Restore backup…",self.restore_backup)):
   b=ttk.Button(btns,text=text,command=cmd)
   b.pack(side="left",padx=(0,6))
   self.buttons.append(b)
  ttk.Label(self,text="Log:").pack(anchor="w")
  self.log=tk.Text(self,height=10,state="disabled",wrap="word",bg=PANEL,fg=FG,insertbackground=FG,selectbackground=ACCENT,relief="flat",highlightthickness=0)
  self.log.pack(fill="both",expand=False)
 def log_line(self,text:str):
  self.log.configure(state="normal")
  self.log.insert("end",text+"\n")
  self.log.see("end")
  self.log.configure(state="disabled")
 def _poll_log(self):
  try:
   while True:
    self.log_line(self.log_queue.get_nowait())
  except queue.Empty:
   pass
  try:
   while True:
    save_name,found=self._updates_queue.get_nowait()
    self._apply_updates(save_name,found)
  except queue.Empty:
   pass
  self.root.after(100,self._poll_log)
 def current_save(self)->str|None:
  s=self.save_var.get()
  return s or None
 def run_op(self,label,fn,done=None):
  if self.busy:
   messagebox.showinfo("SWAM","Another operation is still running")
   return
  self.busy=True
  for b in self.buttons:
   b.state(["disabled"])
  self.log_queue.put(f"--- {label} ---")
  def work():
   buf=io.StringIO()
   ok=True
   try:
    with contextlib.redirect_stdout(buf):
     fn()
   except SystemExit as e:
    ok=False
    if e.code not in(0,None):
     buf.write(f"refused: {e}\n")
   except Exception as e:
    ok=False
    buf.write(f"error: {e}\n")
   for line in buf.getvalue().splitlines():
    self.log_queue.put(line)
   self.root.after(0,lambda:self._op_done(ok,done))
  threading.Thread(target=work,daemon=True).start()
 def _op_done(self,ok,done):
  self.busy=False
  for b in self.buttons:
   b.state(["!disabled"])
  self.refresh_items()
  if ok and done:
   done()
 def _two_buttons(self,title:str,text:str,primary:str,secondary:str)->bool:
  dlg=tk.Toplevel(self.root)
  dlg.title(title)
  dlg.configure(bg=BG)
  dlg.transient(self.root)
  dlg.grab_set()
  dlg.resizable(False,False)
  ttk.Label(dlg,text=text,padding=16,wraplength=420,justify="left").pack()
  row=ttk.Frame(dlg,padding=(16,0,16,12))
  row.pack(fill="x")
  pressed=[]
  ttk.Button(row,text=secondary,command=lambda:(pressed.append(True),dlg.destroy())).pack(side="right")
  ttk.Button(row,text=primary,style="Accent.TButton",command=dlg.destroy).pack(side="right",padx=(0,8))
  dlg.bind("<Escape>",lambda e:dlg.destroy())
  dlg.wait_window()
  return bool(pressed)
 def _needs_game_note(self):
  messagebox.showinfo("SWAM","Task queued for the in-game companion.\n\n""Now load this save in Stormworks, wait for the ""\"[SWAM] tasks done\" chat message, then SAVE the game.")
 def refresh_saves(self):
  try:
   saves=[d.name for d in sorted(paths.saves_dir().iterdir())if(d/"scene.xml").is_file()]
  except(SystemExit,OSError)as e:
   self.log_line(str(e))
   messagebox.showwarning("SWAM",str(e))
   saves=[]
  self.save_box["values"]=saves
  if saves and self.save_var.get()not in saves:
   self.save_var.set(saves[0])
  self.refresh_items()
 def refresh_items(self):
  self.tree.delete(*self.tree.get_children())
  name=self.current_save()
  if not name:
   return
  try:
   save=paths.save_dir(name)
   scene=Scene(save/"scene.xml")
   addons.backfill(name)
   lk=lock.load(name)
  except(SystemExit,OSError,ValueError)as e:
   self.log_line(str(e))
   return
  managed=set(lk["addons"])
  for w in scene.list_mods():
   desc=mods.describe_wine_path(w)
   self.tree.insert("","end",values=("mod",desc,""),tags=("mod",w))
  scripted_paths={s["path"]for s in scene.list_scripts()}
  for v in scene.list_playlists():
   if v.startswith("rom/data/missions/"):
    continue
   aname=addons.playlist_name(v)
   if aname is None:
    self.tree.insert("","end",values=("addon",v,"files not found on disk"),tags=("addon",v))
    continue
   if aname==companion.NAME:
    self.tree.insert("","end",values=("addon",aname,"keeps the journal"),tags=("companion",aname))
    continue
   marks=[]
   if v in scripted_paths:
    marks.append("scripted")
   if not v.startswith("data/missions/"):
    marks.append("straight from the workshop")
   marks.append("installed by SWAM"if aname in managed else"inherited")
   self.tree.insert("","end",values=("addon",aname,", ".join(marks)),tags=("addon",aname))
  for v in scene.list_playlists():
   if v.startswith("rom/data/missions/"):
    aname=v.rsplit("/",1)[-1]
    self.tree.insert("","end",values=("addon",aname,"built-in (vanilla)"),tags=("builtin",aname))
  comp=companion.is_installed(scene)
  self.companion_lbl.configure(text="companion: installed"if comp else"companion: NOT installed",style="Good.TLabel"if comp else"Bad.TLabel")
  self._check_updates_async(name,dict(lk["addons"]))
 def _check_updates_async(self,save_name:str,managed:dict):
  if self._update_check_running or not managed:
   return
  self._update_check_running=True
  def work():
   found=[]
   try:
    addons.workshop_index(refresh=True)
   except Exception:
    pass
   for aname,rec in managed.items():
    try:
     if addons.update_available(rec,aname):
      found.append((aname,"update available"))
     elif addons.local_changed(rec,aname):
      found.append((aname,"local edits - upgrade to apply"))
    except Exception:
     pass
   self._updates_queue.put((save_name,found))
  threading.Thread(target=work,daemon=True).start()
 def _apply_updates(self,save_name:str,names:list):
  self._update_check_running=False
  if self.current_save()!=save_name:
   return
  labels=dict(names)
  for iid in self.tree.get_children():
   tags=self.tree.item(iid,"tags")
   if len(tags)>=2 and tags[0]=="addon"and tags[1]in labels:
    vals=list(self.tree.item(iid,"values"))
    if labels[tags[1]]not in vals[2]:
     vals[2]+=f" - {labels[tags[1]]}"
    self.tree.item(iid,values=vals,tags=(*tags,"update"))
 def _remove_batch(self,save:str,sel):
  mods_,managed_,inherited_,skipped=[],[],[],[]
  lk=lock.load(save)
  for iid in sel:
   kind,ident=self.tree.item(iid,"tags")[:2]
   if kind=="mod":
    mods_.append(ident)
   elif kind=="addon":
    (managed_ if ident in lk["addons"]else inherited_).append(ident)
   else:
    skipped.append(ident)
  lines=[]
  if mods_:
   lines.append(f"{len(mods_)} mod(s)")
  if managed_:
   lines.append(f"{len(managed_)} addon(s) installed by SWAM")
  if inherited_:
   lines.append(f"{len(inherited_)} inherited addon(s)")
  if not lines:
   messagebox.showinfo("SWAM","Nothing removable selected.")
   return
  if not messagebox.askyesno("SWAM","Remove "+", ".join(lines)+"?"):
   return
  force=False
  if inherited_:
   force=messagebox.askyesno("SWAM",f"{len(inherited_)} of those came with the world "f"(inherited). Their entries can be removed, but structures "f"spawned at world creation stay.\n\nRemove them too?")
   if not force:
    inherited_=[]
  def op():
   from.cli import cmd_remove_addon,cmd_remove_mod
   for s in skipped:
    print(f"skipped (companion/built-in): {s}")
   self._batch(mods_,lambda i:cmd_remove_mod(_Args(save=save,mod=i.replace("\\","/").rsplit("/",1)[-1],dry_run=False,no_backup=False)))
   self._batch(managed_,lambda i:cmd_remove_addon(_Args(save=save,addon=i,dry_run=False,no_backup=False,force=False,force_geometry=False)))
   self._batch(inherited_,lambda i:cmd_remove_addon(_Args(save=save,addon=i,dry_run=False,no_backup=False,force=True,force_geometry=False)))
  self.run_op(f"remove {len(mods_)+len(managed_)+len(inherited_)} "f"item(s)",op,done=self._needs_game_note if(managed_ or inherited_)else None)
 def upgrade_selected(self):
  save=self.current_save()
  sel=self.tree.selection()
  if not save or not sel:
   return
  tags=self.tree.item(sel[0],"tags")
  kind,ident=tags[:2]
  if kind!="addon":
   messagebox.showinfo("SWAM","Select an addon installed by SWAM to refresh it from the ""workshop or from its edited local files.")
   return
  rec=lock.load(save)["addons"].get(ident)
  if rec is None:
   messagebox.showinfo("SWAM",f"'{ident}' was not installed by SWAM - upgrades "f"only work for addons it manages.")
   return
  try:
   ws_update=addons.update_available(rec,ident)
   local_changed=addons.local_changed(rec,ident)
   has_workshop=addons.workshop_source(rec,ident)is not None
  except Exception:
   ws_update,local_changed,has_workshop=True,False,True
  use_local=False
  if ws_update and local_changed:
   ans=messagebox.askyesnocancel("SWAM",f"'{ident}' has manual edits in data/missions AND a newer "f"workshop version.\n\n"f"Yes - keep your edits, refresh the save from them\n"f"No - discard the edits, take the workshop version")
   if ans is None:
    return
   use_local=ans
  elif local_changed:
   if has_workshop:
    ans=messagebox.askyesnocancel("SWAM",f"'{ident}' has manual edits in data/missions.\n\n"f"Yes - refresh the save from your edited files\n"f"No - discard the edits, restore the workshop version")
    if ans is None:
     return
    use_local=ans
   else:
    if not messagebox.askyesno("SWAM",f"Refresh '{ident}' from its edited local files?\n\n"f"On next world load the old structures are removed and "f"the ones from your edited files spawned."):
     return
    use_local=True
  else:
   if not messagebox.askyesno("SWAM",f"Upgrade '{ident}' from its workshop version?\n\n"f"On next world load the old structures are removed and "f"the new ones spawned."):
    return
  def op():
   from.cli import cmd_upgrade_addon
   cmd_upgrade_addon(_Args(save=save,addon=ident,dry_run=False,no_backup=False,local=use_local,discard_local=not use_local))
  self.run_op(f"upgrade addon {ident}",op,done=self._needs_game_note)
 def remove_marked(self):
  save=self.current_save()
  if not save:
   return
  try:
   save_dir=paths.save_dir(save)
   sid=companion.script_id(Scene(save_dir/"scene.xml"))
   marks=companion.load_data(save_dir,sid).get("marks")or{}if sid is not None else{}
  except(SystemExit,OSError,ValueError)as e:
   messagebox.showinfo("SWAM",str(e))
   return
  if not marks:
   messagebox.showinfo("SWAM",'No structures are marked in this save.\n\nIn game, stand next to the structure you want gone, type ''"?swam mark" in chat, SAVE the game and close it - then use ''this button.')
   return
  ans=messagebox.askyesnocancel("SWAM",f'{len(marks)} structure(s) marked in game.\n\n''Also remove every IDENTICAL structure anywhere on the map?\n\n''Yes - marked + all identical copies\n''No - only the marked ones')
  if ans is None:
   return
  def op():
   from.cli import cmd_remove_marked
   cmd_remove_marked(_Args(save=save,all=bool(ans),dry_run=False,no_backup=False))
  self.run_op("remove marked",op,done=self._needs_game_note)
 def addon_settings(self):
  save=self.current_save()
  sel=self.tree.selection()
  if not save or not sel:
   messagebox.showinfo("SWAM","Select an addon to edit its settings.")
   return
  tags=self.tree.item(sel[0],"tags")
  kind,aname=tags[:2]
  if kind=="builtin":
   messagebox.showinfo("SWAM","Built-in (vanilla) addons keep their files inside the game ""installation, which SWAM does not modify - their settings ""cannot be edited.")
   return
  if kind not in("addon","companion"):
   messagebox.showinfo("SWAM","Settings exist only for addons.")
   return
  try:
   save_dir=paths.save_dir(save)
   scene=Scene(save_dir/"scene.xml")
   props=properties.read(save_dir,aname,scene)
  except SystemExit as e:
   messagebox.showinfo("SWAM",str(e))
   return
  if not props:
   messagebox.showinfo("SWAM",f"'{aname}' exposes no settings (its script defines "f"no property sliders or checkboxes).")
   return
  self._settings_dialog(save,aname,props)
 def _settings_dialog(self,save:str,aname:str,props):
  dlg=tk.Toplevel(self.root)
  dlg.title(f"Settings - {aname}")
  dlg.configure(bg=BG)
  dlg.transient(self.root)
  dlg.grab_set()
  dlg.geometry("640x520")
  dlg.minsize(520,320)
  canvas=tk.Canvas(dlg,bg=BG,highlightthickness=0)
  vsb=ttk.Scrollbar(dlg,orient="vertical",command=canvas.yview)
  inner=ttk.Frame(canvas,padding=12)
  inner_id=canvas.create_window((0,0),window=inner,anchor="nw")
  canvas.configure(yscrollcommand=vsb.set)
  canvas.pack(side="top",fill="both",expand=True)
  vsb.place(relx=1.0,rely=0,relheight=1.0,anchor="ne")
  inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
  canvas.bind("<Configure>",lambda e:canvas.itemconfigure(inner_id,width=e.width))
  for seq,d in(("<Button-4>",-1),("<Button-5>",1)):
   canvas.bind_all(seq,lambda e,d=d:canvas.winfo_exists()and canvas.yview_scroll(d*2,"units"),add=True)
  canvas.bind_all("<MouseWheel>",lambda e:canvas.winfo_exists()and canvas.yview_scroll(-1 if e.delta>0 else 1,"units"),add=True)
  inner.columnconfigure(0,weight=1)
  controls={}
  for row,p in enumerate(props):
   cur=p.saved_value if p.saved_value is not None else p.default
   ttk.Label(inner,text=p.label,wraplength=340,justify="left").grid(row=row,column=0,sticky="w",pady=4,padx=(0,10))
   if p.kind=="checkbox":
    var=tk.BooleanVar(value=bool(cur))
    ttk.Checkbutton(inner,variable=var).grid(row=row,column=1,sticky="e")
   elif p.kind=="slider":
    var=tk.DoubleVar(value=float(cur))
    cell=ttk.Frame(inner)
    cell.grid(row=row,column=1,sticky="e")
    val_lbl=ttk.Label(cell,width=8,anchor="e")
    val_lbl.configure(text=properties._num(p.clamp(cur)))
    def moved(_v,p=p,var=var,lbl=val_lbl):
     lbl.configure(text=properties._num(p.clamp(var.get())))
    ttk.Scale(cell,from_=p.minimum,to=p.maximum,variable=var,length=160,command=moved).pack(side="left")
    val_lbl.pack(side="left",padx=(8,0))
   else:
    var=tk.StringVar(value=str(cur))
    ttk.Entry(inner,textvariable=var,width=24).grid(row=row,column=1,sticky="e")
   src="per-save"if p.saved_value is not None else"default"
   lbl=ttk.Label(inner,text=src)
   lbl.configure(foreground=MUTED)
   lbl.grid(row=row,column=2,sticky="e",padx=(10,0))
   controls[p.label]=(p,var)
  note=ttk.Label(dlg,padding=(12,6),wraplength=600,justify="left",text="\"per-save\" values live in this save. \"default\" values ""live in the addon's local files and are read by every save ""using it, on each world load.")
  note.configure(foreground=MUTED)
  note.pack(fill="x")
  row_f=ttk.Frame(dlg,padding=(12,0,12,12))
  row_f.pack(fill="x")
  def do_apply():
   changes=[]
   for label,(p,var)in controls.items():
    cur=p.saved_value if p.saved_value is not None else p.default
    v=var.get()
    if p.kind=="checkbox":
     if bool(v)==bool(cur):
      continue
     v="true"if v else"false"
    elif p.kind=="slider":
     if p.clamp(v)==p.clamp(cur):
      continue
     v=properties._num(p.clamp(v))
    elif str(v)==str(cur):
     continue
    changes.append(f"{label}={v}")
   dlg.destroy()
   if not changes:
    self.log_line("settings: nothing changed")
    return
   def op():
    from.cli import cmd_settings
    cmd_settings(_Args(save=save,addon=aname,set=changes,dry_run=False,no_backup=False))
   self.run_op(f"settings {aname}",op)
  ttk.Button(row_f,text="Cancel",command=dlg.destroy).pack(side="right")
  ttk.Button(row_f,text="Apply",style="Accent.TButton",command=do_apply).pack(side="right",padx=(0,8))
  dlg.bind("<Escape>",lambda e:dlg.destroy())
 def _batch(self,idents,each):
  for ident in idents:
   print(f"--- {ident} ---")
   try:
    each(ident)
   except SystemExit as e:
    if e.code not in(0,None):
     print(f"refused: {e}")
 def add_addon(self):
  save=self.current_save()
  if not save:
   return
  scene=Scene(paths.save_dir(save)/"scene.xml")
  attached={n for n in(addons.playlist_name(v)for v in scene.list_playlists()if not v.startswith("rom/"))if n}
  idents=Picker(self.root,"addon",attached).result
  if not idents:
   return
  has_companion=companion.is_installed(scene)
  def op():
   from.cli import cmd_add_addon
   self._batch(idents,lambda i:cmd_add_addon(_Args(save=save,addon=i,dry_run=False,no_backup=False)))
  self.run_op(f"add {len(idents)} addon(s)",op,done=self._needs_game_note if has_companion else None)
 def add_mod(self):
  save=self.current_save()
  if not save:
   return
  scene=Scene(paths.save_dir(save)/"scene.xml")
  attached={w.replace("\\","/").rstrip("/").rsplit("/",1)[-1]for w in scene.list_mods()}
  idents=Picker(self.root,"mod",attached).result
  if not idents:
   return
  def op():
   from.cli import cmd_add_mod
   self._batch(idents,lambda i:cmd_add_mod(_Args(save=save,mod=i,dry_run=False,no_backup=False)))
  self.run_op(f"add {len(idents)} mod(s)",op)
 def remove_selected(self):
  save=self.current_save()
  sel=self.tree.selection()
  if not save or not sel:
   return
  if len(sel)>1:
   self._remove_batch(save,sel)
   return
  kind,ident=self.tree.item(sel[0],"tags")[:2]
  values=self.tree.item(sel[0],"values")
  if kind=="companion":
   wants_more=self._two_buttons("SWAM","You really shouldn't do that.",primary="OK",secondary="But I need...")
   if not wants_more:
    return
   delete_anyway=self._two_buttons("SWAM","The companion is SWAM's agent inside the game. It keeps ""the provenance journal - the record of which addon spawned ""which vehicles and objects - and it is the one who spawns ""and removes structures when you add or remove addons.\n\n""If you delete it:\n""  • the journal for this save is lost forever;\n""  • addons installed so far can no longer be removed ""cleanly (their structures stay in the world);\n""  • any queued tasks are lost.\n\n""The save itself keeps working. You can reinstall the ""companion later, but it starts with an empty journal.",primary="nvm, go back",secondary="delete anyway")
   if not delete_anyway:
    return
   def op():
    from.cli import cmd_uninstall_companion
    cmd_uninstall_companion(_Args(save=save,really=True,dry_run=False,no_backup=False))
   self.run_op("uninstall companion",op)
   return
  if kind=="builtin":
   messagebox.showinfo("SWAM","This is a built-in (vanilla) addon. Removing those is not ""supported yet - it needs separate handling of rom paths.")
   return
  if kind=="mod":
   if not messagebox.askyesno("SWAM",f"Detach mod?\n\n{values[1]}"):
    return
   def op():
    from.cli import cmd_remove_mod
    cmd_remove_mod(_Args(save=save,mod=ident.replace("\\","/").rsplit("/",1)[-1],dry_run=False,no_backup=False))
   self.run_op(f"remove mod {ident}",op)
   return
  lk=lock.load(save)
  managed=ident in lk["addons"]
  force=geometry=False
  if not managed:
   if not messagebox.askyesno("SWAM",f"'{ident}' was not installed by SWAM (it came with the "f"world).\n\nIts entries can be removed, but structures "f"it spawned at world creation stay unless matched by "f"coordinates.\n\nRemove it anyway?"):
    return
   force=True
   geometry=messagebox.askyesno("SWAM","Also try to remove its static structures by coordinate ""matching?\n\n(Safe matches only; anything ambiguous is ""left alone.)")
  elif not messagebox.askyesno("SWAM",f"Remove addon '{ident}'?"):
   return
  scene=Scene(paths.save_dir(save)/"scene.xml")
  has_companion=companion.is_installed(scene)
  def op():
   from.cli import cmd_remove_addon
   cmd_remove_addon(_Args(save=save,addon=ident,dry_run=False,no_backup=False,force=force,force_geometry=geometry))
  self.run_op(f"remove addon {ident}",op,done=self._needs_game_note if has_companion else None)
 def install_companion(self):
  save=self.current_save()
  if not save:
   return
  def op():
   from.cli import cmd_install_companion
   cmd_install_companion(_Args(save=save,dry_run=False,no_backup=False))
  self.run_op("install companion",op)
 def restore_backup(self):
  save=self.current_save()
  if not save:
   return
  from.backup import list_backups
  entries=list_backups(save)
  if not entries:
   messagebox.showinfo("SWAM","No backups for this save yet - ""they appear after the first change.")
   return
  dlg=tk.Toplevel(self.root)
  dlg.title("Restore backup")
  dlg.configure(bg=BG)
  dlg.transient(self.root)
  dlg.grab_set()
  ttk.Label(dlg,text=f"Backups of '{save}', newest first:",padding=(10,10,10,4)).pack(anchor="w")
  lb=tk.Listbox(dlg,width=52,height=min(8,len(entries)),bg=PANEL,fg=FG,selectbackground=ACCENT,selectforeground="#ffffff",relief="flat",highlightthickness=0,activestyle="none")
  for e in entries:
   lb.insert("end",f"{e['time']}   ({e['operation']})")
  lb.selection_set(0)
  lb.pack(padx=10,pady=4)
  row=ttk.Frame(dlg,padding=10)
  row.pack(fill="x")
  chosen=[]
  def do_restore():
   sel=lb.curselection()
   if sel:
    chosen.append(entries[sel[0]])
   dlg.destroy()
  ttk.Button(row,text="Cancel",command=dlg.destroy).pack(side="right")
  ttk.Button(row,text="Restore",style="Accent.TButton",command=do_restore).pack(side="right",padx=(0,8))
  dlg.wait_window()
  if not chosen:
   return
  target=chosen[0]
  if not messagebox.askyesno("SWAM",f"Roll '{save}' back to {target['time']}?\n\n"f"The current state is backed up first, so this is "f"reversible."):
   return
  def op():
   from.cli import cmd_restore
   cmd_restore(_Args(save=save,time=target["time"],dry_run=False,no_backup=False))
  self.run_op(f"restore {target['time']}",op)
 def run_verify(self):
  save=self.current_save()
  if not save:
   return
  def op():
   problems=verify.run(paths.save_dir(save))
   if not problems:
    print("everything checks out")
   for p in problems:
    print(f"! {p}")
  self.run_op("verify",op)
class _Args:
 def __init__(self,**kw):
  self.__dict__.update(kw)
def _explain_crash(exc:BaseException)->None:
 import traceback
 detail="".join(traceback.format_exception(exc)).strip()
 try:
  messagebox.showerror("SWAM - something went wrong","SWAM hit an unexpected problem and cannot continue this ""action.\n\nNothing was half-written: every change is either ""completed or rolled back, and backups are kept in the swam ""backups folder.\n\nIf you report this on GitHub, include the ""text below:\n\n"+detail[-1500:])
 except tk.TclError:
  print(detail,file=sys.stderr)
def main():
 try:
  root=tk.Tk()
 except tk.TclError as e:
  print(f"cannot open a window: {e}",file=sys.stderr)
  raise SystemExit(1)
 root.report_callback_exception=lambda et,ev,tb:_explain_crash(ev)
 try:
  apply_theme(root)
  App(root)
  root.mainloop()
 except SystemExit:
  raise
 except BaseException as e:
  _explain_crash(e)
  raise SystemExit(1)
if __name__=="__main__":
 main()
