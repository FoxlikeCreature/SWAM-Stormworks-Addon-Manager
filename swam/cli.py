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
 already=addons.attached_value(scene,ref.name)
 if already is not None:
  raise SystemExit(f"'{ref.name}' is already attached to this save (as "f"{already}) - adding it again would give the game two "f"copies of the same addon")
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
  rec=lock.addon_record(ref.name,ref.playlist_value,ref.scripted,lock.file_hash(dest/"playlist.xml"),source=ref.source,world_digest=addons.world_digest(dest))
  rec["script_id"]=new_sid
  if ref.source=="workshop":
   rec["source_digest"]=addons.dir_digest(ref.disk_path)
  lk["addons"][ref.name]=rec
  lock.store(save.name,lk)
  sid=companion.script_id(scene)
  if sid is not None:
   companion.queue_task(save,sid,{"action":"spawn_env","addon":ref.name})
   print("companion task queued: spawn the addon's structures on ""next world load (save the game afterwards)")
  else:
   rec["pending_spawn"]=True
   lock.store(save.name,lk)
   print("companion is not installed - the addon's structures cannot ""spawn yet.\nInstall the companion (swam install-companion) ""and SWAM will spawn them then")
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
 value=addons.attached_value(scene,name)
 if value is None:
  raise SystemExit(f"addon '{name}' is not attached to this save")
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
    jr_all=companion.journal(save,sid)
    others={int(x)for aname,rec in jr_all.items()if aname!=name for kind in("v","o")for x in rec.get(kind,{}).values()}
    geo_vids,geo_oids,warns=geometry.match_all(scene.text,name,scene.list_playlists()+[addons.value_for(name)],owned_elsewhere=others)
    for w in warns:
     print(f"  geometry: {w}")
    objects=dict(objects)
    added=0
    for pool,found in((vehicles,geo_vids),(objects,geo_oids)):
     base=max(pool,default=0)
     known=set(pool.values())
     n=0
     for x in found:
      if x not in known:
       n+=1
       added+=1
       pool[base+n]=float(x)
    print(f"  geometry: matched {len(geo_vids)} vehicles and "f"{len(geo_oids)} objects, {added} new queued for despawn")
   if vehicles or objects:
    companion.queue_task(save,sid,{"action":"despawn","addon":name,"vehicles":vehicles,"objects":objects})
    print(f"companion task queued: remove {len(vehicles)} "f"vehicles and {len(objects)} objects on next world "f"load (save the game afterwards)")
   else:
    dropped=companion.cancel_pending(save,sid,name)
    if dropped:
     print(f"cancelled {dropped} queued task(s) for this addon - the ""game never ran them, so nothing was spawned")
 if tx.backup:
  print(f"backup: {tx.backup}")
 print("done. The data/missions folder is untouched - other saves may ""use it")
def cmd_install_companion(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 entry=companion.script_entry(scene)
 if entry is not None:
  if entry["store"]==3:
   print("companion already installed in this save - it comes straight ""from the workshop, so Steam keeps it up to date (SWAM leaves ""those files alone)")
   return
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
  lk=lock.load(save.name)
  waiting=[n for n,rec in lk["addons"].items()if rec.get("pending_spawn")]
  for n in waiting:
   companion.queue_task(save,sid,{"action":"spawn_env","addon":n})
   lk["addons"][n]["pending_spawn"]=False
  if waiting:
   lock.store(save.name,lk)
   print(f"queued the structures of {len(waiting)} addon(s) added before "f"the companion existed: {', '.join(waiting)}")
 if tx.backup:
  print(f"backup: {tx.backup}")
 print(f"companion installed (script_id={sid}). It starts keeping the "f"provenance journal after the save is loaded; chat command: ?swam")
 if waiting:
  print("load the save once, wait for the \"[SWAM] tasks done\" chat ""message, then save the game")
def cmd_upgrade_addon(args):
 save=paths.save_dir(args.save)
 scene=Scene(save/"scene.xml")
 addons.backfill(save.name)
 lk=lock.load(save.name)
 name=args.addon
 if name not in lk["addons"]:
  raise SystemExit(f"addon '{name}' is not managed by SWAM - upgrade "f"only works for addons it installed")
 rec=lk["addons"][name]
 local_dir=paths.sw_root()/"data"/"missions"/name
 if not(local_dir/"playlist.xml").is_file():
  raise SystemExit(f"{local_dir} has no playlist.xml - the addon's local "f"files are gone, nothing to work from")
 src=addons.workshop_source(rec,name)
 local_changed=addons.local_changed(rec,name)
 ws_update=src is not None and addons.update_available(rec,name)
 if args.local and args.discard_local:
  raise SystemExit("--local and --discard-local mean opposite things - pick one")
 if args.discard_local and src is None:
  raise SystemExit(f"'{name}' has no workshop source to fall back to "f"(it was installed from local files)")
 from_workshop=bool(src)and not args.local and(ws_update or args.discard_local)
 if ws_update and local_changed and not(args.local or args.discard_local):
  raise SystemExit(f"the local copy of '{name}' has manual edits AND the "f"workshop has a newer version. Pick one:\n"f"  --local          keep your edits, refresh the save from them\n"f"  --discard-local  replace the local copy with the workshop version")
 if not from_workshop and not local_changed:
  print("already up to date (script.lua edits in data/missions apply on ""every load by themselves - only playlist and location files need ""an upgrade)")
  return
 if from_workshop and src.name!=name:
  raise SystemExit(f"the workshop version renamed the addon to "f"'{src.name}' - that changes save entries; "f"remove and re-add instead")
 sid=companion.script_id(scene)
 if sid is None:
  raise SystemExit("the companion is required for upgrades ""(swam install-companion)")
 shared=lock.other_saves_using(name,save.name)
 if shared:
  print(f"note: {len(shared)} other save(s) use the same files in "f"data/missions ({', '.join(shared[:3])}"f"{'...'if len(shared)>3 else''}). They get the new version too, "f"but their structures are only refreshed when you upgrade the "f"addon there as well")
 source_desc=str(src.disk_path)if from_workshop else f"local edits in {local_dir}"
 if args.dry_run:
  steps="despawn old structures -> replace files -> respawn"if from_workshop else"despawn old structures -> respawn from the edited local files"
  print(f"would upgrade '{name}' from {source_desc}\n({steps})")
  return
 import shutil
 stash=None
 with Transaction(save,f"upgrade-addon {name}",enabled=not args.no_backup)as tx:
  try:
   jr=companion.journal(save,sid).get(name,{})
   vehicles,objects=jr.get("v",{}),jr.get("o",{})
   if vehicles or objects:
    companion.queue_task(save,sid,{"action":"despawn","addon":name,"vehicles":vehicles,"objects":objects})
   if from_workshop:
    stash=local_dir.with_name(local_dir.name+".swam-old")
    if stash.exists():
     shutil.rmtree(stash)
    local_dir.rename(stash)
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
   rec["world_digest"]=addons.world_digest(local_dir)
   lock.store(save.name,lk)
  except BaseException:
   if stash is not None and stash.is_dir():
    if local_dir.exists():
     shutil.rmtree(local_dir)
    stash.rename(local_dir)
    print(f"restored the previous files of '{name}' in data/missions")
   raise
 if stash is not None and stash.is_dir():
  shutil.rmtree(stash)
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
 jr=companion.journal(save,sid)
 known_v={int(x)for rec in jr.values()for x in rec.get("v",{}).values()}
 known_o={int(x)for rec in jr.values()for x in rec.get("o",{}).values()}
 vids,oids,warns=geometry.match_all(scene.text,name,scene.list_playlists(),owned_elsewhere=known_v|known_o)
 for w in warns:
  print(f"  geometry: {w}")
 vids=[v for v in vids if v not in known_v]
 oids=[o for o in oids if o not in known_o]
 if not vids and not oids:
  print("no leftover structures of this addon matched - nothing to do")
  return
 if args.dry_run:
  print(f"(dry-run) would despawn {len(vids)} vehicles {sorted(vids)} "f"and {len(oids)} objects {sorted(oids)}")
  return
 with Transaction(save,f"cleanup {name}",enabled=not args.no_backup)as tx:
  companion.queue_task(save,sid,{"action":"despawn","addon":name,"vehicles":{i+1:float(v)for i,v in enumerate(sorted(vids))},"objects":{i+1:float(o)for i,o in enumerate(sorted(oids))}})
 if tx.backup:
  print(f"backup: {tx.backup}")
 print(f"queued: {len(vids)} vehicles and {len(oids)} objects will be "f"despawned on next world load (save the game afterwards)")
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
  seen_groups=set()
  for v in near:
   gid=v["group_id"]
   if gid in seen_groups:
    continue
   seen_groups.add(gid)
   if group_ok(gid):
    picked=v
    break
   if any(i in known for i in groups[gid]):
    print(f"mark {n}: skipping group {gid} - it belongs to a "f"managed addon (see swam journal); remove that addon "f"instead")
   else:
    print(f"mark {n}: skipping group {gid} - the game does not "f"mark it as addon-spawned (players built it?)")
  if picked is None:
   if not near:
    print(f"mark {n}: nothing within 100 m - skipped")
   else:
    print(f"mark {n}: nothing removable within 100 m - skipped")
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
 if args.dry_run:
  props={p.label:p for p in properties.read(save,name,scene)}
  unknown=[k for k in changes if k not in props]
  if unknown:
   raise SystemExit("no such setting: "+"; ".join(unknown))
  for label,raw in changes.items():
   p=props[label]
   cur=p.saved_value if p.saved_value is not None else p.default
   print(f"(dry-run) '{label}': {cur} -> {p.clamp(raw)}")
  print("(dry-run) nothing was written")
  return
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
 entry=companion.script_entry(scene)
 if entry is None:
  raise SystemExit("the companion is not installed in this save")
 sid=entry["script_id"]
 if not args.really:
  raise SystemExit("This deletes the provenance journal for this save - SWAM will ""forget who spawned what,\nand clean removal of addons installed ""so far becomes impossible.\nIf you mean it, re-run with --really")
 pv=companion.playlist_value(scene)
 if pv is not None:
  scene.remove_playlist(pv)
 scene.remove_script(entry["path"])
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
 if args.dry_run:
  print(f"(dry-run) would roll '{args.save}' back to {target['time']} "f"({target['operation']}), backing up the current state first")
  return
 ensure_game_closed()
 if not args.no_backup:
  make_backup(save,"pre-restore",keep=target["path"])
 restore_backup(save,target["path"])
 print(f"restored '{args.save}' from {target['time']} "f"({target['operation']})."+(""if args.no_backup else" The previous state was backed up as ""'pre-restore'."))
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
 addons.backfill(save.name)
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
   if addons.local_changed(rec,name):
    note+="  [local files edited: swam upgrade-addon --local]"
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
 sp.add_argument("--dry-run",action="store_true",help="show what would change, write nothing")
 sp.add_argument("--no-backup",action="store_true")
 sp.set_defaults(fn=cmd_settings)
 sp=sub.add_parser("restore",help="restore a save from a backup")
 sp.add_argument("save")
 sp.add_argument("time",nargs="?",help="backup timestamp (default: the newest)")
 sp.add_argument("--dry-run",action="store_true",help="show what would be restored, change nothing")
 sp.add_argument("--no-backup",action="store_true",help="do not back up the current state first ""(not recommended)")
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
