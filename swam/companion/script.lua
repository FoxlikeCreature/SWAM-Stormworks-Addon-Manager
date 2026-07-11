local TICK_DELAY = 120
local KEEP_REPORTS = 20
local g_tick = 0
local g_tasks_done = false
local function ensure(t, k, default)
if t[k] == nil then t[k] = default end
return t[k]
end
local function count(t)
local n = 0
if type(t) == "table" then
for _ in pairs(t) do n = n + 1 end
end
return n
end
local function next_index(t)
local max = 0
for k in pairs(t) do
if type(k) == "number" and k > max then max = k end
end
return max + 1
end
local function init_savedata()
if type(g_savedata) ~= "table" then g_savedata = {} end
ensure(g_savedata, "journal", {})
ensure(g_savedata, "tasks", {})
ensure(g_savedata, "report", {})
end
function onCreate(is_world_create)
init_savedata()
end
local function report(n, text)
g_savedata.report[n] = text
server.announce("[SWAM]", text)
debug.log("[SWAM] " .. text)
end
function onSpawnAddonComponent(id, component_name, type_string, addon_index)
init_savedata()
local adata = server.getAddonData(addon_index)
local aname = adata and adata.name or ("index_" .. tostring(addon_index))
local rec = ensure(g_savedata.journal, aname, {})
local kind = (type_string == "vehicle") and "v" or "o"
local list = ensure(rec, kind, {})
list[next_index(list)] = id
end
function onVehicleDespawn(vehicle_id, peer_id)
if type(g_savedata) ~= "table" or g_savedata.journal == nil then return end
for _, rec in pairs(g_savedata.journal) do
if rec.v then
for i, id in pairs(rec.v) do
if id == vehicle_id then rec.v[i] = nil end
end
end
end
end
local function do_spawn_env(task)
local ai, ok = server.getAddonIndex(task.addon)
if not ok then return "addon not found: " .. tostring(task.addon) end
local adata = server.getAddonData(ai)
if adata == nil then return "no addon data: " .. tostring(task.addon) end
local spawned, skipped, failed = 0, 0, 0
for li = 0, (adata.location_count or 0) - 1 do
local ldata = server.getLocationData(ai, li)
if ldata ~= nil and ldata.env_mod and ldata.tile ~= nil and ldata.tile ~= "" then
local tm, tok = server.getTileTransform(
matrix.translation(0, 0, 0), ldata.tile, 100000)
if tok then
local _, sok = server.spawnAddonLocation(tm, ai, li)
if sok then spawned = spawned + 1 else failed = failed + 1 end
else
skipped = skipped + 1
end
end
end
return "spawned " .. tostring(task.addon) .. ": locations " .. spawned ..
", no-tile " .. skipped .. ", failed " .. failed
end
local function do_despawn(task)
local n = 0
if task.vehicles then
for _, vid in pairs(task.vehicles) do
if server.despawnVehicle(math.floor(vid), true) then n = n + 1 end
end
end
if task.objects then
for _, oid in pairs(task.objects) do
if server.despawnObject(math.floor(oid), true) then n = n + 1 end
end
end
return "despawned " .. tostring(task.addon or "?") .. ": removed " .. n
end
local function run_tasks()
init_savedata()
local ns = {}
for n in pairs(g_savedata.tasks) do ns[#ns + 1] = n end
table.sort(ns)
local ran = 0
for _, n in ipairs(ns) do
local task = g_savedata.tasks[n]
if g_savedata.report[n] == nil then
ran = ran + 1
if task.action == "spawn_env" then
report(n, do_spawn_env(task))
elseif task.action == "despawn" then
report(n, do_despawn(task))
else
report(n, "unknown task: " .. tostring(task.action))
end
end
end
if ran > 0 then
server.announce("[SWAM]", "tasks done: " .. ran .. ". SAVE the game to persist")
end
end
local function prune_tasks()
local ns = {}
for n in pairs(g_savedata.tasks) do
if g_savedata.report[n] ~= nil then ns[#ns + 1] = n end
end
table.sort(ns)
local drop = #ns - KEEP_REPORTS
for i = 1, drop do
g_savedata.tasks[ns[i]] = nil
g_savedata.report[ns[i]] = nil
end
if drop > 0 then
debug.log("[SWAM] pruned " .. drop .. " finished task(s) from the save")
end
end
local function clean_journal()
local removed, forgotten = 0, 0
for name, rec in pairs(g_savedata.journal) do
if rec.o then
for i, id in pairs(rec.o) do
local _, ok = server.getObjectPos(id)
if not ok then
rec.o[i] = nil
removed = removed + 1
end
end
end
if rec.v then
for i, id in pairs(rec.v) do
local _, ok = server.getVehiclePos(id)
if not ok then
rec.v[i] = nil
removed = removed + 1
end
end
end
if count(rec.v) == 0 and count(rec.o) == 0 then
g_savedata.journal[name] = nil
forgotten = forgotten + 1
end
end
if removed > 0 or forgotten > 0 then
debug.log("[SWAM] journal cleanup: dropped " .. removed ..
" dead ids and " .. forgotten .. " empty record(s)")
end
end
function onTick(game_ticks)
if not g_tasks_done then
g_tick = g_tick + 1
if g_tick >= TICK_DELAY then
g_tasks_done = true
run_tasks()
clean_journal()
prune_tasks()
end
end
end
function onCustomCommand(full_message, peer_id, is_admin, is_auth, command, arg1)
if command ~= "?swam" then return end
init_savedata()
if (arg1 == "mark" or arg1 == "unmark") and not is_admin then
server.announce("[SWAM]", "only admins can mark structures for removal", peer_id)
return
end
if arg1 == "mark" then
local m, ok = server.getPlayerPos(peer_id)
if not ok then
server.announce("[SWAM]", "could not read your position", peer_id)
return
end
local marks = ensure(g_savedata, "marks", {})
marks[next_index(marks)] = { x = m[13], y = m[14], z = m[15] }
server.announce("[SWAM]", "marked (" .. math.floor(m[13]) .. ", " ..
math.floor(m[14]) .. ", " .. math.floor(m[15]) .. ") - " ..
count(marks) .. " mark(s) total. SAVE the game, then close it and use " ..
"SWAM remove-marked", peer_id)
return
end
if arg1 == "unmark" then
g_savedata.marks = {}
server.announce("[SWAM]", "marks cleared. SAVE the game", peer_id)
return
end
server.announce("[SWAM]", "journal: " .. count(g_savedata.journal) ..
" addons; tasks: " .. count(g_savedata.report) .. "/" ..
count(g_savedata.tasks) .. "; marks: " .. count(g_savedata.marks), peer_id)
for name, rec in pairs(g_savedata.journal) do
server.announce("[SWAM]", "  " .. name .. ": vehicles " .. count(rec.v) ..
", objects " .. count(rec.o), peer_id)
end
end
