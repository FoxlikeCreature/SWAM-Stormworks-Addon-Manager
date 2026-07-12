import contextlib
import io
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,ttk
from.import addons,catalog,companion,lock,mods,paths,properties,snapshot,verify
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
EDGE="#5a5a63"
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
 style.configure("Vertical.TScrollbar",background=ACCENT,troughcolor=PANEL,bordercolor=EDGE,lightcolor=ACCENT_DIM,darkcolor=ACCENT,gripcount=3,arrowcolor="#ffffff",borderwidth=1)
 style.map("Vertical.TScrollbar",background=[("pressed",ACCENT_DIM),("active",ACCENT)],lightcolor=[("pressed",ACCENT_DIM)],darkcolor=[("pressed",ACCENT_DIM)])
 style.layout("Horizontal.TScale",[("Horizontal.Scale.trough",{"sticky":"nswe","children":[("Horizontal.Scale.slider",{"side":"left","sticky":""})]})])
 style.configure("Horizontal.TScale",background=ACCENT,troughcolor=FIELD,bordercolor=EDGE,lightcolor=ACCENT_DIM,darkcolor=ACCENT,gripcount=3,borderwidth=1,sliderthickness=16,sliderlength=26)
 style.map("Horizontal.TScale",background=[("pressed",ACCENT_DIM),("active","#c86bff")])
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
HELP=[
 ("h1","Before anything else"),
 ("","Close Stormworks. SWAM will not touch a save while the game is running, because the game rewrites the whole save when it saves and your changes would be lost."),
 ("","Some operations cannot be done from outside the game: spawning a building, removing one. Those are handed to the companion addon, which does them inside the game. Whenever SWAM says a task is queued, do this:"),
 ("step","1. Load the save."),
 ("step","2. Wait a few seconds for the chat line \"[SWAM] tasks done\"."),
 ("step","3. Save the game. That is the moment the world actually changes."),
 ("","If you quit without saving, nothing happened and the task simply runs again next time."),
 ("h1","The buttons"),
 ("h2","Add addon..."),
 ("","Opens a catalog of your workshop subscriptions, local files and the game's built-in content. Attaches the addon to the save and, if it places buildings, queues them for spawning."),
 ("h2","Add mod..."),
 ("","Attaches a mod (meshes, tiles, shaders). Mods need no in-game work, they take effect on the next game launch."),
 ("h2","Remove selected"),
 ("","Detaches whatever you picked in the list. Works on mods, addons and built-in (vanilla) addons. For addons it also offers to remove the structures they placed in the world."),
 ("h2","Upgrade selected"),
 ("","Refreshes an addon SWAM installed: takes the newer workshop version, removes the old structures and spawns the new ones. If you edited the local copy yourself, it asks which side wins."),
 ("h2","Settings..."),
 ("","The sliders and checkboxes the game only shows when you create a world. Values marked \"per-save\" live in this save. Values marked \"default\" live in the addon's files and apply to every save using them. Takes effect on the next world load."),
 ("h2","Refresh from files"),
 ("","For when you want to edit an addon yourself: move a building, delete one, change a spawn point. Edit its files in data/missions, press this, then load the world."),
 ("h2","Clean leftovers..."),
 ("","For an addon you already removed whose buildings are still standing. Finds them by their spawn coordinates and queues them for removal."),
 ("h2","Remove marked..."),
 ("","The last resort for a structure nothing else can attribute. In game, stand next to it, type \"?swam mark\" in chat, save, close the game, then press this. It can also remove every identical copy of that structure on the map. Things you built yourself are never touched: SWAM only accepts structures the game itself marks as addon-spawned, with no author list."),
 ("h2","Install companion"),
 ("","Puts SWAM's agent into the save. One button, once per save. Without it an addon can be attached, but its buildings will not appear."),
 ("h2","Check integrity"),
 ("","Audits the save: script entries, state files, the lock file. Run it if something feels off."),
 ("h2","Restore backup..."),
 ("","Rolls the save back. SWAM makes a backup before every change, so there is always something to roll back to."),
 ("h1","Colors in the list"),
 ("","Green is SWAM's companion. Amber means a newer workshop version is available. Violet is built-in (vanilla) content that shipped with the game."),
 ("h1","Workflow: add a mod"),
 ("step","1. Add mod..., pick it."),
 ("step","2. Start the game. That is all, mods need nothing else."),
 ("h1","Workflow: remove a mod"),
 ("step","1. Select it, Remove selected."),
 ("","A tile mod is worth a thought first: it changes the ground, and anything you built on that ground may end up floating or buried."),
 ("h1","Workflow: add an addon"),
 ("step","1. Install companion, if the save has none."),
 ("step","2. Add addon..., pick it."),
 ("step","3. Load the save, wait for \"[SWAM] tasks done\", save."),
 ("","Its buildings appear on that load. An addon that only sets itself up when a world is created may not work properly in an old save. SWAM reads its script and warns you when it sees that."),
 ("h1","Workflow: remove an addon"),
 ("step","1. Select it, Remove selected."),
 ("step","2. Say yes to removing its structures when asked."),
 ("step","3. Load the save, wait for \"[SWAM] tasks done\", save."),
 ("","For an addon SWAM installed, removal is exact: the companion wrote down everything it spawned. For an addon that came with the world there is no such record, so SWAM matches structures by their spawn coordinates. That covers placed buildings, not things the addon's script spawned later. Anything it cannot attribute with confidence is left alone, and it will tell you so."),
 ("h1","Workflow: update an addon from the workshop"),
 ("step","1. An amber row means a new version is waiting."),
 ("step","2. Select it, Upgrade selected."),
 ("step","3. Load the save, wait for \"[SWAM] tasks done\", save."),
 ("","Old structures out, new ones in, one world load. Your settings for that addon are re-applied afterwards."),
 ("h1","Workflow: apply your own edits to an addon"),
 ("","Editing playlist.xml alone does nothing to a world that already exists: the buildings are already in the save, and the addon's files are only read when a world is created. So the old ones have to go and the new ones have to be spawned."),
 ("step","1. Edit data/missions/<addon>: move a building, delete a location, whatever you wanted."),
 ("step","2. Select the addon, Refresh from files."),
 ("step","3. Load the save, wait for \"[SWAM] tasks done\", save."),
 ("","Your edits move the buildings out from under SWAM's feet, so it keeps its own copy of each addon's playlist as it was when the structures went into the world, and finds the old ones with that. It tells you when it is doing so."),
 ("h1","Workflow: replace a built-in addon with a workshop one"),
 ("step","1. Select the built-in (violet) row, Remove selected."),
 ("step","2. Say yes when asked about its structures."),
 ("step","3. Add addon..., pick the workshop version."),
 ("step","4. Load the save, wait for \"[SWAM] tasks done\", save."),
 ("","Removing built-in content is safe in the sense that the save simply stops loading it, and its files stay in the game folder, so you can always put it back. Just know what you are taking out: mission zones feed the mission system, the AI addons drive NPC crews, cargo runs on its own addon."),
 ("h1","Workflow: buildings left behind"),
 ("","If an addon is gone from the list but its buildings still stand:"),
 ("step","1. Clean leftovers..., pick the addon."),
 ("step","2. Load the save, wait for \"[SWAM] tasks done\", save."),
 ("","If even that does not find a particular structure, mark it by hand: stand next to it in game, type \"?swam mark\", save, close the game, then Remove marked..."),
 ("h1","If something goes wrong"),
 ("","Restore backup... takes the save back to how it was before the last change. Backups are kept per save, and the one you restore from is never deleted to make room. Check integrity tells you whether the save still adds up."),
]
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
  for text,cmd in(("Add addon…",self.add_addon),("Add mod…",self.add_mod),("Remove selected",self.remove_selected),("Upgrade selected",self.upgrade_selected),("Settings…",self.addon_settings),("Refresh from files",self.refresh_addon),("Clean leftovers…",self.clean_leftovers),("Remove marked…",self.remove_marked),("Install companion",self.install_companion),("Check integrity",self.run_verify),("Restore backup…",self.restore_backup),("Help",self.show_help)):
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
  snapshot.sync(name,scene.list_playlists())
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
    aname=addons.playlist_name(v)or v.rsplit("/",1)[-1]
    marks=["built-in (vanilla)"]
    if v[4:]in scripted_paths:
     marks.append("scripted")
    self.tree.insert("","end",values=("addon",aname,", ".join(marks)),tags=("builtin",aname))
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
  mods_,managed_,inherited_,builtin_,skipped=[],[],[],[],[]
  lk=lock.load(save)
  for iid in sel:
   kind,ident=self.tree.item(iid,"tags")[:2]
   if kind=="mod":
    mods_.append(ident)
   elif kind=="addon":
    (managed_ if ident in lk["addons"]else inherited_).append(ident)
   elif kind=="builtin":
    builtin_.append(ident)
   else:
    skipped.append(ident)
  lines=[]
  if mods_:
   lines.append(f"{len(mods_)} mod(s)")
  if managed_:
   lines.append(f"{len(managed_)} addon(s) installed by SWAM")
  if inherited_:
   lines.append(f"{len(inherited_)} inherited addon(s)")
  if builtin_:
   lines.append(f"{len(builtin_)} built-in addon(s)")
  if not lines:
   messagebox.showinfo("SWAM","Nothing removable selected.")
   return
  if not messagebox.askyesno("SWAM","Remove "+", ".join(lines)+"?"):
   return
  geo=False
  if inherited_:
   if not messagebox.askyesno("SWAM",f"{len(inherited_)} of those came with the world "f"(inherited). Their entries can be removed, but structures "f"spawned at world creation stay.\n\nRemove them too?"):
    inherited_=[]
  if builtin_:
   geo=messagebox.askyesno("SWAM",f"{len(builtin_)} of those are built-in (vanilla) content. The save "f"stops loading them; their files stay in the game's folder, so "f"you can add them back from the Built-in tab.\n\n"f"Also remove the structures they placed in the world?\n\n"f"Yes - if you are replacing them with a workshop version\n"f"No - keep the structures, drop only the addon")
  if not(mods_ or managed_ or inherited_ or builtin_):
   return
  def op():
   from.cli import cmd_remove_addon,cmd_remove_mod
   for s in skipped:
    print(f"skipped (companion): {s}")
   self._batch(mods_,lambda i:cmd_remove_mod(_Args(save=save,mod=i.replace("\\","/").rsplit("/",1)[-1],dry_run=False,no_backup=False)))
   self._batch(managed_,lambda i:cmd_remove_addon(_Args(save=save,addon=i,dry_run=False,no_backup=False,force=False,force_geometry=False)))
   self._batch(inherited_,lambda i:cmd_remove_addon(_Args(save=save,addon=i,dry_run=False,no_backup=False,force=True,force_geometry=False)))
   self._batch(builtin_,lambda i:cmd_remove_addon(_Args(save=save,addon=i,dry_run=False,no_backup=False,force=True,force_geometry=geo)))
  self.run_op(f"remove {len(mods_)+len(managed_)+len(inherited_)+len(builtin_)} "f"item(s)",op,done=self._needs_game_note if(managed_ or inherited_ or builtin_)else None)
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
 def show_help(self):
  dlg=tk.Toplevel(self.root)
  dlg.title("SWAM - help")
  dlg.configure(bg=BG)
  dlg.transient(self.root)
  dlg.geometry("760x620")
  dlg.minsize(560,400)
  row=ttk.Frame(dlg,padding=(12,0,12,12))
  row.pack(side="bottom",fill="x")
  frame=ttk.Frame(dlg,padding=12)
  frame.pack(side="top",fill="both",expand=True)
  txt=tk.Text(frame,wrap="word",bg=PANEL,fg=FG,relief="flat",highlightthickness=0,padx=14,pady=12,spacing1=2,spacing3=4,cursor="arrow")
  vsb=ttk.Scrollbar(frame,orient="vertical",command=txt.yview)
  txt.configure(yscrollcommand=vsb.set)
  vsb.pack(side="right",fill="y")
  txt.pack(side="left",fill="both",expand=True)
  txt.tag_configure("h1",foreground=ACCENT,font=("TkDefaultFont",13,"bold"),spacing1=14,spacing3=6)
  txt.tag_configure("h2",foreground=FG,font=("TkDefaultFont",10,"bold"),spacing1=8)
  txt.tag_configure("dim",foreground=MUTED)
  txt.tag_configure("step",lmargin1=16,lmargin2=32)
  for kind,line in HELP:
   txt.insert("end",line+"\n",kind)
  txt.configure(state="disabled")
  for seq,d in(("<Button-4>",-1),("<Button-5>",1)):
   txt.bind(seq,lambda e,d=d:txt.yview_scroll(d*2,"units"))
  ttk.Button(row,text="Close",style="Accent.TButton",command=dlg.destroy).pack(side="right")
 def refresh_addon(self):
  save=self.current_save()
  sel=self.tree.selection()
  if not save or not sel:
   messagebox.showinfo("SWAM","Select an addon whose files you want to edit by hand.")
   return
  kind,ident=self.tree.item(sel[0],"tags")[:2]
  if kind not in("addon","builtin"):
   messagebox.showinfo("SWAM","Select an addon, not a mod.")
   return
  if not messagebox.askyesno("SWAM",f"Refresh '{ident}' from its files in data/missions?\n\n""Everything it placed in the world is removed and spawned again ""from its playlist, so your hand-edits to that playlist (moving a ""building, deleting one) take effect in this save.\n\n""Edit the files first, then press this. SWAM keeps a copy of the ""playlist as it was when the structures were spawned, so it still ""knows where to find them."):
   return
  def op():
   from.cli import cmd_refresh
   cmd_refresh(_Args(save=save,addon=ident,dry_run=False,no_backup=False))
  self.run_op(f"refresh {ident}",op,done=self._needs_game_note)
 def clean_leftovers(self):
  save=self.current_save()
  if not save:
   return
  try:
   attached={addons.playlist_name(v)for v in Scene(paths.save_dir(save)/"scene.xml").list_playlists()}
  except(SystemExit,OSError)as e:
   messagebox.showinfo("SWAM",str(e))
   return
  gone=sorted(d.name for d in(paths.sw_root()/"data"/"missions").iterdir()if(d/"playlist.xml").is_file()and d.name not in attached)
  if not gone:
   messagebox.showinfo("SWAM","Every addon whose files are in data/missions is still attached ""to this save - there is nothing to clean up.\n\nThis button is ""for structures left behind by an addon you already removed.")
   return
  pick=self._pick_one("Clean leftovers","An addon that is no longer attached to this save, but whose ""structures may still stand in the world:",gone)
  if pick is None:
   return
  def op():
   from.cli import cmd_cleanup
   cmd_cleanup(_Args(save=save,addon=pick,dry_run=False,no_backup=False))
  self.run_op(f"cleanup {pick}",op,done=self._needs_game_note)
 def _pick_one(self,title:str,text:str,items:list[str])->str|None:
  dlg=tk.Toplevel(self)
  dlg.title(title)
  dlg.configure(bg=BG)
  dlg.transient(self)
  dlg.grab_set()
  ttk.Label(dlg,text=text,wraplength=420,justify="left").pack(anchor="w",padx=12,pady=(12,6))
  var=tk.StringVar(value=items[0])
  box=ttk.Combobox(dlg,textvariable=var,values=items,state="readonly",width=48)
  box.pack(fill="x",padx=12)
  out:list[str]=[]
  row=ttk.Frame(dlg)
  row.pack(fill="x",padx=12,pady=12)
  ttk.Button(row,text="Cancel",command=dlg.destroy).pack(side="right")
  ttk.Button(row,text="Clean",style="Accent.TButton",command=lambda:(out.append(var.get()),dlg.destroy())).pack(side="right",padx=(0,8))
  self.wait_window(dlg)
  return out[0]if out else None
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
  dlg.geometry("720x520")
  dlg.minsize(600,320)
  canvas=tk.Canvas(dlg,bg=BG,highlightthickness=0)
  vsb=ttk.Scrollbar(dlg,orient="vertical",command=canvas.yview)
  inner=ttk.Frame(canvas,padding=(12,12,28,12))
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
   if p.saved_value is None:
    src="all saves"
   elif properties._num(p.clamp(p.saved_value))!=properties._num(p.clamp(p.default)):
    src=f"this save (files: {properties._num(p.clamp(p.default))})"
   else:
    src="this save"
   lbl=ttk.Label(inner,text=src)
   lbl.configure(foreground=MUTED)
   lbl.grid(row=row,column=2,sticky="e",padx=(10,0))
   controls[p.label]=(p,var)
  note=ttk.Label(dlg,padding=(12,6),wraplength=600,justify="left",text="\"this save\" means the addon wrote the value into this save when ""the world was made, so changing it here changes this world (and ""the addon's own default, so new worlds start the same). ""\"all saves\" means the value only lives in the addon's files and ""every save using them reads it on each world load.")
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
  if kind=="builtin":
   if not messagebox.askyesno("SWAM",f"Remove built-in addon '{ident}'?\n\nThe save stops loading it. "f"Its files stay in the game's folder, so you can add it back "f"from the Built-in tab at any time."):
    return
   geometry=messagebox.askyesno("SWAM","Also remove the structures it placed in the world?\n\n""Yes - if you are replacing it with a workshop version\n""No - keep the structures, drop only the addon")
  elif not managed:
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
