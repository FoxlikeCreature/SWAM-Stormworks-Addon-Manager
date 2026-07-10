import argparse
from.import addons,companion,geometry,lock,mods,paths,properties,verify
from.backup import Transaction
from.scene import Scene
def cmd_saves(_args):
 for d in sorted(paths.saves_dir().iterdir()):
  if(d/"scene.xml").is_file():
   print(d.name)
def cmd_list(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 print(f"=== mods ({args.save}) ===")
 mod_paths=scene.list_mods()
 if not mod_paths:
  print("  (none)")
 for w in mod_paths:
  print(f"  {mods.describe_wine_path(w)}")
 print("\n=== scripted addons ===")
 for s in scene.list_scripts():
  print(f"  id={s['script_id']:>3} store={s['store']} {s['path']}")
 print("\n=== all attached playlists ===")
 for v in scene.list_playlists():
  print(f"  {v}")
def _apply(args,save,scene,operation):
 if args.dry_run:
  print(scene.diff()or"(no changes)")
  return
 with Transaction(save,operation,enabled=not args.no_backup)as tx:
  scene.write()
 if tx.backup:
  print(f"backup: {tx.backup}")
 print("done")
def cmd_add_mod(args):
 save=paths.save_dir(args.save)
 ref=mods.resolve_mod(args.mod)
 print(f"mod: {ref.name} [{ref.mod_id}] source: {ref.source}")
 if ref.has_tiles:
  print("WARNING: this mod contains tiles - it will change terrain, ""including under anything already built there")
 scene=Scene(save/"scene.xml")
 scene.add_mod(ref.wine_path)
 _apply(args,save,scene,f"add-mod {ref.mod_id}")
def cmd_remove_mod(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 wine_path=mods.match_installed(scene.list_mods(),args.mod)
 print(f"detaching: {mods.describe_wine_path(wine_path)}")
 scene.remove_mod(wine_path)
 _apply(args,save,scene,f"remove-mod {args.mod}")
def cmd_add_addon(args):
 save=paths.save_dir(args.save)
 ref=addons.resolve_addon(args.addon)
 kind="scripted"if ref.scripted else"scriptless"
 print(f"addon: {ref.name} ({kind})")
 if ref.scripted:
  risk=ref.init_risk()
  if risk:
   print(f"WARNING: {risk}")
 scene=Scene(save/"scene.xml")
 scene.add_playlist(ref.playlist_value)
 new_sid=scene.add_script(ref.playlist_value)if ref.scripted else None
 if args.dry_run:
  print(scene.diff())
  print(f"(dry-run: files would be copied to {ref.local_dir()})")
  return
 with Transaction(save,f"add-addon {ref.name}",enabled=not args.no_backup)as tx:
  dest=addons.install_files(ref)
  scene.write()
  lk=lock.load(save.name)
  rec=lock.addon_record(ref.name,ref.playlist_value,ref.scripted,lock.file_hash(dest/"playlist.xml"))
  rec["script_id"]=new_sid
  rec["source_digest"]=addons.dir_digest(ref.disk_path)
  lk["addons"][ref.name]=rec
  lock.store(save.name,lk)
  sid=companion.script_id(scene)
  if sid is not None:
   companion.queue_task(save,sid,{"action":"spawn_env","addon":ref.name})
   print("companion task queued: spawn the addon's structures on ""next world load (save the game afterwards)")
  else:
   print("companion is not installed - static structures will not ""appear by themselves (swam install-companion)")
 if tx.backup:
  print(f"backup: {tx.backup}")
 print("done")
def cmd_remove_addon(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 lk=lock.load(save.name)
 name=args.addon
 if name==companion.NAME:
  raise SystemExit("You really shouldn't do that.\n\n""The companion is the one holding the cleanup journal - deleting ""the janitor along with his notebook is the single job he cannot ""do. If you truly want it gone: swam uninstall-companion")
 value=f"data/missions/{name}"
 if value not in scene.list_playlists():
  raise SystemExit(f"addon '{name}' is not attached to this save "f"(expected entry {value})")
 scripted,script_path=addons.find_script_entry(scene,name,value)
 managed=name in lk["addons"]
 if not managed and not args.force:
  raise SystemExit(f"addon '{name}' was not installed by SWAM (inherited).\n"f"Its entries can be removed, but structures spawned at world "f"creation will remain (the companion only removes what it has "f"seen itself).\nIf that is acceptable, re-run with --force")
 scene.remove_playlist(value)
 removed_sid=scene.remove_script(script_path)if scripted else None
 if args.dry_run:
  print(scene.diff())
  if removed_sid is not None:
   print(f"(dry-run: script_data/{removed_sid}.xml would be deleted; "f"the numbering gap is kept - the game stores it as is)")
  return
 with Transaction(save,f"remove-addon {name}",enabled=not args.no_backup)as tx:
  scene.write()
  if removed_sid is not None:
   sd=save/"script_data"/f"{removed_sid}.xml"
   if sd.is_file():
    sd.unlink()
    print(f"deleted script_data/{removed_sid}.xml (addon g_savedata)")
  if managed:
   del lk["addons"][name]
   lock.store(save.name,lk)
  sid=companion.script_id(scene)
  if sid is not None:
   jr=companion.journal(save,sid).get(name,{})
   vehicles=dict(jr.get("v",{}))
   objects=jr.get("o",{})
   if args.force_geometry and not managed:
    geo_vids,warns=geometry.match(scene.text,name,scene.list_playlists()+[f"data/missions/{name}"])
    for w in warns:
     print(f"  geometry: {w}")
    base=max(vehicles,default=0)
    known=set(vehicles.values())
    added=0
    for v in geo_vids:
     if v not in known:
      added+=1
      vehicles[base+added]=float(v)
    print(f"  geometry: matched {len(geo_vids)} vehicles, "f"{added} new queued for despawn")
   if vehicles or objects:
    companion.queue_task(save,sid,{"action":"despawn","addon":name,"vehicles":vehicles,"objects":objects})
    print(f"companion task queued: remove {len(vehicles)} "f"vehicles and {len(objects)} objects on next world "f"load (save the game afterwards)")
 if tx.backup:
  print(f"backup: {tx.backup}")
 print("done. The data/missions folder is untouched - other saves may ""use it")
def cmd_install_companion(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 if companion.is_installed(scene):
  companion.install_files()
  print("companion already installed, script refreshed")
  return
 sid=companion.install_into_scene(scene)
 if args.dry_run:
  print(scene.diff())
  return
 with Transaction(save,"install-companion",enabled=not args.no_backup)as tx:
  companion.install_files()
  scene.write()
 if tx.backup:
  print(f"backup: {tx.backup}")
 print(f"companion installed (script_id={sid}). It starts keeping the "f"provenance journal after the save is loaded; chat command: ?swam")
def cmd_upgrade_addon(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 lk=lock.load(save.name)
 name=args.addon
 if name not in lk["addons"]:
  raise SystemExit(f"addon '{name}' is not managed by SWAM - upgrade "f"only works for addons it installed")
 rec=lk["addons"][name]
 local_dir=paths.sw_root()/"data"/"missions"/name
 if not(local_dir/"playlist.xml").is_file():
  raise SystemExit(f"{local_dir} has no playlist.xml - the addon's local "f"files are gone, nothing to work from")
 src=None if args.local else addons.find_workshop_source(name)
 local_changed=addons.local_playlist_changed(rec,name)
 from_workshop=src is not None and addons.update_available(rec,name)
 if from_workshop and local_changed and not args.discard_local:
  raise SystemExit(f"the local copy of '{name}' has manual edits AND the "f"workshop has a newer version. Pick one:\n"f"  --local          keep your edits, refresh the save from them\n"f"  --discard-local  replace the local copy with the workshop version")
 if not from_workshop and not local_changed:
  print("already up to date (script.lua edits in data/missions apply on ""every load by themselves - only playlist.xml changes need an ""upgrade)")
  return
 if from_workshop and src.name!=name:
  raise SystemExit(f"the workshop version renamed the addon to "f"'{src.name}' - that changes save entries; "f"remove and re-add instead")
 sid=companion.script_id(scene)
 if sid is None:
  raise SystemExit("the companion is required for upgrades ""(swam install-companion)")
 source_desc=str(src.disk_path)if from_workshop else f"local edits in {local_dir}"
 if args.dry_run:
  steps="despawn old structures -> replace files -> respawn"if from_workshop else"despawn old structures -> respawn from the edited playlist"
  print(f"would upgrade '{name}' from {source_desc}\n({steps})")
  return
 import shutil
 with Transaction(save,f"upgrade-addon {name}",enabled=not args.no_backup)as tx:
  jr=companion.journal(save,sid).get(name,{})
  vehicles,objects=jr.get("v",{}),jr.get("o",{})
  if vehicles or objects:
   companion.queue_task(save,sid,{"action":"despawn","addon":name,"vehicles":vehicles,"objects":objects})
  if from_workshop:
   shutil.rmtree(local_dir)
   shutil.copytree(src.disk_path,local_dir)
  companion.queue_task(save,sid,{"action":"spawn_env","addon":name})
  if from_workshop:
   settings=rec.get("settings")or{}
   if settings:
    try:
     report,applied=properties.apply(save,name,scene,settings)
     print(f"re-applied {len(applied)} saved setting(s)")
    except SystemExit as e:
     print(f"could not re-apply saved settings: {e}")
   rec["source_digest"]=addons.dir_digest(src.disk_path)
  rec["playlist_hash"]=lock.file_hash(local_dir/"playlist.xml")
  lock.store(save.name,lk)
 if tx.backup:
  print(f"backup: {tx.backup}")
 what="the workshop version"if from_workshop else"your edited local copy"
 print(f"upgraded from {what}. On next world load the companion removes "f"the old structures and spawns the new ones (in that order) - "f"then save")
def cmd_cleanup(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 name=args.addon
 sid=companion.script_id(scene)
 if sid is None:
  raise SystemExit("the companion is required for cleanup ""(swam install-companion)")
 vids,warns=geometry.match(scene.text,name,scene.list_playlists())
 for w in warns:
  print(f"  geometry: {w}")
 known={int(v)for rec in companion.journal(save,sid).values()for v in rec.get("v",{}).values()}
 vids=[v for v in vids if v not in known]
 if not vids:
  print("no leftover structures of this addon matched - nothing to do")
  return
 if args.dry_run:
  print(f"(dry-run) would despawn {len(vids)} vehicles: "f"{sorted(vids)}")
  return
 with Transaction(save,f"cleanup {name}",enabled=not args.no_backup)as tx:
  companion.queue_task(save,sid,{"action":"despawn","addon":name,"vehicles":{i+1:float(v)for i,v in enumerate(sorted(vids))},"objects":{}})
 if tx.backup:
  print(f"backup: {tx.backup}")
 print(f"queued: {len(vids)} vehicles will be despawned on next world "f"load (save the game afterwards)")
def cmd_remove_marked(args):
 import hashlib
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 sid=companion.script_id(scene)
 if sid is None:
  raise SystemExit("the companion is required ""(swam install-companion)")
 data=companion.load_data(save,sid)
 marks=data.get("marks")or{}
 if not marks:
  raise SystemExit("no marks in this save.\nIn game, stand next to the structure ""you want gone and type \"?swam mark\" in chat, then SAVE the ""game, close it and re-run this command.")
 vehicles=geometry.scene_vehicles(scene.text)
 attested=geometry.addon_attested(scene.text)
 known={int(v)for rec in data.get("journal",{}).values()for v in rec.get("v",{}).values()}
 groups:dict[int,list[int]]={}
 for v in vehicles:
  groups.setdefault(v["group_id"],[]).append(v["id"])
 def group_ok(gid):
  return(all(v in attested for v in groups[gid])and not any(v in known for v in groups[gid]))
 def group_digest(gid):
  hs=[]
  for v in sorted(groups[gid]):
   f=save/"vehicles"/f"{v}.xml.bin"
   if not f.is_file():
    return None
   hs.append(hashlib.sha256(f.read_bytes()).hexdigest())
  return tuple(sorted(hs))
 target_gids=set()
 for n in sorted(marks,key=str):
  mk=marks[n]
  pos=(float(mk.get("x",0)),float(mk.get("y",0)),float(mk.get("z",0)))
  def d(v):
   return sum((a-b)**2 for a,b in zip(v["pos"],pos))**0.5
  near=sorted((v for v in vehicles if d(v)<=100),key=d)
  picked=None
  for v in near:
   if group_ok(v["group_id"]):
    picked=v
    break
   if v["id"]in known:
    print(f"mark {n}: nearest structure belongs to a managed "f"addon (see swam journal) - remove that addon "f"instead; skipping")
    break
   print(f"mark {n}: skipping vehicle {v['id']} - the game does "f"not mark it as addon-spawned (players built it?)")
  if picked is None:
   if not near:
    print(f"mark {n}: nothing within 100 m - skipped")
   continue
  target_gids.add(picked["group_id"])
  print(f"mark {n}: vehicle group {picked['group_id']} "f"({len(groups[picked['group_id']])} vehicle(s), "f"{d(picked):.0f} m away)")
  if args.all:
   dig=group_digest(picked["group_id"])
   if dig is None:
    print("  cannot fingerprint it - --all skipped for this mark")
    continue
   twins=[g for g in groups if g!=picked["group_id"]and group_ok(g)and group_digest(g)==dig]
   for g in twins:
    target_gids.add(g)
   print(f"  --all: {len(twins)} identical group(s) found elsewhere")
 vids=sorted(v for g in target_gids for v in groups[g])
 if not vids:
  raise SystemExit("nothing matched the marks - nothing to do")
 if args.dry_run:
  print(f"(dry-run) would despawn {len(vids)} vehicles: {vids}")
  return
 with Transaction(save,"remove-marked",enabled=not args.no_backup)as tx:
  data=companion.load_data(save,sid)
  tasks=data.setdefault("tasks",{})
  tn=max((k for k in tasks if isinstance(k,int)),default=0)+1
  tasks[tn]={"action":"despawn","addon":"marked structures","vehicles":{i+1:float(v)for i,v in enumerate(vids)},"objects":{}}
  data["marks"]={}
  data.setdefault("journal",{})
  data.setdefault("report",{})
  from.import savedata
  savedata.save_file(save/"script_data"/f"{sid}.xml",data)
 if tx.backup:
  print(f"backup: {tx.backup}")
 print(f"queued: {len(vids)} vehicles ({len(target_gids)} group(s)) will "f"be despawned on next world load (save the game afterwards). "f"Marks cleared.")
def cmd_settings(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 name=args.addon
 if not args.set:
  props=properties.read(save,name,scene)
  if not props:
   print("this addon exposes no settings")
   return
  for p in props:
   rng=(f"  [{properties._num(p.minimum)}"f"..{properties._num(p.maximum)}"f" step {properties._num(p.step)}]"if p.kind=="slider"else"")
   cur=p.saved_value if p.saved_value is not None else p.default
   src="save state"if p.saved_value is not None else"script default"
   if p.kind=="checkbox":
    cur="on"if cur else"off"
   elif p.kind=="slider":
    cur=properties._num(cur)
   print(f"  [{p.kind:8}] {p.label}{rng}\n"f"             = {cur}  ({src})")
  print("\nchange with: swam settings <save> <addon> ""--set \"Label=value\"")
  return
 changes={}
 for item in args.set:
  if"="not in item:
   raise SystemExit(f'expected "Label=value", got: {item}')
  k,v=item.split("=",1)
  changes[k.strip()]=v.strip()
 with Transaction(save,f"settings {name}",enabled=not args.no_backup)as tx:
  report,applied=properties.apply(save,name,scene,changes)
  for line in report:
   print(line)
  lk=lock.load(save.name)
  if name in lk["addons"]:
   lk["addons"][name].setdefault("settings",{}).update(applied)
   lock.store(save.name,lk)
 if tx.backup:
  print(f"backup: {tx.backup}")
 print("done. The values apply from the next world load")
def cmd_uninstall_companion(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 sid=companion.script_id(scene)
 if sid is None:
  raise SystemExit("the companion is not installed in this save")
 if not args.really:
  raise SystemExit("This deletes the provenance journal for this save - SWAM will ""forget who spawned what,\nand clean removal of addons installed ""so far becomes impossible.\nIf you mean it, re-run with --really")
 scene.remove_playlist(companion.PLAYLIST_VALUE)
 scene.remove_script(companion.PLAYLIST_VALUE)
 if args.dry_run:
  print(scene.diff())
  return
 with Transaction(save,"uninstall-companion",enabled=not args.no_backup)as tx:
  scene.write()
  sd=save/"script_data"/f"{sid}.xml"
  if sd.is_file():
   sd.unlink()
 if tx.backup:
  print(f"backup: {tx.backup}")
 print("companion uninstalled. It cleaned out its desk and left the ""building. The journal went with it.")
def cmd_journal(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 sid=companion.script_id(scene)
 if sid is None:
  raise SystemExit("companion is not installed in this save")
 jr=companion.journal(save,sid)
 if not jr:
  print("journal is empty (the companion has not seen any spawns yet)")
 for name,rec in jr.items():
  nv=len(rec.get("v",{}))
  no=len(rec.get("o",{}))
  print(f"  {name}: vehicles {nv}, objects {no}")
 rep=companion.reports(save,sid)
 if rep:
  print("task reports:")
  for n in sorted(rep):
   print(f"  #{n}: {rep[n]}")
def cmd_backups(args):
 from.backup import list_backups
 entries=list_backups(args.save)
 if not entries:
  print("no backups for this save yet")
  return
 for e in entries:
  print(f"  {e['time']}  ({e['operation']})")
def cmd_restore(args):
 from.backup import list_backups,make_backup,restore_backup
 from.guard import ensure_game_closed
 save=paths.save_dir(args.save)
 entries=list_backups(args.save)
 if not entries:
  raise SystemExit("no backups for this save")
 if args.time:
  matches=[e for e in entries if e["time"]==args.time]
  if not matches:
   raise SystemExit(f"no backup named {args.time} - see: "f"swam backups {args.save}")
  target=matches[0]
 else:
  target=entries[0]
 ensure_game_closed()
 make_backup(save,"pre-restore")
 restore_backup(save,target["path"])
 print(f"restored '{args.save}' from {target['time']} "f"({target['operation']}). The previous state was backed up as "f"'pre-restore'.")
def cmd_verify(args):
 save=paths.save_dir(args.save)
 problems=verify.run(save)
 if not problems:
  print("everything checks out")
 else:
  for p in problems:
   print(f"  ! {p}")
  raise SystemExit(f"problems: {len(problems)}")
def cmd_status(args):
 save=paths.save_dir(args.save)
 lk=lock.load(save.name)
 print(f"save: {args.save}")
 if not lk["addons"]:
  print("no managed addons")
 else:
  print("managed addons:")
  for name,rec in lk["addons"].items():
   kind="scripted"if rec["scripted"]else"scriptless"
   note=""
   if addons.update_available(rec,name):
    note+="  [update available: swam upgrade-addon]"
   if addons.local_playlist_changed(rec,name):
    note+="  [local playlist edited: swam upgrade-addon --local]"
   print(f"  {name} ({kind}, installed {rec['installed_at']}){note}")
 problems=verify.run(save)
 print(f"verify: {'ok'if not problems else f'{len(problems)} problem(s)'}")
 for p in problems:
  print(f"  ! {p}")
def cmd_manage(args):
 from.import interactive
 interactive.run(args.save,lambda cmd,extra:main([cmd]+extra))
def build_parser():
 p=argparse.ArgumentParser(prog="swam",description="addon and mod manager for existing Stormworks saves")
 sub=p.add_subparsers(dest="cmd",required=True)
 sub.add_parser("saves",help="list saves").set_defaults(fn=cmd_saves)
 sp=sub.add_parser("list",help="show what is attached to a save")
 sp.add_argument("save")
 sp.set_defaults(fn=cmd_list)
 for name,fn,arg,help_ in(("add-mod",cmd_add_mod,"mod","attach a mod"),("remove-mod",cmd_remove_mod,"mod","detach a mod"),("add-addon",cmd_add_addon,"addon","attach an addon"),("remove-addon",cmd_remove_addon,"addon","detach an addon"),("upgrade-addon",cmd_upgrade_addon,"addon","refresh a SWAM-installed addon from the workshop ""or from its edited local copy")):
  sp=sub.add_parser(name,help=help_)
  sp.add_argument("save")
  sp.add_argument(arg,help="workshop id, path or name")
  sp.add_argument("--dry-run",action="store_true",help="show the diff without changing anything")
  sp.add_argument("--no-backup",action="store_true",help="skip the backup (not recommended)")
  if name=="remove-addon":
   sp.add_argument("--force",action="store_true",help="remove entries of an inherited addon")
   sp.add_argument("--force-geometry",action="store_true",help="despawn an inherited addon's structures by ""coordinate matching (a compromise)")
  if name=="upgrade-addon":
   sp.add_argument("--local",action="store_true",help="refresh the save from the (edited) local copy in ""data/missions instead of the workshop")
   sp.add_argument("--discard-local",action="store_true",help="overwrite local manual edits with the workshop version")
  sp.set_defaults(fn=fn)
 for name,fn,help_ in(("verify",cmd_verify,"check integrity"),("status",cmd_status,"save and lock state"),("journal",cmd_journal,"provenance journal"),("backups",cmd_backups,"list backups")):
  sp=sub.add_parser(name,help=help_)
  sp.add_argument("save")
  sp.set_defaults(fn=fn)
 sp=sub.add_parser("cleanup",help="despawn an addon's leftover structures by ""coordinate matching (works even after the ""addon entries were already removed)")
 sp.add_argument("save")
 sp.add_argument("addon",help="addon name (its files must still be in ""data/missions)")
 sp.add_argument("--dry-run",action="store_true")
 sp.add_argument("--no-backup",action="store_true")
 sp.set_defaults(fn=cmd_cleanup)
 sp=sub.add_parser("remove-marked",help="despawn structures marked in game with ""\"?swam mark\"")
 sp.add_argument("save")
 sp.add_argument("--all",action="store_true",help="also remove every identical structure on the map")
 sp.add_argument("--dry-run",action="store_true")
 sp.add_argument("--no-backup",action="store_true")
 sp.set_defaults(fn=cmd_remove_marked)
 sp=sub.add_parser("settings",help="view or change an addon's settings (the same ""sliders the game shows at world creation)")
 sp.add_argument("save")
 sp.add_argument("addon",help="addon name")
 sp.add_argument("--set",action="append",metavar='"Label=value"',help="change a setting (repeatable)")
 sp.add_argument("--no-backup",action="store_true")
 sp.set_defaults(fn=cmd_settings)
 sp=sub.add_parser("restore",help="restore a save from a backup")
 sp.add_argument("save")
 sp.add_argument("time",nargs="?",help="backup timestamp (default: the newest)")
 sp.set_defaults(fn=cmd_restore)
 sp=sub.add_parser("install-companion",help="install the companion addon into a save")
 sp.add_argument("save")
 sp.add_argument("--dry-run",action="store_true")
 sp.add_argument("--no-backup",action="store_true")
 sp.set_defaults(fn=cmd_install_companion)
 sp=sub.add_parser("uninstall-companion",help="remove the companion (deletes the journal)")
 sp.add_argument("save")
 sp.add_argument("--really",action="store_true",help="confirm losing the provenance journal")
 sp.add_argument("--dry-run",action="store_true")
 sp.add_argument("--no-backup",action="store_true")
 sp.set_defaults(fn=cmd_uninstall_companion)
 sp=sub.add_parser("manage",help="interactive mode")
 sp.add_argument("save")
 sp.set_defaults(fn=cmd_manage)
 sp=sub.add_parser("gui",help="graphical interface")
 sp.set_defaults(fn=lambda args:__import__("swam.gui",fromlist=["main"]).main())
 return p
def main(argv=None):
 args=build_parser().parse_args(argv)
 args.fn(args)
