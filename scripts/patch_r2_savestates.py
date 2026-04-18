#!/usr/bin/env python3
"""Patch embedded RetroVault HTML inside worker.js CHUNKS for R2-backed save states."""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path


def extract_chunks_array(src: str) -> tuple[str, list[str], str]:
    """Return (before, chunk_strings, after) for const CHUNKS = [ ... ];"""
    marker = "const CHUNKS = ["
    start = src.find(marker)
    if start < 0:
        raise SystemExit("const CHUNKS = [ not found")

    i = src.find("[", start)
    depth = 0
    in_str = False
    esc = False
    q: str | None = None
    while i < len(src):
        ch = src[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == q:
                in_str = False
                q = None
            i += 1
            continue
        if ch in "\"'":
            in_str = True
            q = ch
            i += 1
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end_bracket = i + 1
                break
        i += 1
    else:
        raise SystemExit("unterminated CHUNKS array")

    semi = src.find(";", end_bracket)
    if semi < 0:
        raise SystemExit("missing ; after CHUNKS")
    end_stmt = semi + 1

    inner = src[start + len(marker) : end_bracket]
    # inner is like "\n  \"...\",\n  \"...\",\n"
    strings: list[str] = []
    pos = 0
    while pos < len(inner):
        m = re.search(r'"', inner[pos:])
        if not m:
            break
        pos += m.start() + 1
        buf: list[str] = []
        while pos < len(inner):
            ch = inner[pos]
            if ch == "\\":
                if pos + 1 < len(inner):
                    buf.append(inner[pos : pos + 2])
                    pos += 2
                else:
                    buf.append(ch)
                    pos += 1
                continue
            if ch == '"':
                pos += 1
                break
            buf.append(ch)
            pos += 1
        strings.append("".join(buf))
        # skip comma whitespace
        while pos < len(inner) and inner[pos] in " \t\n\r,":
            pos += 1

    return src[:start], strings, src[end_stmt:]


def join_chunks(strings: list[str]) -> bytes:
    raw_b64 = "".join(strings)
    return base64.b64decode(raw_b64)


def split_chunks(data: bytes, max_len: int = 8000) -> list[str]:
    b64 = base64.b64encode(data).decode("ascii")
    return [b64[i : i + max_len] for i in range(0, len(b64), max_len)]


def patch_html(html: str) -> str:
    # 1) Settings UI: cloud save toggle + slot
    needle = (
        '<div class="srow"><div><div class="slbl">Save States</div>'
        '<div class="sdsc">Enable save/load state slots</div></div>'
        '<div class="tog on" id="ejsSaveStates" onclick="this.classList.toggle(\'on\');saveEjsSettings()"></div></div>\n'
        '            <div class="srow"><div><div class="slbl">Rewind</div>'
    )
    insert = (
        '<div class="srow"><div><div class="slbl">Save States</div>'
        '<div class="sdsc">Enable save/load state slots</div></div>'
        '<div class="tog on" id="ejsSaveStates" onclick="this.classList.toggle(\'on\');saveEjsSettings()"></div></div>\n'
        '            <div class="srow"><div><div class="slbl">Cloud save states (R2)</div>'
        '<div class="sdsc">Store EmulatorJS save states in your bucket (same owner as ROM sync), not only in this browser</div></div>'
        '<div class="tog on" id="ejsCloudSaveR2" onclick="this.classList.toggle(\'on\');saveEjsSettings()"></div></div>\n'
        '            <div class="srow"><div><div class="slbl">Cloud save slot</div>'
        '<div class="sdsc">Which slot is uploaded to R2 (1–9). Must match in-game save-state slot.</div></div>'
        '<select class="ssel" id="ejsCloudSaveSlot" onchange="saveEjsSettings()">'
        + "".join(f'<option value="{n}">{n}</option>' for n in range(1, 10))
        + "</select></div>\n"
        '            <div class="srow"><div><div class="slbl">Rewind</div>'
    )
    if 'id="ejsCloudSaveR2"' not in html:
        if needle not in html:
            raise SystemExit("needle for settings UI not found")
        html = html.replace(needle, insert, 1)

    # 2) r2SaveMeta early return + payload
    old_meta_guard = (
        "async function r2SaveMeta(rom){\n"
        "  if(!rom || !rom.name) return;\n"
        "  // Only save if we have something worth persisting\n"
        "  if(!rom.coverUrl && !rom.description && !rom.year && !rom.rating) return;\n"
    )
    new_meta_guard = (
        "async function r2SaveMeta(rom){\n"
        "  if(!rom || !rom.name) return;\n"
        "  // Persist metadata and/or cloud save-state pointers\n"
        "  if(!rom.coverUrl && !rom.description && !rom.year && !rom.rating && !rom.videoUrl && !rom.cloudSaveStateKey) return;\n"
    )
    if old_meta_guard in html:
        html = html.replace(old_meta_guard, new_meta_guard, 1)

    old_payload = (
        "      genres: rom.genres||null,\n"
        "    };\n"
    )
    new_payload = (
        "      genres: rom.genres||null,\n"
        "      videoUrl: rom.videoUrl||null,\n"
        "      cloudSaveStateKey: rom.cloudSaveStateKey||null,\n"
        "      cloudSaveStateUrl: rom.cloudSaveStateUrl||null,\n"
        "      cloudSaveStateRev: rom.cloudSaveStateRev||null,\n"
        "      cloudSaveStateUpdatedAt: rom.cloudSaveStateUpdatedAt||null,\n"
        "      cloudSaveStateSlot: (rom.cloudSaveStateSlot!=null?rom.cloudSaveStateSlot:null),\n"
        "    };\n"
    )
    if old_payload in html:
        html = html.replace(old_payload, new_payload, 1)

    # 3) Sync-from-bucket metadata restore
    old_sync = (
        "              if(meta.genres      && !match.genres)      { match.genres      = meta.genres;      changed=true; }\n"
        "              if(changed){ await dbPut('roms', match); metaRestored++; }\n"
    )
    new_sync = (
        "              if(meta.genres      && !match.genres)      { match.genres      = meta.genres;      changed=true; }\n"
        "              if(meta.videoUrl   && !match.videoUrl)   { match.videoUrl   = meta.videoUrl;   changed=true; }\n"
        "              if(meta.cloudSaveStateKey){\n"
        "                const revM = parseInt(match.cloudSaveStateRev,10)||0;\n"
        "                const revMeta = parseInt(meta.cloudSaveStateRev,10)||0;\n"
        "                if(meta.cloudSaveStateKey !== match.cloudSaveStateKey || revMeta > revM){\n"
        "                  match.cloudSaveStateKey = meta.cloudSaveStateKey;\n"
        "                  match.cloudSaveStateRev = meta.cloudSaveStateRev||match.cloudSaveStateRev;\n"
        "                  match.cloudSaveStateUpdatedAt = meta.cloudSaveStateUpdatedAt||match.cloudSaveStateUpdatedAt;\n"
        "                  match.cloudSaveStateSlot = (meta.cloudSaveStateSlot!=null?meta.cloudSaveStateSlot:match.cloudSaveStateSlot);\n"
        "                  if(meta.cloudSaveStateUrl) match.cloudSaveStateUrl = meta.cloudSaveStateUrl;\n"
        "                  changed=true;\n"
        "                }\n"
        "              }\n"
        "              if(changed){ await dbPut('roms', match); metaRestored++; }\n"
    )
    if old_sync in html:
        html = html.replace(old_sync, new_sync, 1)

    # 4) saveEjsSettings / loadEjsSettings
    old_save = (
        "  ejsSettings.saveStates = document.getElementById('ejsSaveStates')?.classList.contains('on');\n"
        "  ejsSettings.rewind     = document.getElementById('ejsRewind')?.classList.contains('on');\n"
    )
    new_save = (
        "  ejsSettings.saveStates = document.getElementById('ejsSaveStates')?.classList.contains('on');\n"
        "  ejsSettings.cloudSaveR2 = document.getElementById('ejsCloudSaveR2')?.classList.contains('on');\n"
        "  try{\n"
        "    const ss=document.getElementById('ejsCloudSaveSlot');\n"
        "    if(ss) ejsSettings.cloudSaveSlot = Math.max(1, Math.min(9, parseInt(ss.value,10)||1));\n"
        "  }catch(e){}\n"
        "  ejsSettings.rewind     = document.getElementById('ejsRewind')?.classList.contains('on');\n"
    )
    if "ejsSettings.cloudLoadPrompt = document" not in html:
        if old_save in html:
            html = html.replace(old_save, new_save, 1)
        elif "ejsSettings.cloudSaveR2 = document" in html:
            html = html.replace(
                "  ejsSettings.cloudSaveR2 = document.getElementById('ejsCloudSaveR2')?.classList.contains('on');\n",
                "  ejsSettings.cloudSaveR2 = document.getElementById('ejsCloudSaveR2')?.classList.contains('on');\n"
                "  ejsSettings.cloudLoadPrompt = document.getElementById('ejsCloudLoadPrompt')?.classList.contains('on');\n"
                "  ejsSettings.cloudLoadAfterSave = document.getElementById('ejsCloudLoadAfterSave')?.classList.contains('on');\n",
                1,
            )

    old_load = (
        "function loadEjsSettings(){\n"
        "  if(ejsSettings.version) document.getElementById('ejsVersion').value=ejsSettings.version;\n"
        "  if(ejsSettings.saveStates===false) document.getElementById('ejsSaveStates')?.classList.remove('on');\n"
    )
    new_load = (
        "function loadEjsSettings(){\n"
        "  if(ejsSettings.version) document.getElementById('ejsVersion').value=ejsSettings.version;\n"
        "  if(ejsSettings.saveStates===false) document.getElementById('ejsSaveStates')?.classList.remove('on');\n"
        "  if(ejsSettings.cloudSaveR2===false) document.getElementById('ejsCloudSaveR2')?.classList.remove('on');\n"
        "  else document.getElementById('ejsCloudSaveR2')?.classList.add('on');\n"
        "  try{\n"
        "    const sl=document.getElementById('ejsCloudSaveSlot');\n"
        "    if(sl){\n"
        "      const n=Math.max(1, Math.min(9, parseInt(ejsSettings.cloudSaveSlot,10)||1));\n"
        "      sl.value=String(n);\n"
        "    }\n"
        "  }catch(e){}\n"
    )
    if "getElementById('ejsCloudLoadPrompt')" not in html:
        if old_load in html:
            html = html.replace(old_load, new_load, 1)
        elif "if(ejsSettings.cloudSaveR2===false)" in html and "ejsCloudLoadPrompt" not in html:
            html = html.replace(
                "  if(ejsSettings.cloudSaveR2===false) document.getElementById('ejsCloudSaveR2')?.classList.remove('on');\n"
                "  else document.getElementById('ejsCloudSaveR2')?.classList.add('on');\n",
                "  if(ejsSettings.cloudSaveR2===false) document.getElementById('ejsCloudSaveR2')?.classList.remove('on');\n"
                "  else document.getElementById('ejsCloudSaveR2')?.classList.add('on');\n"
                "  if(ejsSettings.cloudLoadPrompt===false) document.getElementById('ejsCloudLoadPrompt')?.classList.remove('on');\n"
                "  else document.getElementById('ejsCloudLoadPrompt')?.classList.add('on');\n"
                "  if(ejsSettings.cloudLoadAfterSave) document.getElementById('ejsCloudLoadAfterSave')?.classList.add('on');\n"
                "  else document.getElementById('ejsCloudLoadAfterSave')?.classList.remove('on');\n",
                1,
            )

    # 5) Helpers + patch launchRomById + closeEmu — insert after ejsSettings const (once)
    if "async function _rvFlushCloudSaveState" in html:
        pass  # already patched
    else:
        anchor = "const ejsSettings = JSON.parse(localStorage.getItem('rv-ejs')||'{}');\n\nasync function launchRomById(id){\n"
        if anchor not in html:
            raise SystemExit("launch anchor not found")

        helper = r"""const ejsSettings = JSON.parse(localStorage.getItem('rv-ejs')||'{}');

function _rvCloudSaveToR2On(){
  try{ return ejsSettings.cloudSaveR2 !== false; }catch(e){ return true; }
}
function _rvCloudSaveSlot(){
  try{
    const n = parseInt(ejsSettings.cloudSaveSlot, 10);
    if(Number.isFinite(n)) return Math.max(1, Math.min(9, n));
  }catch(e){}
  return 1;
}
function _rvSafeStem(rom){
  const base = String((rom && (rom.filename||rom.name))||'game').split('/').pop()||'game';
  return base.replace(/[^a-zA-Z0-9._-]/g,'_').slice(0,120)||'game';
}
window.__rvPendingSaveState = null;

async function _rvFlushCloudSaveState(){
  const pending = window.__rvPendingSaveState;
  if(!pending || !pending.romId || !pending.uint8 || !pending.uint8.byteLength) return;
  if(!_rvCloudSaveToR2On()){ window.__rvPendingSaveState=null; return; }
  const owner = (typeof _rvOwnerId==='function'? _rvOwnerId(): '');
  if(!owner){ if(typeof toast==='function') toast('Set Shared Sync Owner ID to upload save states','warn'); return; }
  let rom = await dbGet('roms', pending.romId);
  if(!rom){ window.__rvPendingSaveState=null; return; }
  const slot = pending.slot || _rvCloudSaveSlot();
  const stem = _rvSafeStem(rom);
  const key = 'saves/'+(rom.console||'unknown')+'/'+stem+'-slot'+slot+'.state';
  const rev = Date.now();
  try{
    const fd = new FormData();
    fd.append('file', new Blob([pending.uint8], {type:'application/octet-stream'}), stem+'-slot'+slot+'.state');
    fd.append('key', key);
    fd.append('owner', owner);
    const resp = await fetch(window.location.origin+'/r2-upload', { method:'POST', body: fd });
    const data = await resp.json().catch(function(){ return {}; });
    if(!resp.ok || !data.ok) throw new Error((data && data.error) ? data.error : ('HTTP '+resp.status));
    rom.cloudSaveStateKey = data.key || key;
    rom.cloudSaveStateRev = rev;
    rom.cloudSaveStateUpdatedAt = rev;
    rom.cloudSaveStateSlot = slot;
    rom.cloudSaveStateUrl = window.location.origin + '/r2-rom?key=' + encodeURIComponent(rom.cloudSaveStateKey) + '&owner=' + encodeURIComponent(owner) + '&v=' + encodeURIComponent(String(rev));
    await dbPut('roms', rom);
    await r2SaveMeta(rom);
    if(typeof logScrape==='function') logScrape('[r2-savestate] uploaded '+rom.cloudSaveStateKey);
    if(typeof toast==='function') toast('Cloud save state uploaded');
  }catch(e){
    if(typeof toast==='function') toast('Cloud save upload failed: '+(e && e.message ? e.message : e), 'err');
    if(typeof logScrape==='function') logScrape('[r2-savestate] '+String(e && e.message ? e.message : e));
  }
  window.__rvPendingSaveState = null;
}

async function launchRomById(id){
"""

        html = html.replace(anchor, helper, 1)

        # Inject EJS hooks after EJS_gameName assignment
        inj = (
            "  window.EJS_gameName    = rom.name;\n"
            "  window.EJS_pathtodata  = `https://cdn.emulatorjs.org/${ver}/data/`;\n"
        )
        repl = (
            "  window.EJS_gameName    = rom.name;\n"
            "  let __rvLoadStateUrl = '';\n"
            "  if(_rvCloudSaveToR2On() && rom.cloudSaveStateUrl){\n"
            "    try{ __rvLoadStateUrl = String(rom.cloudSaveStateUrl); }catch(e){ __rvLoadStateUrl = ''; }\n"
            "  }\n"
            "  window.EJS_loadStateURL = __rvLoadStateUrl;\n"
            "  window.EJS_defaultOptions = window.EJS_defaultOptions && typeof window.EJS_defaultOptions==='object' ? Object.assign({}, window.EJS_defaultOptions) : {};\n"
            "  window.EJS_defaultOptions['save-state-location'] = 'browser';\n"
            "  window.EJS_defaultOptions['save-state-slot'] = String(_rvCloudSaveSlot());\n"
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
            "  window.EJS_onLoadState = async function(){\n"
            "    try{\n"
            "      if(!_rvCloudSaveToR2On() || !ejsSettings.saveStates) return 0;\n"
            "      const r = await dbGet('roms', lastRomId);\n"
            "      if(!r || !r.cloudSaveStateUrl) return 0;\n"
            "      const resp = await fetch(r.cloudSaveStateUrl);\n"
            "      if(!resp.ok) return 0;\n"
            "      const buf = new Uint8Array(await resp.arrayBuffer());\n"
            "      if(window.EJS_emulator && window.EJS_emulator.gameManager && typeof window.EJS_emulator.gameManager.loadState==='function'){\n"
            "        window.EJS_emulator.gameManager.loadState(buf);\n"
            "        if(typeof toast==='function') toast('Loaded cloud save state');\n"
            "        return 1;\n"
            "      }\n"
            "    }catch(e){}\n"
            "    return 0;\n"
            "  };\n"
            "  window.EJS_pathtodata  = `https://cdn.emulatorjs.org/${ver}/data/`;\n"
        )
        if inj not in html:
            raise SystemExit("EJS_gameName injection point not found")
        html = html.replace(inj, repl, 1)

        # closeEmu: await flush before terminate
        old_close = (
            "  // 2. Terminate the EJS emulator instance — stops the game loop\n"
            "  if(window.EJS_emulator){\n"
            "    try{ window.EJS_emulator.terminate(); }catch(e){}\n"
            "    try{ window.EJS_emulator.callMain && window.EJS_emulator.callMain([]); }catch(e){}\n"
            "    window.EJS_emulator = null;\n"
            "  }\n"
        )
        new_close = (
            "  // 2. Upload pending cloud save state before tearing the core down\n"
            "  try{ await _rvFlushCloudSaveState(); }catch(e){}\n"
            "  // 3. Terminate the EJS emulator instance — stops the game loop\n"
            "  if(window.EJS_emulator){\n"
            "    try{ window.EJS_emulator.terminate(); }catch(e){}\n"
            "    try{ window.EJS_emulator.callMain && window.EJS_emulator.callMain([]); }catch(e){}\n"
            "    window.EJS_emulator = null;\n"
            "  }\n"
        )
        if old_close in html:
            html = html.replace(old_close, new_close, 1)

            # Renumber closeEmu comments after inserting flush step
            html = html.replace(
                "  // 3. Stop and close any AudioContext EJS created",
                "  // 4. Stop and close any AudioContext EJS created",
                1,
            )
            html = html.replace(
                "  // 4. Terminate any lingering Web Workers EJS may have spawned",
                "  // 5. Terminate any lingering Web Workers EJS may have spawned",
                1,
            )
            html = html.replace(
                "  // 5. Remove the loader script",
                "  // 6. Remove the loader script",
                1,
            )
            html = html.replace(
                "  // 6. Destroy the canvas/WebGL context",
                "  // 7. Destroy the canvas/WebGL context",
                1,
            )
            html = html.replace(
                "  // 7. Wipe the container DOM",
                "  // 8. Wipe the container DOM",
                1,
            )
            html = html.replace(
                "  // 8. Revoke the blob URL",
                "  // 9. Revoke the blob URL",
                1,
            )
            html = html.replace(
                "  // 9. Null out ALL EJS window globals",
                "  // 10. Null out ALL EJS window globals",
                1,
            )
            html = html.replace(
                "  // 10. Exit fullscreen if the emulator had gone fullscreen",
                "  // 11. Exit fullscreen if the emulator had gone fullscreen",
                1,
            )

        if "'EJS_loadStateURL'" not in html:
            html = html.replace(
                "    'EJS_fullscreenOnLoaded','EJS_threads','EJS_biosUrl','EJS_disableKeyboard',\n"
                "    'Module','EJS_Buttons','EJS_defaultOptions',\n",
                "    'EJS_fullscreenOnLoaded','EJS_threads','EJS_biosUrl','EJS_disableKeyboard',\n"
                "    'EJS_loadStateURL','EJS_onSaveState','EJS_onLoadState',\n"
                "    'Module','EJS_Buttons','EJS_defaultOptions',\n",
                1,
            )

        # Make closeEmu async
        html = html.replace("function closeEmu(){", "async function closeEmu(){", 1)

    # Launch prompt + optional reload-after-save (idempotent; see patch_savestate_prompt.py)
    _scripts_dir = Path(__file__).resolve().parent
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))
    import patch_savestate_prompt as _rv_ss_ux

    html = _rv_ss_ux.patch_savestate_ux(html)

    return html


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    worker = root / "worker.js"
    src = worker.read_text(encoding="utf-8")
    before, chunks, after = extract_chunks_array(src)
    html_bytes = join_chunks(chunks)
    html = html_bytes.decode("utf-8")
    new_html = patch_html(html)
    new_chunks = split_chunks(new_html.encode("utf-8"), max_len=8000)
    rebuilt = (
        before
        + "const CHUNKS = [\n"
        + "".join(f'  "{s}",\n' for s in new_chunks)
        + "];\n"
        + after
    )
    worker.write_text(rebuilt, encoding="utf-8")
    print("OK: patched worker.js CHUNKS", len(chunks), "->", len(new_chunks))


if __name__ == "__main__":
    main()
