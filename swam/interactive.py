from.import addons,companion,lock,mods,paths,verify
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
   if v.startswith("rom/data/missions/"):
    continue
   name=addons.playlist_name(v)
   if name is None:
    continue
   marks=[]
   if v in scripted_paths:
    marks.append("scripted")
   if not v.startswith("data/missions/"):
    marks.append("workshop")
   marks.append("SWAM"if name in managed else"inherited")
   rows.append(("addon",name))
   print(f"  {len(rows):2}. {name} [{', '.join(marks)}]")
  comp="installed"if companion.is_installed(scene)else"NOT installed"
  problems=verify.run(save)
  print(f"companion: {comp}; verify: "f"{'ok'if not problems else f'{len(problems)} problem(s)'}")
  print("\ncommands: d <N> remove | a <id|path|name> add addon | ""m <id|path> add mod | u <N> upgrade | s <N> settings |\n"" k <N> cleanup leftovers | x remove marked | c companion | ""j journal | r restore | q quit")
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
   elif cmd in("u","s","k")and arg.isdigit()and 1<=int(arg)<=len(rows):
    kind,ident=rows[int(arg)-1]
    if kind!="addon":
     print("that is a mod - this command works on addons")
    elif cmd=="u":
     dispatch("upgrade-addon",[save_name,ident])
    elif cmd=="k":
     dispatch("cleanup",[save_name,ident])
    else:
     extra=[]
     print("current settings:")
     dispatch("settings",[save_name,ident])
     line2=input('change ("Label=value", empty to skip): ').strip()
     if line2:
      extra=["--set",line2]
      dispatch("settings",[save_name,ident]+extra)
   elif cmd=="a"and arg:
    dispatch("add-addon",[save_name,arg])
   elif cmd=="m"and arg:
    dispatch("add-mod",[save_name,arg])
   elif cmd=="x":
    all_=input("also remove every identical copy on the map? [y/N] ").strip().lower()
    dispatch("remove-marked",[save_name]+(["--all"]if all_=="y"else[]))
   elif cmd=="c":
    dispatch("install-companion",[save_name])
   elif cmd=="j":
    dispatch("journal",[save_name])
   elif cmd=="r":
    dispatch("backups",[save_name])
    ts=input("timestamp to restore (empty = newest, 'n' to cancel): ").strip()
    if ts.lower()!="n":
     dispatch("restore",[save_name]+([ts]if ts else[]))
   else:
    print("unrecognized command")
  except SystemExit as e:
   if e.code not in(0,None):
    print(f"refused: {e}")
