# RetroVault — Bug Fixes & Technical Notes

## Emulator Bugs Fixed (v2.0)

### Fix 1 — Wrong EJS System IDs
**Problem:** The previous version used core names (e.g. `genesis_plus_gx`, `pcsx_rearmed`)
as the `EJS_core` value instead of EmulatorJS's system identifiers.

**What EmulatorJS actually expects:**
| Console        | Correct EJS_core value |
|----------------|------------------------|
| NES            | `nes`                  |
| SNES           | `snes`                 |
| Nintendo 64    | `n64`                  |
| Game Boy       | `gb`                   |
| Game Boy Color | `gbc`                  |
| GBA            | `gba`                  |
| Sega Genesis   | `segaMD`               |
| Sega Saturn    | `segaSaturn`           |
| Dreamcast      | `segaDC`               |
| PlayStation 1  | `psx`                  |
| Atari 2600     | `atari2600`            |
| Atari 7800     | `atari7800`            |
| Arcade/MAME    | `arcade`               |

These are NOT the same as the libretro core names (e.g. `genesis_plus_gx` is the
underlying core, but EJS expects `segaMD` as the system identifier).

---

### Fix 2 — loader.js not properly removed between game launches
**Problem:** Each launch appended a new `<script src="loader.js">` tag to the page.
On the 2nd+ launch, multiple EJS instances were fighting over the same DOM.

**Fix:** Remove the old loader script tag AND terminate the old EJS instance BEFORE
injecting a new one. Also, call `EJS_emulator.terminate()` on the previous instance.

---

### Fix 3 — Player div not recreated
**Problem:** EJS requires a fresh DOM node as its player. Reusing the same div caused
the second game launch to fail silently.

**Fix:** `container.innerHTML = ''` then create a new `<div id="ejs-player">` every time.

---

### Fix 4 — ROM data stored as ArrayBuffer, not Uint8Array
**Problem:** When reading with `FileReader.readAsArrayBuffer()`, the result is an
`ArrayBuffer` object. When stored in IndexedDB and retrieved, some browsers lose the
type information, causing `new Blob([bytes])` to create a corrupted blob.

**Fix:** Immediately wrap as `new Uint8Array(e.target.result)` before storing.
On retrieval, check `instanceof Uint8Array` and re-wrap if needed:
```js
const bytes = rom.data instanceof Uint8Array ? rom.data : new Uint8Array(rom.data);
const blob = new Blob([bytes]);
const romUrl = URL.createObjectURL(blob);
```

---

### Fix 5 — Blob URL created after EJS_gameUrl was set
**Problem:** The previous code set `window.EJS_gameUrl = romUrl` before the blob was
actually created, so EJS received an empty string.

**Fix:** Create the blob URL first, then assign all EJS window variables, then inject
the loader script.

---

### Fix 6 — Missing EJS_gameName
**Problem:** Without `EJS_gameName`, save states were saved as `game.state` instead of
the actual game name, causing them to overwrite each other.

**Fix:** Always set `window.EJS_gameName = rom.name` before loading.

---

## Cross-Device Sync (Supabase)

### Why ROMs don't sync
IndexedDB is browser-local. There's no built-in way to sync between devices.

### Solution: Supabase (free)
- Metadata (name, console, cover URL, filename) syncs via Supabase Postgres
- The actual ROM binary stays in local IndexedDB on each device
- You re-upload the ROM binary on each new device (or link a cloud URL)

### Setup (5 minutes):
1. Create free project at supabase.com
2. Run in SQL Editor:
   ```sql
   CREATE TABLE IF NOT EXISTS roms (
     id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
     name text,
     console text,
     console_name text,
     filename text,
     size bigint,
     cover_url text,
     added_at bigint,
     ejs_system text,
     ejs_core text
   );
   ALTER TABLE roms ENABLE ROW LEVEL SECURITY;
   CREATE POLICY "allow_all" ON roms FOR ALL USING (true);
   ```
3. Go to Settings → API → copy URL and anon key
4. Paste into RetroVault → ROMs → Cloud Sync

---

## ScreenScraper Artwork

### How auto-fetch works
On upload, if SS credentials are saved, RetroVault immediately calls:
```
https://api.screenscraper.fr/api2/jeuInfos.php?
  devid=retrovault&ssid=USER&sspassword=PASS&
  romnom=FILENAME&systemeid=SYSTEM_ID&output=json
```

The response contains a `medias` array. The first `box-2D` image URL is saved as
`coverUrl` in the ROM's IndexedDB record.

### CORS Issue
The ScreenScraper API does not send CORS headers, so direct browser fetch() calls
will fail with a CORS error in production. Solutions:

1. **Enable CORS Proxy** in Scraper → Sources → toggle "CORS Proxy"
   (uses corsproxy.io as a middleman)

2. **Use the Node.js desktop version** (RetroVault.bat) — the server-side fetch
   bypasses CORS entirely

3. **Deploy a Cloudflare Worker** as your own proxy (see DEPLOY.md)

---

## Required Cloudflare Headers (for SharedArrayBuffer)

EmulatorJS needs `SharedArrayBuffer` for threaded cores (N64, PSX, etc.).
This requires two HTTP headers:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

The `_headers` file in this package automatically sets these on Cloudflare Pages.
For other hosts, configure these headers in your server/CDN settings.

---

## Known Limitations

| System     | Status  | Notes |
|------------|---------|-------|
| NES        | ✅ Works | fceumm core |
| SNES       | ✅ Works | snes9x core |
| Game Boy   | ✅ Works | gambatte core |
| GBA        | ✅ Works | mgba core |
| Genesis    | ✅ Works | genesis_plus_gx via segaMD |
| N64        | ⚠ Needs COEP headers | mupen64plus_next |
| PSX        | ⚠ Needs BIOS | Upload scph1001.bin, set EJS_biosUrl |
| Saturn     | ⚠ Experimental | yabause core |
| PSP        | ⚠ Large ROMs | ppsspp, use zipped ISOs |
| Switch     | ❌ Not supported | No browser core exists |
| PS4/PS5    | ❌ Not supported | No browser core exists |
| Xbox       | ❌ Not supported | No browser core exists |

---

RetroVault v2.0 — All bugs documented and fixed.
