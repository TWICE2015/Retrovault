#!/usr/bin/env python3
"""
Cloud save UX: launch prompt (load vs fresh), optional auto-load after save,
and idempotent CHUNK rebuild for worker.js.

Import patch_savestate_ux(html) from patch_r2_savestates.py after edits.
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from patch_r2_savestates import extract_chunks_array, split_chunks  # noqa: E402


def patch_savestate_ux(html: str) -> str:
    """Apply cloud save load prompt + after-save reload (idempotent)."""

    needle_slot = (
        "</select></div>\n"
        '            <div class="srow"><div><div class="slbl">Rewind</div>'
    )
    insert_rows = (
        "</select></div>\n"
        '            <div class="srow"><div><div class="slbl">Ask before loading cloud save</div>'
        '<div class="sdsc">When a cloud save exists, show Load or Start fresh before the core runs</div></div>'
        '<div class="tog on" id="ejsCloudLoadPrompt" onclick="this.classList.toggle(\'on\');saveEjsSettings()"></div></div>\n'
        '            <div class="srow"><div><div class="slbl">After save: auto-load from cloud</div>'
        '<div class="sdsc">When cloud saves are on, upload after each save then reload that state (extra bandwidth)</div></div>'
        '<div class="tog" id="ejsCloudLoadAfterSave" onclick="this.classList.toggle(\'on\');saveEjsSettings()"></div></div>\n'
        '            <div class="srow"><div><div class="slbl">Rewind</div>'
    )

    if 'id="ejsCloudLoadPrompt"' not in html:
        if needle_slot not in html:
            raise ValueError("needle_slot not found for cloud load UX rows")
        html = html.replace(needle_slot, insert_rows, 1)

    old_save = (
        "  ejsSettings.cloudSaveR2 = document.getElementById('ejsCloudSaveR2')?.classList.contains('on');\n"
        "  try{\n"
        "    const ss=document.getElementById('ejsCloudSaveSlot');\n"
        "    if(ss) ejsSettings.cloudSaveSlot = Math.max(1, Math.min(9, parseInt(ss.value,10)||1));\n"
        "  }catch(e){}\n"
    )
    new_save = (
        "  ejsSettings.cloudSaveR2 = document.getElementById('ejsCloudSaveR2')?.classList.contains('on');\n"
        "  ejsSettings.cloudLoadPrompt = document.getElementById('ejsCloudLoadPrompt')?.classList.contains('on');\n"
        "  ejsSettings.cloudLoadAfterSave = document.getElementById('ejsCloudLoadAfterSave')?.classList.contains('on');\n"
        "  try{\n"
        "    const ss=document.getElementById('ejsCloudSaveSlot');\n"
        "    if(ss) ejsSettings.cloudSaveSlot = Math.max(1, Math.min(9, parseInt(ss.value,10)||1));\n"
        "  }catch(e){}\n"
    )
    if old_save in html:
        html = html.replace(old_save, new_save, 1)

    old_load = (
        "  if(ejsSettings.cloudSaveR2===false) document.getElementById('ejsCloudSaveR2')?.classList.remove('on');\n"
        "  else document.getElementById('ejsCloudSaveR2')?.classList.add('on');\n"
    )
    new_load = (
        "  if(ejsSettings.cloudSaveR2===false) document.getElementById('ejsCloudSaveR2')?.classList.remove('on');\n"
        "  else document.getElementById('ejsCloudSaveR2')?.classList.add('on');\n"
        "  if(ejsSettings.cloudLoadPrompt===false) document.getElementById('ejsCloudLoadPrompt')?.classList.remove('on');\n"
        "  else document.getElementById('ejsCloudLoadPrompt')?.classList.add('on');\n"
        "  if(ejsSettings.cloudLoadAfterSave) document.getElementById('ejsCloudLoadAfterSave')?.classList.add('on');\n"
        "  else document.getElementById('ejsCloudLoadAfterSave')?.classList.remove('on');\n"
    )
    if old_load in html:
        html = html.replace(old_load, new_load, 1)

    anchor = (
        "function _rvCloudSaveSlot(){\n"
        "  try{\n"
        "    const n = parseInt(ejsSettings.cloudSaveSlot, 10);\n"
        "    if(Number.isFinite(n)) return Math.max(1, Math.min(9, n));\n"
        "  }catch(e){}\n"
        "  return 1;\n"
        "}\n"
        "function _rvSafeStem(rom){\n"
    )
    insert_helpers = (
        "function _rvCloudSaveSlot(){\n"
        "  try{\n"
        "    const n = parseInt(ejsSettings.cloudSaveSlot, 10);\n"
        "    if(Number.isFinite(n)) return Math.max(1, Math.min(9, n));\n"
        "  }catch(e){}\n"
        "  return 1;\n"
        "}\n"
        "function _rvCloudLoadPromptOn(){\n"
        "  try{ return ejsSettings.cloudLoadPrompt !== false; }catch(e){ return true; }\n"
        "}\n"
        "function _rvCloudLoadAfterSaveOn(){\n"
        "  try{ return !!ejsSettings.cloudLoadAfterSave; }catch(e){ return false; }\n"
        "}\n"
        "window.__rvSaveUploadBusy = false;\n"
        "async function _rvUploadCloudSaveStateNow(romId, uint8, slot){\n"
        "  const owner = (typeof _rvOwnerId==='function'? _rvOwnerId(): '');\n"
        "  if(!owner){ if(typeof toast==='function') toast('Set Shared Sync Owner ID to upload save states','warn'); return false; }\n"
        "  let rom = await dbGet('roms', romId);\n"
        "  if(!rom || !uint8 || !uint8.byteLength) return false;\n"
        "  const stem = _rvSafeStem(rom);\n"
        "  const key = 'saves/'+(rom.console||'unknown')+'/'+stem+'-slot'+slot+'.state';\n"
        "  const rev = Date.now();\n"
        "  const fd = new FormData();\n"
        "  fd.append('file', new Blob([uint8], {type:'application/octet-stream'}), stem+'-slot'+slot+'.state');\n"
        "  fd.append('key', key);\n"
        "  fd.append('owner', owner);\n"
        "  const resp = await fetch(window.location.origin+'/r2-upload', { method:'POST', body: fd });\n"
        "  const data = await resp.json().catch(function(){ return {}; });\n"
        "  if(!resp.ok || !data.ok) throw new Error((data && data.error) ? data.error : ('HTTP '+resp.status));\n"
        "  rom.cloudSaveStateKey = data.key || key;\n"
        "  rom.cloudSaveStateRev = rev;\n"
        "  rom.cloudSaveStateUpdatedAt = rev;\n"
        "  rom.cloudSaveStateSlot = slot;\n"
        "  rom.cloudSaveStateUrl = window.location.origin + '/r2-rom?key=' + encodeURIComponent(rom.cloudSaveStateKey) + '&owner=' + encodeURIComponent(owner) + '&v=' + encodeURIComponent(String(rev));\n"
        "  await dbPut('roms', rom);\n"
        "  await r2SaveMeta(rom);\n"
        "  if(typeof logScrape==='function') logScrape('[r2-savestate] immediate upload '+rom.cloudSaveStateKey);\n"
        "  return true;\n"
        "}\n"
        "function _rvHideCloudLoadModal(){\n"
        "  const m=document.getElementById('rvCloudLoadModal');\n"
        "  if(m) m.remove();\n"
        "}\n"
        "function _rvPromptCloudLoad(rom){\n"
        "  return new Promise(function(resolve){\n"
        "    _rvHideCloudLoadModal();\n"
        "    const wrap=document.createElement('div');\n"
        "    wrap.id='rvCloudLoadModal';\n"
        "    wrap.style.cssText='position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;padding:20px;';\n"
        "    const card=document.createElement('div');\n"
        "    card.style.cssText='max-width:420px;width:100%;background:var(--s1, #1e1e1e);color:var(--text,#eee);border:1px solid var(--line,#444);border-radius:12px;padding:20px;font-family:sans-serif;box-shadow:0 8px 32px rgba(0,0,0,.5);';\n"
        "    const t=document.createElement('div');\n"
        "    t.style.fontWeight='700'; t.style.marginBottom='8px'; t.textContent='Load cloud save state?';\n"
        "    const p=document.createElement('div');\n"
        "    p.style.fontSize='13px'; p.style.color='var(--muted,#aaa)'; p.style.lineHeight='1.5'; p.style.marginBottom='14px';\n"
        "    p.textContent='A save state was found in your cloud backup for this game. Load it now, or start fresh from the ROM.';\n"
        "    const row=document.createElement('div');\n"
        "    row.style.display='flex'; row.style.gap='10px'; row.style.flexWrap='wrap'; row.style.marginBottom='12px';\n"
        "    const btnLoad=document.createElement('button'); btnLoad.className='bb p'; btnLoad.type='button'; btnLoad.textContent='Load cloud save';\n"
        "    const btnSkip=document.createElement('button'); btnSkip.className='bb s'; btnSkip.type='button'; btnSkip.textContent='Start fresh';\n"
        "    const chkRow=document.createElement('label'); chkRow.style.display='flex'; chkRow.style.alignItems='center'; chkRow.style.gap='8px'; chkRow.style.fontSize='12px'; chkRow.style.color='var(--muted,#aaa);';\n"
        "    const chk=document.createElement('input'); chk.type='checkbox'; chk.id='rvCloudLoadDontAsk';\n"
        "    chkRow.appendChild(chk); chkRow.appendChild(document.createTextNode(' Do not ask again (auto-load cloud save when available)'));\n"
        "    const cleanup=function(v){ _rvHideCloudLoadModal(); resolve(v); };\n"
        "    btnLoad.onclick=function(){ try{ if(chk.checked){ ejsSettings.cloudLoadPrompt=false; localStorage.setItem('rv-ejs', JSON.stringify(ejsSettings)); } }catch(e){} cleanup(true); };\n"
        "    btnSkip.onclick=function(){ cleanup(false); };\n"
        "    row.appendChild(btnLoad); row.appendChild(btnSkip);\n"
        "    card.appendChild(t); card.appendChild(p); card.appendChild(row); card.appendChild(chkRow);\n"
        "    wrap.appendChild(card);\n"
        "    wrap.addEventListener('click', function(ev){ if(ev.target===wrap) cleanup(false); });\n"
        "    document.body.appendChild(wrap);\n"
        "    try{ btnLoad.focus(); }catch(e){}\n"
        "  });\n"
        "}\n"
        "async function _rvResolveLoadStateUrlForLaunch(rom){\n"
        "  let u='';\n"
        "  if(_rvCloudSaveToR2On() && rom && rom.cloudSaveStateUrl){\n"
        "    try{ u = String(rom.cloudSaveStateUrl); }catch(e){ u=''; }\n"
        "  }\n"
        "  if(!u) return '';\n"
        "  if(!_rvCloudLoadPromptOn()) return u;\n"
        "  const load = await _rvPromptCloudLoad(rom);\n"
        "  return load ? u : '';\n"
        "}\n"
        "function _rvSafeStem(rom){\n"
    )
    if "function _rvResolveLoadStateUrlForLaunch" not in html:
        if anchor not in html:
            raise ValueError("anchor for helper insert not found")
        html = html.replace(anchor, insert_helpers, 1)

    old_flush_head = (
        "async function _rvFlushCloudSaveState(){\n"
        "  const pending = window.__rvPendingSaveState;\n"
        "  if(!pending || !pending.romId || !pending.uint8 || !pending.uint8.byteLength) return;\n"
    )
    new_flush_head = (
        "async function _rvFlushCloudSaveState(){\n"
        "  const pending = window.__rvPendingSaveState;\n"
        "  if(!pending || !pending.romId || !pending.uint8 || !pending.uint8.byteLength) return;\n"
        "  if(_rvCloudLoadAfterSaveOn()){ window.__rvPendingSaveState=null; return; }\n"
    )
    if "if(_rvCloudLoadAfterSaveOn())" not in html and old_flush_head in html:
        html = html.replace(old_flush_head, new_flush_head, 1)

    old_inj = (
        "  let __rvLoadStateUrl = '';\n"
        "  if(_rvCloudSaveToR2On() && rom.cloudSaveStateUrl){\n"
        "    try{ __rvLoadStateUrl = String(rom.cloudSaveStateUrl); }catch(e){ __rvLoadStateUrl = ''; }\n"
        "  }\n"
        "  window.EJS_loadStateURL = __rvLoadStateUrl;\n"
    )
    new_inj = (
        "  const __rvLoadStateUrl = await _rvResolveLoadStateUrlForLaunch(rom);\n"
        "  window.EJS_loadStateURL = __rvLoadStateUrl;\n"
    )
    if old_inj in html:
        html = html.replace(old_inj, new_inj, 1)

    old_on_save = (
        "  window.EJS_onSaveState = function(data){\n"
        "    try{\n"
        "      if(!_rvCloudSaveToR2On() || !ejsSettings.saveStates) return 0;\n"
        "      const st = data && data.state;\n"
        "      if(!st || !lastRomId) return 0;\n"
        "      const u8 = (st instanceof Uint8Array) ? st : new Uint8Array(st);\n"
        "      window.__rvPendingSaveState = { romId:lastRomId, uint8:u8.slice(), slot:_rvCloudSaveSlot(), ts:Date.now() };\n"
        "      if(typeof toast==='function') toast('Save state will upload to cloud on exit');\n"
        "      return 1;\n"
        "    }catch(e){ return 0; }\n"
        "  };\n"
    )
    new_on_save = (
        "  window.EJS_onSaveState = function(data){\n"
        "    try{\n"
        "      if(!_rvCloudSaveToR2On() || !ejsSettings.saveStates) return 0;\n"
        "      const st = data && data.state;\n"
        "      if(!st || !lastRomId) return 0;\n"
        "      const u8 = (st instanceof Uint8Array) ? st : new Uint8Array(st);\n"
        "      const slot = _rvCloudSaveSlot();\n"
        "      const buf = u8.slice();\n"
        "      if(_rvCloudLoadAfterSaveOn()){\n"
        "        if(window.__rvSaveUploadBusy) return 1;\n"
        "        window.__rvSaveUploadBusy = true;\n"
        "        window.__rvPendingSaveState = null;\n"
        "        (async function(){\n"
        "          try{\n"
        "            await _rvUploadCloudSaveStateNow(lastRomId, buf, slot);\n"
        "            if(window.EJS_emulator && window.EJS_emulator.gameManager && typeof window.EJS_emulator.gameManager.loadState==='function'){\n"
        "              window.EJS_emulator.gameManager.loadState(buf);\n"
        "              if(typeof toast==='function') toast('Saved to cloud and reloaded');\n"
        "            }\n"
        "          }catch(e){\n"
        "            window.__rvPendingSaveState = { romId:lastRomId, uint8:buf, slot: slot, ts:Date.now() };\n"
        "            if(typeof toast==='function') toast('Cloud upload failed — will retry on exit', 'warn');\n"
        "          }\n"
        "          window.__rvSaveUploadBusy = false;\n"
        "        })();\n"
        "        return 1;\n"
        "      }\n"
        "      window.__rvPendingSaveState = { romId:lastRomId, uint8:buf, slot:slot, ts:Date.now() };\n"
        "      if(typeof toast==='function') toast('Save state will upload to cloud on exit');\n"
        "      return 1;\n"
        "    }catch(e){ return 0; }\n"
        "  };\n"
    )
    if old_on_save in html:
        html = html.replace(old_on_save, new_on_save, 1)

    return html


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    worker_path = root / "worker.js"
    src = worker_path.read_text(encoding="utf-8")

    before, chunks, after = extract_chunks_array(src)
    html = base64.b64decode("".join(chunks)).decode("utf-8")
    html = patch_savestate_ux(html)
    new_chunks = split_chunks(html.encode("utf-8"), max_len=8000)

    rebuilt = (
        before
        + "const CHUNKS = [\n"
        + "".join(f'  "{s}",\n' for s in new_chunks)
        + "];\n"
        + after
    )
    worker_path.write_text(rebuilt, encoding="utf-8")
    print("OK: patched CHUNKS, chunk count", len(new_chunks))


if __name__ == "__main__":
    main()
