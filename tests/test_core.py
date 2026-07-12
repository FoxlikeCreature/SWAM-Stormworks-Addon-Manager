import os
import re
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
SCENE_TEMPLATE_RAW="""<?xml version="1.0" encoding="UTF-8"?>
<scene version="4" script_ui_id_counter="1" dlc="7">
\t<game_data day_tick="1" month="1" year="2030">
\t\t<active_playlists>
\t\t\t<playlist_name value="rom/data/missions/default_ai"/>
\t\t</active_playlists>
\t\t<active_mods>
\t\t\t<mod_path value="@MOD111@"/>
\t\t</active_mods>
\t</game_data>
\t<vehicles>
\t\t<vehicle_data/>
\t</vehicles>
\t<scripts>
\t\t<scripts>
\t\t\t<s store="1" path="data/missions/default_ai"/>
\t\t</scripts>
\t</scripts>
</scene>
"""
def scene_template()->str:
 from swam import paths
 return SCENE_TEMPLATE_RAW.replace("@MOD111@",paths.local_mod_game_path("111"))
@pytest.fixture()
def sw_root(tmp_path,monkeypatch):
 root=tmp_path/"Stormworks"
 (root/"saves"/"testsave"/"script_data").mkdir(parents=True)
 (root/"data"/"mods"/"111").mkdir(parents=True)
 (root/"data"/"mods"/"222").mkdir(parents=True)
 (root/"data"/"missions").mkdir(parents=True)
 scene=root/"saves"/"testsave"/"scene.xml"
 with open(scene,"w",encoding="utf-8",newline="")as f:
  f.write(scene_template())
 for mid,name in(("111","Installed Mod"),("222","Fresh Mod")):
  (root/"data"/"mods"/mid/"mod.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n'f'<mod name="{name}" author="t" desc="d" workshop_id="{mid}"/>\n')
 tuned=('freq = property.slider("Wave Interval (Mins)", 1, 60, 1, 15)\n''g_savedata = {\n''    interval = freq * 60 * 60,\n''    opts = { loud = property.checkbox("Loud Mode","false") },\n''}\n')
 for name,script in(("Zone Pack",""),("Logic Pack","x = 1\n"),("Tuned Pack",tuned)):
  d=root/"data"/"missions"/name
  d.mkdir()
  (d/"playlist.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n'f'<playlist path_id="app_data/data/missions/x" 'f'folder_path="data/missions/x" file_store="4" name="{name}">\n'f'\t<locations location_id_counter="1">\n\t\t<locations/>\n'f'\t</locations>\n</playlist>\n')
  (d/"script.lua").write_text(script)
 monkeypatch.setenv("SWAM_SW_ROOT",str(root))
 monkeypatch.setenv("SWAM_IGNORE_RUNNING","1")
 monkeypatch.setattr("swam.paths.SWAM_DATA",tmp_path/"swam_data")
 return root
def read_scene(root:Path)->str:
 with open(root/"saves"/"testsave"/"scene.xml",encoding="utf-8",newline="")as f:
  return f.read()
def run_cli(*argv):
 from swam.cli import main
 main(list(argv))
def test_mod_add_remove_roundtrip(sw_root):
 run_cli("add-mod","testsave","222","--no-backup")
 text=read_scene(sw_root)
 assert"data/mods/222"in text
 assert"\r"not in text,"newlines must stay LF on every platform"
 run_cli("remove-mod","testsave","222","--no-backup")
 assert read_scene(sw_root)==scene_template()
def test_duplicate_mod_refused(sw_root):
 with pytest.raises(SystemExit):
  run_cli("add-mod","testsave","111","--no-backup")
def test_scriptless_addon_cycle(sw_root):
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 text=read_scene(sw_root)
 assert'<playlist_name value="data/missions/Zone Pack"/>'in text
 assert"Zone Pack"not in text[text.rfind("<scripts>"):]
 run_cli("remove-addon","testsave","Zone Pack","--no-backup")
 assert read_scene(sw_root)==scene_template()
def test_scripted_addon_gets_script_id_and_gap_survives(sw_root):
 run_cli("install-companion","testsave","--no-backup")
 run_cli("add-addon","testsave","Logic Pack","--no-backup")
 text=read_scene(sw_root)
 assert'<s script_id="1" store="4" path="data/missions/SWAM Companion"/>'in text
 assert'<s script_id="2" store="4" path="data/missions/Logic Pack"/>'in text
 from swam import savedata
 data=savedata.load_file(sw_root/"saves"/"testsave"/"script_data"/"1.xml")
 assert data["tasks"][1]["action"]=="spawn_env"
 assert data["tasks"][1]["addon"]=="Logic Pack"
 run_cli("remove-addon","testsave","Logic Pack","--no-backup")
 text=read_scene(sw_root)
 assert"Logic Pack"not in text
 assert'<s script_id="1" store="4" path="data/missions/SWAM Companion"/>'in text
def test_verify_clean_and_detects_missing_folder(sw_root):
 from swam import verify,paths
 assert verify.run(paths.save_dir("testsave"))==[]
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 import shutil
 shutil.rmtree(sw_root/"data"/"missions"/"Zone Pack")
 problems=verify.run(paths.save_dir("testsave"))
 assert any("Zone Pack"in p for p in problems)
def test_savedata_codec_roundtrip_tricky_values():
 from swam import savedata
 original={"s":"multi\nline \"quoted\" & <tagged>","n":2.5,"whole":3.0,"flag":True,"off":False,"nested":{1:"a",2:{"deep":{}},"empty":{}},7:1.0,}
 assert savedata.parse(savedata.dump(original))==original
def test_settings_schema_and_full_apply_cycle(sw_root):
 run_cli("install-companion","testsave","--no-backup")
 run_cli("add-addon","testsave","Tuned Pack","--no-backup")
 from swam import paths,properties,savedata
 from swam.scene import Scene
 save=paths.save_dir("testsave")
 scene=Scene(save/"scene.xml")
 props={p.label:p for p in properties.read(save,"Tuned Pack",scene)}
 slider=props["Wave Interval (Mins)"]
 assert(slider.minimum,slider.maximum,slider.default)==(1,60,15)
 assert slider.saved_path==("interval",)and slider.saved_scale==3600
 assert props["Loud Mode"].saved_path==("opts","loud")
 sid=properties._script_id(scene,"Tuned Pack")
 savedata.save_file(save/"script_data"/f"{sid}.xml",{"interval":15*3600.0,"opts":{"loud":False}})
 run_cli("settings","testsave","Tuned Pack","--no-backup","--set","Wave Interval (Mins)=30","--set","Loud Mode=on")
 text=(sw_root/"data"/"missions"/"Tuned Pack"/"script.lua").read_text()
 assert'"Wave Interval (Mins)", 1, 60, 1, 30'in text
 assert'"Loud Mode","true"'in text
 data=savedata.load_file(save/"script_data"/f"{sid}.xml")
 assert data["interval"]==30*3600
 assert data["opts"]["loud"]is True
 props={p.label:p for p in properties.read(save,"Tuned Pack",scene)}
 assert props["Wave Interval (Mins)"].saved_value==30
 assert props["Loud Mode"].saved_value is True
 run_cli("settings","testsave","Tuned Pack","--no-backup","--set","Wave Interval (Mins)=999")
 text=(sw_root/"data"/"missions"/"Tuned Pack"/"script.lua").read_text()
 assert'"Wave Interval (Mins)", 1, 60, 1, 60'in text
 with pytest.raises(SystemExit,match="no such setting"):
  run_cli("settings","testsave","Tuned Pack","--no-backup","--set","Nonsense=1")
 from swam import lock
 rec=lock.load("testsave")["addons"]["Tuned Pack"]
 assert rec["settings"]["Wave Interval (Mins)"]==60
 assert rec["settings"]["Loud Mode"]is True
 assert rec["source"]=="local"and rec["world_digest"]
GEO_SCENE="""
<vehicles>
\t<vehicle id="50" vehicle_group_id="7" is_mission="true" is_static="true">
\t\t<transform 30="3010.0" 31="11.5" 32="4020.0"/>
\t\t<authors/>
\t</vehicle>
\t<vehicle id="60" vehicle_group_id="8">
\t\t<transform 30="8010.0" 31="11.5" 32="9020.0"/>
\t\t<authors><a name="player"/></authors>
\t</vehicle>
</vehicles>
<vehicle_group_data>
\t<group id="7">
\t\t<vehicles><v value="50"/></vehicles>
\t\t<initial_transform 30="3010.0" 31="11.5" 32="4020.0"/>
\t</group>
\t<group id="8">
\t\t<vehicles><v value="60"/></vehicles>
\t\t<initial_transform 30="8010.0" 31="11.5" 32="9020.0"/>
\t</group>
</vehicle_group_data>
"""
TOWER_PLAYLIST=('<?xml version="1.0" encoding="UTF-8"?>\n''<playlist path_id="x" folder_path="x" file_store="4" name="Tower Pack">\n''\t<locations location_id_counter="2">\n\t\t<locations>\n''\t\t\t<l id="1" tile="data/tiles/t.xml" is_env_mod="true">\n''\t\t\t\t<components>\n''\t\t\t\t\t<c component_type="3" id="1">\n''\t\t\t\t\t\t<spawn_transform 30="10.0" 31="20.0" 32="20.875"/>\n''\t\t\t\t\t\t<spawn_local_offset y="-8.5" z="-0.875"/>\n''\t\t\t\t\t</c>\n''\t\t\t\t</components>\n''\t\t\t</l>\n''\t\t</locations>\n\t</locations>\n</playlist>\n')
def test_geometry_offset_settling_and_player_protection(sw_root):
 d=sw_root/"data"/"missions"/"Tower Pack"
 d.mkdir()
 (d/"playlist.xml").write_text(TOWER_PLAYLIST)
 (d/"script.lua").write_text("")
 from swam import geometry
 vids,warns=geometry.match(GEO_SCENE,"Tower Pack",[])
 assert vids==[50],warns
 settled=GEO_SCENE.replace('30="3010.0" 31="11.5" 32="4020.0"','30="3010.0" 31="10.6" 32="4019.1"')
 vids,warns=geometry.match(settled,"Tower Pack",[])
 assert vids==[50],"physics settling within tolerance must still match"
 far=GEO_SCENE.replace('30="3010.0" 31="11.5" 32="4020.0"','30="3010.0" 31="11.5" 32="4025.0"')
 vids,_=geometry.match(far,"Tower Pack",[])
 assert vids==[]
 player_spot=GEO_SCENE.replace('id="60" vehicle_group_id="8"','id="60" vehicle_group_id="8" ''is_mission="true"').replace('30="8010.0" 31="11.5" 32="9020.0"','30="7010.0" 31="11.5" 32="7020.0"')
 vids,warns=geometry.match(player_spot,"Tower Pack",[])
 assert 60 not in vids,"authored vehicles must never match"
ROTATED_PLAYLIST=('<?xml version="1.0" encoding="UTF-8"?>\n''<playlist path_id="x" folder_path="x" file_store="4" name="Rot Pack">\n''\t<locations location_id_counter="3">\n\t\t<locations>\n''\t\t\t<l id="1" tile="data/tiles/t.xml" is_env_mod="true">\n''\t\t\t\t<components>\n''\t\t\t\t\t<c component_type="3" id="1">\n''\t\t\t\t\t\t<spawn_transform 00="0" 02="-1" 20="1" 22="0" ''30="100.0" 31="5.0" 32="200.0"/>\n''\t\t\t\t\t\t<spawn_local_offset x="3.25" y="-9" z="-1"/>\n''\t\t\t\t\t</c>\n''\t\t\t\t</components>\n''\t\t\t</l>\n''\t\t\t<l id="2" name="drop_off">\n''\t\t\t\t<components>\n''\t\t\t\t\t<c component_type="3" id="2">\n''\t\t\t\t\t\t<spawn_transform 30="0.0" 31="0.0" 32="0.0"/>\n''\t\t\t\t\t</c>\n''\t\t\t\t</components>\n''\t\t\t</l>\n''\t\t</locations>\n\t</locations>\n</playlist>\n')
ROT_SCENE="""
<vehicles>
\t<vehicle id="50" vehicle_group_id="7" is_mission="true" is_static="true">
\t\t<transform 30="99.0" 31="-4.0" 32="196.75"/>
\t\t<authors/>
\t</vehicle>
\t<vehicle id="60" vehicle_group_id="8" is_mission="true" is_static="true">
\t\t<transform 30="1000.0" 31="0.0" 32="0.0"/>
\t\t<authors/>
\t</vehicle>
</vehicles>
<vehicle_group_data>
\t<group id="7">
\t\t<vehicles><v value="50"/></vehicles>
\t\t<initial_transform 30="99.0" 31="-4.0" 32="196.75"/>
\t</group>
\t<group id="8">
\t\t<vehicles><v value="60"/></vehicles>
\t\t<initial_transform 30="1000.0" 31="0.0" 32="0.0"/>
\t</group>
</vehicle_group_data>
"""
def test_geometry_rotated_offset_and_tileless_locations(sw_root):
 d=sw_root/"data"/"missions"/"Rot Pack"
 d.mkdir()
 (d/"playlist.xml").write_text(ROTATED_PLAYLIST)
 (d/"script.lua").write_text("")
 from swam import geometry
 vids,warns=geometry.match(ROT_SCENE,"Rot Pack",[])
 assert vids==[50],("the local offset must be rotated by the spawn "f"transform, not added along world axes: {warns}")
 assert 60 not in vids,("a location with no tile has no world coordinates - ""its components must never claim anything")
def test_refresh_finds_structures_after_you_edited_the_playlist(sw_root):
 d=sw_root/"data"/"missions"/"Tower Pack"
 d.mkdir()
 (d/"playlist.xml").write_text(TOWER_PLAYLIST)
 (d/"script.lua").write_text("")
 from swam import geometry,snapshot
 snapshot.record("testsave","Tower Pack",d)
 moved=TOWER_PLAYLIST.replace('30="10.0" 31="20.0" 32="20.875"','30="90.0" 31="20.0" 32="20.875"')
 (d/"playlist.xml").write_text(moved)
 vids,_=geometry.match(GEO_SCENE,"Tower Pack",[])
 assert vids==[],"sanity: the edited playlist no longer points at the tower"
 assert snapshot.edited("testsave","Tower Pack",d)
 vids,warns=geometry.match(GEO_SCENE,"Tower Pack",[],target_playlist=snapshot.recorded("testsave","Tower Pack"))
 assert vids==[50],("the tower must still be found through the playlist recorded "f"before the edit: {warns}")
def test_builtin_addon_removal(sw_root):
 run_cli("remove-addon","testsave","default_ai","--no-backup")
 text=read_scene(sw_root)
 assert'rom/data/missions/default_ai'not in text
 assert'path="data/missions/default_ai"'not in text,("the script entry of a built-in addon is stored without the "'"rom/" prefix - it must be removed with the playlist entry, '"or the game keeps running the script")
def test_remove_marked_with_identical_twins(sw_root):
 run_cli("install-companion","testsave","--no-backup")
 from swam import companion,paths,savedata
 from swam.scene import Scene
 save=paths.save_dir("testsave")
 scene=Scene(save/"scene.xml")
 sid=companion.script_id(scene)
 text=scene.text.replace("\t<vehicles>\n\t\t<vehicle_data/>\n\t</vehicles>","\t<vehicles>\n"'\t\t<vehicle id="50" vehicle_group_id="7" is_mission="true">\n''\t\t\t<transform 30="100.0" 31="5.0" 32="100.0"/>\n'"\t\t\t<authors/>\n\t\t</vehicle>\n"'\t\t<vehicle id="60" vehicle_group_id="8" is_mission="true">\n''\t\t\t<transform 30="5100.0" 31="5.0" 32="5100.0"/>\n'"\t\t\t<authors/>\n\t\t</vehicle>\n"'\t\t<vehicle id="70" vehicle_group_id="9">\n''\t\t\t<transform 30="102.0" 31="5.0" 32="102.0"/>\n'"\t\t\t<authors><a name=\"player\"/></authors>\n\t\t</vehicle>\n""\t</vehicles>")
 with open(save/"scene.xml","w",encoding="utf-8",newline="")as f:
  f.write(text)
 (save/"vehicles").mkdir()
 for vid,blob in((50,b"towerdata"),(60,b"towerdata"),(70,b"playerdata")):
  (save/"vehicles"/f"{vid}.xml.bin").write_bytes(blob)
 data=companion.load_data(save,sid)
 data["marks"]={1:{"x":101.0,"y":5.0,"z":101.0}}
 savedata.save_file(save/"script_data"/f"{sid}.xml",data)
 run_cli("remove-marked","testsave","--all","--no-backup")
 data=companion.load_data(save,sid)
 task=data["tasks"][max(k for k in data["tasks"]if isinstance(k,int))]
 assert task["action"]=="despawn"
 assert sorted(task["vehicles"].values())==[50.0,60.0]
 assert data["marks"]=={}
def test_all_modules_import_with_eager_annotations():
 import importlib
 import inspect
 import typing
 for name in("paths","scene","backup","lock","mods","addons","verify","savedata","companion","geometry","catalog","guard","interactive","cli","gui","properties","snapshot"):
  m=importlib.import_module(f"swam.{name}")
  for obj in vars(m).values():
   if inspect.isfunction(obj):
    typing.get_type_hints(obj)
   elif inspect.isclass(obj)and obj.__module__==m.__name__:
    for member in vars(obj).values():
     if inspect.isfunction(member):
      typing.get_type_hints(member)
def test_game_path_strings():
 from swam import paths
 p=Path("C:/lib/steamapps/workshop/content/573090/42")if paths.IS_WINDOWS else Path("/lib/steamapps/workshop/content/573090/42")
 s=paths.game_path_string(p)
 if paths.IS_WINDOWS:
  assert s.endswith("573090\\42")and":"in s
 else:
  assert s=="Z:\\lib\\steamapps\\workshop\\content\\573090\\42"
 assert paths.local_mod_game_path("42").endswith("Stormworks\\data/mods/42")
def test_missing_saves_folder_is_a_friendly_refusal(tmp_path,monkeypatch):
 root=tmp_path/"Stormworks"
 root.mkdir()
 monkeypatch.setenv("SWAM_SW_ROOT",str(root))
 from swam import paths
 with pytest.raises(SystemExit,match="saves"):
  paths.saves_dir()
def test_restore_backup_roundtrip(sw_root,tmp_path):
 run_cli("add-mod","testsave","222")
 assert"data/mods/222"in read_scene(sw_root)
 run_cli("restore","testsave")
 assert read_scene(sw_root)==scene_template()
 from swam.backup import list_backups
 assert any(e["operation"]=="pre-restore"for e in list_backups("testsave"))
def test_companion_found_when_subscribed_from_workshop(sw_root,tmp_path):
 from swam import companion,paths
 from swam.scene import Scene
 ws=tmp_path/"ws"/"123456"/"playlist"
 ws.mkdir(parents=True)
 (ws/"playlist.xml").write_text('<playlist path_id="x" folder_path="x" file_store="3" ''name="SWAM Companion">\n</playlist>\n')
 scene=Scene(paths.save_dir("testsave")/"scene.xml")
 game_path=paths.game_path_string(ws)
 scene.add_script(game_path,store=3)
 assert companion.script_id(scene)is not None
 assert companion.is_installed(scene)
def companion_data(sw_root):
 from swam import savedata
 return savedata.load_file(sw_root/"saves"/"testsave"/"script_data"/"1.xml")
def test_upgrade_from_edited_local_copy(sw_root):
 run_cli("install-companion","testsave","--no-backup")
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 from swam import addons,lock
 rec=lock.load("testsave")["addons"]["Zone Pack"]
 assert rec["source"]=="local"
 assert not addons.local_changed(rec,"Zone Pack")
 pl=sw_root/"data"/"missions"/"Zone Pack"/"playlist.xml"
 pl.write_text(pl.read_text().replace('location_id_counter="1"','location_id_counter="2"'))
 assert addons.local_changed(rec,"Zone Pack")
 run_cli("upgrade-addon","testsave","Zone Pack","--no-backup")
 rec=lock.load("testsave")["addons"]["Zone Pack"]
 assert not addons.local_changed(rec,"Zone Pack")
 tasks=companion_data(sw_root)["tasks"]
 assert[t["action"]for t in tasks.values()]==["spawn_env"]
 run_cli("upgrade-addon","testsave","Zone Pack","--local","--no-backup")
 assert len(companion_data(sw_root)["tasks"])==1
def test_local_edits_are_detected_beyond_the_playlist(sw_root):
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 from swam import addons,lock
 rec=lock.load("testsave")["addons"]["Zone Pack"]
 (sw_root/"data"/"missions"/"Zone Pack"/"vehicle_1.xml").write_text("<vehicle/>")
 assert addons.local_changed(rec,"Zone Pack")
def test_script_edits_alone_are_not_an_upgrade(sw_root):
 run_cli("install-companion","testsave","--no-backup")
 run_cli("add-addon","testsave","Logic Pack","--no-backup")
 from swam import addons,lock
 s=sw_root/"data"/"missions"/"Logic Pack"/"script.lua"
 s.write_text("x = 2\n")
 rec=lock.load("testsave")["addons"]["Logic Pack"]
 assert not addons.local_changed(rec,"Logic Pack")
def test_pending_spawn_is_cancelled_when_the_addon_is_removed(sw_root):
 run_cli("install-companion","testsave","--no-backup")
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 assert len(companion_data(sw_root)["tasks"])==1
 run_cli("remove-addon","testsave","Zone Pack","--no-backup")
 assert companion_data(sw_root)["tasks"]=={}
def test_restore_never_prunes_the_backup_it_restores_from(sw_root):
 from swam.backup import KEEP_BACKUPS,list_backups,make_backup
 from swam import paths
 save=paths.save_dir("testsave")
 for i in range(KEEP_BACKUPS):
  make_backup(save,f"filler {i}")
 entries=list_backups("testsave")
 assert len(entries)==KEEP_BACKUPS
 target=entries[-1]
 run_cli("restore","testsave",target["time"])
 assert target["path"].is_dir(),"the backup being restored was pruned"
 ops=[e["operation"]for e in list_backups("testsave")]
 assert"pre-restore"in ops
 assert target["time"]in[e["time"]for e in list_backups("testsave")]
def test_workshop_installed_companion_can_be_uninstalled(sw_root,tmp_path):
 from swam import companion,paths
 from swam.scene import Scene
 ws=tmp_path/"ws"/"777"/"playlist"
 ws.mkdir(parents=True)
 (ws/"playlist.xml").write_text('<playlist path_id="x" folder_path="x" file_store="3" ''name="SWAM Companion">\n</playlist>\n')
 game_path=paths.game_path_string(ws)
 scene=Scene(paths.save_dir("testsave")/"scene.xml")
 scene.add_playlist(game_path)
 scene.add_script(game_path,store=3)
 scene.write()
 run_cli("uninstall-companion","testsave","--really","--no-backup")
 text=read_scene(sw_root)
 assert game_path not in text
 assert not companion.is_installed(Scene(paths.save_dir("testsave")/"scene.xml"))
def test_rapid_backups_never_collide_and_keep_the_newest(sw_root):
 from swam.backup import KEEP_BACKUPS,KEEP_PRE_RESTORE,list_backups,make_backup
 from swam import paths
 save=paths.save_dir("testsave")
 for i in range(KEEP_BACKUPS+4):
  make_backup(save,f"op{i}")
 kept=[e["operation"]for e in list_backups("testsave")]
 assert kept==[f"op{i}"for i in range(KEEP_BACKUPS+3,KEEP_BACKUPS-2,-1)]
 for _ in range(KEEP_PRE_RESTORE+1):
  make_backup(save,"pre-restore")
 ops=[e["operation"]for e in list_backups("testsave")]
 assert ops.count("pre-restore")==KEEP_PRE_RESTORE
 assert len([o for o in ops if o!="pre-restore"])==KEEP_BACKUPS
def test_changing_several_settings_at_once_keeps_the_script_valid(sw_root):
 from swam import properties
 src=('a = property.slider("Alpha", 1, 60, 1, 15)\n''b = property.checkbox("Beta", "false")\n''c = property.slider("Gamma", 0, 100, 5, 50)\n')
 d=sw_root/"data"/"missions"/"Multi Pack"
 d.mkdir()
 (d/"playlist.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n''<playlist path_id="x" folder_path="x" file_store="4" name="Multi Pack">\n''\t<locations location_id_counter="1">\n\t\t<locations/>\n''\t</locations>\n</playlist>\n')
 (d/"script.lua").write_text(src)
 run_cli("add-addon","testsave","Multi Pack","--no-backup")
 run_cli("settings","testsave","Multi Pack","--no-backup","--set","Alpha=5","--set","Beta=on","--set","Gamma=25")
 text=(d/"script.lua").read_text()
 assert'property.slider("Alpha", 1, 60, 1, 5)'in text
 assert'property.checkbox("Beta", "true")'in text
 assert'property.slider("Gamma", 0, 100, 5, 25)'in text
 assert len({p.label for p in properties.parse_schema(text)})==3
def test_slider_refuses_nonsense_values(sw_root):
 run_cli("add-addon","testsave","Tuned Pack","--no-backup")
 with pytest.raises(SystemExit,match="needs a number"):
  run_cli("settings","testsave","Tuned Pack","--no-backup","--set","Wave Interval (Mins)=soon")
def test_addon_names_hostile_to_windows_are_refused(sw_root):
 d=sw_root/"data"/"missions"/"Trailing Space"
 d.mkdir()
 (d/"playlist.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n''<playlist path_id="x" folder_path="x" file_store="4" name="Trailing Space ">\n''</playlist>\n')
 with pytest.raises(SystemExit,match="cannot become a folder"):
  run_cli("add-addon","testsave","Trailing Space","--no-backup")
def test_workshop_attached_addon_is_visible_and_removable(sw_root,tmp_path):
 from swam import addons,paths
 from swam.scene import Scene
 ws=tmp_path/"ws"/"424242"/"playlist"
 ws.mkdir(parents=True)
 (ws/"playlist.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n''<playlist path_id="x" folder_path="x" file_store="3" name="Straight From Workshop">\n''\t<locations location_id_counter="1">\n\t\t<locations/>\n''\t</locations>\n</playlist>\n')
 value=paths.game_path_string(ws)
 scene=Scene(paths.save_dir("testsave")/"scene.xml")
 scene.add_playlist(value)
 scene.write()
 scene=Scene(paths.save_dir("testsave")/"scene.xml")
 assert addons.playlist_name(value)=="Straight From Workshop"
 assert addons.attached_value(scene,"Straight From Workshop")==value
 run_cli("remove-addon","testsave","Straight From Workshop","--force","--no-backup")
 assert value not in read_scene(sw_root)
def test_save_without_mods_can_still_be_edited(sw_root):
 scene_path=sw_root/"saves"/"testsave"/"scene.xml"
 with open(scene_path,encoding="utf-8",newline="")as f:
  text=f.read()
 empty=re.sub(r"<active_mods>.*?</active_mods>","<active_mods/>",text,flags=re.S)
 with open(scene_path,"w",encoding="utf-8",newline="")as f:
  f.write(empty)
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 assert'<playlist_name value="data/missions/Zone Pack"/>'in read_scene(sw_root)
 run_cli("add-mod","testsave","222","--no-backup")
 run_cli("remove-mod","testsave","222","--no-backup")
 assert"<active_mods/>"in read_scene(sw_root),"an emptied block must collapse back"
 run_cli("remove-addon","testsave","Zone Pack","--no-backup")
 assert read_scene(sw_root)==empty
def test_adding_the_same_addon_twice_is_refused(sw_root):
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 with pytest.raises(SystemExit,match="already attached"):
  run_cli("add-addon","testsave","Zone Pack","--no-backup")
def test_verify_notices_a_missing_workshop_playlist(sw_root,tmp_path):
 from swam import paths,verify
 from swam.scene import Scene
 gone=paths.game_path_string(tmp_path/"ws"/"9999"/"playlist")
 scene=Scene(paths.save_dir("testsave")/"scene.xml")
 scene.add_playlist(gone)
 scene.write()
 problems=verify.run(paths.save_dir("testsave"))
 assert any("playlist missing on disk"in p for p in problems)
def test_property_without_a_default_gets_one_instead_of_losing_its_label(sw_root):
 from swam import properties
 d=sw_root/"data"/"missions"/"Bare Pack"
 d.mkdir()
 (d/"playlist.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n''<playlist path_id="x" folder_path="x" file_store="4" name="Bare Pack">\n''\t<locations location_id_counter="1">\n\t\t<locations/>\n''\t</locations>\n</playlist>\n')
 (d/"script.lua").write_text('loud = property.checkbox("Loud")\n')
 run_cli("add-addon","testsave","Bare Pack","--no-backup")
 run_cli("settings","testsave","Bare Pack","--no-backup","--set","Loud=on")
 text=(d/"script.lua").read_text()
 assert'property.checkbox("Loud", "true")'in text
 assert[p.label for p in properties.parse_schema(text)]==["Loud"]
def test_commented_out_properties_are_ignored(sw_root):
 from swam import properties
 src=('-- old = property.slider("Ghost", 1, 10, 1, 5)\n''--[[ dead = property.checkbox("Buried") ]]\n''real = property.checkbox("Real", "false")\n')
 assert[p.label for p in properties.parse_schema(src)]==["Real"]
def test_restore_rolls_back_the_lock_file_too(sw_root):
 from swam import lock,paths,verify
 run_cli("add-addon","testsave","Zone Pack")
 assert"Zone Pack"in lock.load("testsave")["addons"]
 run_cli("restore","testsave")
 assert lock.load("testsave")["addons"]=={},"the lock must roll back with the save"
 assert verify.run(paths.save_dir("testsave"))==[]
 run_cli("restore","testsave")
 assert"Zone Pack"in lock.load("testsave")["addons"]
 assert verify.run(paths.save_dir("testsave"))==[]
def test_lock_knows_which_saves_share_an_addon(sw_root):
 from swam import lock
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 other=lock.load("other")
 other["addons"]["Zone Pack"]=lock.addon_record("Zone Pack","data/missions/Zone Pack",False,"x")
 lock.store("other",other)
 assert lock.other_saves_using("Zone Pack","testsave")==["other"]
 assert lock.other_saves_using("Zone Pack","other")==["testsave"]
def test_addon_name_with_xml_escapes(sw_root):
 from swam import addons,lock,paths,verify,companion,savedata
 from swam.scene import Scene
 A="Search & Rescue"
 d=sw_root/"data"/"missions"/A
 d.mkdir()
 (d/"playlist.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n''<playlist path_id="x" folder_path="x" file_store="4" name="Search &amp; Rescue">\n''\t<locations location_id_counter="1">\n\t\t<locations/>\n''\t</locations>\n</playlist>\n')
 run_cli("install-companion","testsave","--no-backup")
 before=read_scene(sw_root)
 run_cli("add-addon","testsave",A,"--no-backup")
 text=read_scene(sw_root)
 assert'<playlist_name value="data/missions/Search &amp; Rescue"/>'in text
 assert addons.resolve_addon(A).name==A
 assert A in lock.load("testsave")["addons"]
 sid=companion.script_id(Scene(paths.save_dir("testsave")/"scene.xml"))
 task=list(companion.load_data(paths.save_dir("testsave"),sid)["tasks"].values())[-1]
 assert task["addon"]==A,"the game looks the addon up by its real name"
 assert verify.run(paths.save_dir("testsave"))==[]
 run_cli("remove-addon","testsave",A,"--no-backup")
 assert read_scene(sw_root)==before
def test_a_save_with_no_addons_at_all(sw_root):
 scene_path=sw_root/"saves"/"testsave"/"scene.xml"
 bare=('<?xml version="1.0" encoding="UTF-8"?>\n<scene version="4">\n''\t<game_data day_tick="1">\n\t\t<active_playlists/>\n''\t\t<active_mods/>\n\t</game_data>\n\t<scripts>\n''\t\t<scripts/>\n\t</scripts>\n</scene>\n')
 with open(scene_path,"w",encoding="utf-8",newline="")as f:
  f.write(bare)
 run_cli("add-addon","testsave","Logic Pack","--no-backup")
 text=read_scene(sw_root)
 assert'<playlist_name value="data/missions/Logic Pack"/>'in text
 assert'store="4" path="data/missions/Logic Pack"'in text
 run_cli("remove-addon","testsave","Logic Pack","--no-backup")
 assert read_scene(sw_root)==bare,"an addon-less save must come back exactly as it was"
def test_corrupted_files_are_refused_with_a_clear_message(sw_root):
 from swam import paths,savedata
 scene_path=paths.save_dir("testsave")/"scene.xml"
 with open(scene_path,encoding="utf-8",newline="")as f:
  good=f.read()
 with open(scene_path,"w",encoding="utf-8",newline="")as f:
  f.write(good[:len(good)//2])
 with pytest.raises(SystemExit,match="damaged"):
  run_cli("list","testsave")
 with open(scene_path,"w",encoding="utf-8",newline="")as f:
  f.write(good)
 sd=paths.save_dir("testsave")/"script_data"/"9.xml"
 sd.write_text("")
 with pytest.raises(SystemExit,match="not readable as addon state"):
  savedata.load_file(sd)
def test_journal_beats_geometry_when_they_disagree(sw_root):
 from swam import geometry
 d=sw_root/"data"/"missions"/"Tower Pack"
 d.mkdir()
 (d/"playlist.xml").write_text(TOWER_PLAYLIST)
 vids,_=geometry.match(GEO_SCENE,"Tower Pack",[])
 assert 50 in vids,"the matcher normally claims this structure"
 vids2,warns=geometry.match(GEO_SCENE,"Tower Pack",[],owned_elsewhere={50})
 assert 50 not in vids2,"a vehicle the journal gives to another addon is never claimed"
 assert any("journal"in w for w in warns)
def test_addon_added_before_the_companion_spawns_later(sw_root):
 from swam import companion,lock,paths,savedata
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 assert lock.load("testsave")["addons"]["Zone Pack"]["pending_spawn"]is True
 run_cli("install-companion","testsave","--no-backup")
 sid=1
 data=savedata.load_file(paths.save_dir("testsave")/"script_data"/f"{sid}.xml")
 tasks=[t for t in data["tasks"].values()if t["addon"]=="Zone Pack"]
 assert tasks and tasks[0]["action"]=="spawn_env"
 assert lock.load("testsave")["addons"]["Zone Pack"]["pending_spawn"]is False
ZONE_PLAYLIST=('<?xml version="1.0" encoding="UTF-8"?>\n''<playlist path_id="x" folder_path="x" file_store="4" name="Zones Only">\n''\t<locations location_id_counter="2">\n\t\t<locations>\n''\t\t\t<l id="1" tile="data/tiles/t.xml" is_env_mod="true">\n''\t\t\t\t<components>\n''\t\t\t\t\t<c component_type="10" id="1">\n''\t\t\t\t\t\t<spawn_transform 30="3010.0" 31="11.5" 32="4020.0"/>\n''\t\t\t\t\t</c>\n''\t\t\t\t</components>\n''\t\t\t</l>\n''\t\t</locations>\n\t</locations>\n</playlist>\n')
def test_a_zone_only_addon_never_claims_vehicles(sw_root):
 from swam import geometry
 d=sw_root/"data"/"missions"/"Zones Only"
 d.mkdir()
 (d/"playlist.xml").write_text(ZONE_PLAYLIST)
 vids,oids,warns=geometry.match_all(GEO_SCENE,"Zones Only",["data/missions/Zones Only"])
 assert vids==[],"zone spawn points must never claim vehicles standing on them"
 assert oids==[]
def test_objects_are_matched_and_despawned_too(sw_root):
 from swam import geometry
 d=sw_root/"data"/"missions"/"Prop Pack"
 d.mkdir()
 pl=TOWER_PLAYLIST.replace('component_type="3"','component_type="2"').replace("Tower Pack","Prop Pack")
 (d/"playlist.xml").write_text(pl)
 scene=('<dynamics object_counter="9">\n''\t<object type="24" id="77" char_steam_id="-1" is_mission="true">\n''\t\t<transform 30="3010.0" 31="11.5" 32="4020.0"/>\n''\t</object>\n''\t<object type="24" id="78" char_steam_id="-1">\n''\t\t<transform 30="3010.0" 31="11.5" 32="4020.0"/>\n''\t</object>\n</dynamics>\n')
 vids,oids,warns=geometry.match_all(scene,"Prop Pack",["data/missions/Prop Pack"])
 assert oids==[77],"only the game-attested object is claimed"
 assert any("not mark it as addon-spawned"in w for w in warns)
def test_a_failed_backup_leaves_nothing_behind(sw_root,monkeypatch):
 import shutil
 from swam import backup,paths
 def boom(src,dst,*a,**k):
  Path(dst).mkdir(parents=True,exist_ok=True)
  (Path(dst)/"half.xml").write_text("partial")
  raise OSError(28,"No space left on device")
 monkeypatch.setattr(shutil,"copytree",boom)
 with pytest.raises(SystemExit,match="backup of 'testsave' failed"):
  backup.make_backup(paths.save_dir("testsave"),"test")
 assert backup.list_backups("testsave")==[]
 root=backup.backups_root("testsave")
 assert not any(root.iterdir())if root.is_dir()else True
def test_half_written_backups_are_never_offered(sw_root):
 from swam import backup,paths
 good=backup.make_backup(paths.save_dir("testsave"),"real")
 half=backup.backups_root("testsave")/"20990101-000000"
 half.mkdir()
 (half/"scene.xml").write_text("truncated")
 offered=[e["time"]for e in backup.list_backups("testsave")]
 assert offered==[good.name],"a backup without its meta file is not a backup"
def test_two_swam_operations_cannot_overlap(sw_root):
 import os
 from swam import backup
 held=backup._busy_path("testsave")
 held.parent.mkdir(parents=True,exist_ok=True)
 held.write_text(str(os.getppid()))
 with pytest.raises(SystemExit,match="another SWAM operation"):
  run_cli("add-addon","testsave","Zone Pack","--no-backup")
 backup.release(held)
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 assert'data/missions/Zone Pack'in read_scene(sw_root)
 assert not list((backup.paths.SWAM_DATA/"locks").glob("*.busy")),"the lock is released afterwards"
def test_a_stale_lock_from_a_dead_process_is_taken_over(sw_root):
 from swam import backup
 p=backup._busy_path("testsave")
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text("999999")
 run_cli("add-addon","testsave","Zone Pack","--no-backup")
 assert'data/missions/Zone Pack'in read_scene(sw_root)
