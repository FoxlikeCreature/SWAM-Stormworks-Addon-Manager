-- args: scriptpath, overrides_json_ish (label\1value per line file) 
local scriptpath, ovfile = ...
local overrides = {}
if ovfile then
  local f = io.open(ovfile,"r")
  if f then
    for line in f:lines() do
      local k,v = line:match("^(.-)\1(.*)$")
      if k then overrides[k]=v end
    end
    f:close()
  end
end
local function conv(v, kind, default)
  if kind=="checkbox" then return v=="true"
  elseif kind=="slider" then return tonumber(v) or default
  else return v end
end
property = {
  slider=function(label,mn,mx,step,default)
    if overrides[label] then return conv(overrides[label],"slider",default) end
    return default end,
  checkbox=function(label,default)
    if overrides[label] then return conv(overrides[label],"checkbox",default) end
    if type(default)=="string" then return default=="true" end
    return default and true or false end,
  text=function(label,default)
    if overrides[label] then return overrides[label] end
    return default end,
}
local function stub(name)
  return setmetatable({},{__index=function(t,k)
    local f=function(...) return 0,false end
    rawset(t,k,f); return f end})
end
server=stub("server"); matrix=stub("matrix")
g_savedata={}
debug.sethook(function() error("INSTRLIMIT",2) end,"",2e7)
local chunk,err=loadfile(scriptpath)
if not chunk then io.stderr:write("LOADFAIL "..tostring(err).."\n"); os.exit(2) end
local ok,e=pcall(chunk)
if not ok then io.stderr:write("RUNFAIL "..tostring(e).."\n") end
if type(onCreate)=="function" then
  local ok2,e2=pcall(onCreate,true)
  if not ok2 then io.stderr:write("ONCREATEFAIL "..tostring(e2).."\n") end
end
local out={}
local seen={}
local function walk(t,path)
  if seen[t] then return end
  seen[t]=true
  local keys={}
  for k in pairs(t) do keys[#keys+1]=k end
  table.sort(keys,function(a,b) return tostring(a)<tostring(b) end)
  for _,k in ipairs(keys) do
    local v=t[k]
    local p=path.."."..tostring(k)
    if type(v)=="table" then walk(v,p)
    elseif type(v)~="function" then out[#out+1]=p.."\1"..tostring(v) end
  end
end
if type(g_savedata)=="table" then walk(g_savedata,"") end
print(table.concat(out,"\n"))
