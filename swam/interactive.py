from.import companion,lock,mods,paths,verify
from.scene import Scene
def run(save_name:str,dispatch)->None:
 save=paths.save_dir(save_name)
 while True:
  scene=Scene(save/"scene.xml")
  lk=lock.load(save_name)
  managed=set(lk["addons"])
  print(f"\n=== {save_name} ===")
  rows=[]
  print("mods:")
  for w in scene.list_mods():
   rows.append(("mod",w))
   print(f"  {len(rows):2}. {mods.describe_wine_path(w)}")
  scripted_paths={s["path"]for s in scene.list_scripts()}
  print("addons:")
  for v in scene.list_playlists():
   if not v.startswith("data/missions/"):
    continue
   name=v.split("/",2)[2]
   marks=[]
   if v in scripted_paths:
    marks.append("scripted")
   marks.append("SWAM"if name in managed else"inherited")
   rows.append(("addon",name))
   print(f"  {len(rows):2}. {name} [{', '.join(marks)}]")
  comp="installed"if companion.is_installed(scene)else"NOT installed"
  problems=verify.run(save)
  print(f"companion: {comp}; verify: "f"{'ok'if not problems else f'{len(problems)} problem(s)'}")
  print("\ncommands: d <N> remove | a <id|path|name> add addon | ""m <id|path> add mod | c companion | j journal | q quit")
  try:
   line=input("> ").strip()
  except(EOFError,KeyboardInterrupt):
   print()
   return
  if not line or line=="q":
   return
  try:
   cmd,_,arg=line.partition(" ")
   arg=arg.strip()
   if cmd=="d"and arg.isdigit()and 1<=int(arg)<=len(rows):
    kind,ident=rows[int(arg)-1]
    if kind=="mod":
     dispatch("remove-mod",[save_name,ident])
    else:
     extra=[]if ident in managed else["--force"]
     dispatch("remove-addon",[save_name,ident]+extra)
   elif cmd=="a"and arg:
    dispatch("add-addon",[save_name,arg])
   elif cmd=="m"and arg:
    dispatch("add-mod",[save_name,arg])
   elif cmd=="c":
    dispatch("install-companion",[save_name])
   elif cmd=="j":
    dispatch("journal",[save_name])
   else:
    print("unrecognized command")
  except SystemExit as e:
   if e.code not in(0,None):
    print(f"refused: {e}")
