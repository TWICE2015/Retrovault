# RetroVault Cloud Frontend Changelog

This file tracks cloud-agent changes applied to the live Worker/frontend integration.

## 2026-04-13

### Core cloud + ownership
- Enforced owner-scoped ROM sync and metadata paths (`users/{owner}/...`) to isolate user libraries.
- Added shared owner ID controls in UI for cross-device sync consistency.
- Added owner-aware ROM streaming route (`/r2-rom`) and launch URL normalization.
- Added legacy migration route/UI (`/r2-migrate-owner`) with preview + migrate actions.

### Sessions
- Added private online session routes:
  - `/session-create`
  - `/session-join`
  - `/session-get`
  - `/session-leave`
- Added settings-side session controls (password save, create/join actions, status display).

### Sync + metadata reliability
- Fixed nested key parser for owner-prefixed paths during bucket sync.
- Fixed sync refresh behavior so Home updates when existing ROM entries are corrected.
- Ensured metadata sidecars are saved after upload (`r2SaveMeta(saved)`).
- Added cloud key normalization during update matching.

### Scraper overhaul
- Introduced all-provider scraper controls in Scraper settings.
- Added provider toggles and per-provider credential fields.
- Added no-login-first flow with configurable providers:
  - Libretro
  - Wikidata/Wikipedia
  - LaunchBox
  - TheGamesDB
  - MobyGames
  - IGDB
  - GiantBomb
  - OpenVGDB
  - ScreenScraper fallback
- LaunchBox default is OFF.
- Added strict provider-off behavior (all-off skips scraping).

### Cover rendering + recovery
- Fixed card image fallback behavior when cover image fails.
- Added bad-cover URL memory list (`rv-bad-cover-urls`).
- Added auto-recovery flow: bad cover -> clear cover -> retry scrape across enabled providers.

### Noise reduction
- Fixed malformed LaunchBox cleanup regex in the index fast-path override.
- Updated `/lb-search` missing-index response to return a non-fatal empty match payload.

### Product direction prep
- Added landing page function scaffold and release log constants.
- Added release-notes and GitHub integration status API endpoints.
- Added route split prep (`/` landing target, `/app` app target) while preserving existing app route behavior.

## 2026-04-14

### Metadata: Hasheous only
- Removed worker routes that proxied arbitrary scraper URLs and the LaunchBox index search (`/scraper-proxy`, `/lb-search`, and related test routes).
- Added `POST /hasheous-lookup`, which forwards hash payloads to `https://hasheous.org/api/v1/Lookup/ByHash` with CORS-friendly responses for the browser.
- Frontend scrape actions route through client-side ROM hashing and the Hasheous lookup only.

### BIOS serving
- Restored `GET` and `HEAD` for `/bios/:filename` so firmware in the `bios/` R2 prefix streams with COOP/COEP/CORP headers expected by the emulator shell.

### Manual box art (GIF) + sync
- Drag-and-drop and file picker accept GIF/WebP as well as PNG/JPEG; extension is inferred from MIME when the file has no name.
- After **Sync from bucket**, metadata sidecars apply R2-hosted cover URLs (your uploaded art) even when the local row still has a remote scraper URL, so GIF box art follows the same path as ROM sync.
- Existing ROM rows get `cloudStoragePath` updated to the normalized R2 key when the bucket listing returns it, improving sidecar matching across devices.

### Hotfix: client SyntaxError on `/app`
- Fixed invalid injected regex in `normalizeCloudKey` (was `/^\+/` after HTML embedding) which broke the whole script with “Invalid regular expression: missing /” and follow-on “Unexpected token 'try'”.

### Cover upload UX
- **Upload** button on the game detail panel (next to **Set**) opens the image picker (PNG, JPEG, WebP, GIF).
- Drag-and-drop targets the **left box art**; listeners are delegated so it keeps working after the cover image is injected.

### Cover drop reliability
- Drop target is the **whole game info panel** (not only the small cover tile).
- Handles **empty MIME types** (extension-based), **DataTransferItem** file entries, **data:image/...** and **http(s) image URLs** when the OS does not expose a File (browser-tab drags may still be blocked by CORS).
- **Paste** an image while the game panel is open to set cover.

### R2 public URL (`*.r2.dev`) box art + COEP
- Pasting a public **R2.dev** image URL and tapping **Set** now stores **`/img-proxy?url=...`** so the cover displays under **Cross-Origin-Embedder-Policy** (raw `r2.dev` responses often omit `Cross-Origin-Resource-Policy` and were blocked).
- **One-time migration** rewrites existing IndexedDB `coverUrl` rows that still point at raw `*.r2.dev` (or `r2.cloudflarestorage.com`) so old libraries fix themselves on load.

### Home row scroll arrows
- Arrow buttons are **`type="button"`** with **`preventDefault` / `stopPropagation`** so they don’t act like submit buttons or bubble to parent handlers (avoids navigation / “goes back” when scrolling rows).

### JS: async `setArtUrl` / `setRomUrl`
- The embedded app used **`await` inside non-`async` functions**, which breaks parsing (`Unexpected token 'try'`) and stops Hasheous / network code from running. A final **`_rvEnsureAsyncDetailSavers`** pass in `getHTML()` forces the correct `async function` declarations.
- **Hotfix:** replacing `function setArtUrl(){…}` could also match **inside** `async function setArtUrl(){…}` and yield **`async async function`**. The saver now strips duplicate `async` tokens after replacement.

### Box art: fit (contain) + larger tiles
- ROM grid and detail cover images use **`object-fit: contain`** with a dark background so full artwork is visible (less zoom/crop than `cover`).
- Home row cards are slightly **wider/taller** for a sharper on-screen bitmap.

### Manual cover R2 layout
- Uploaded box art is stored under **`meta/<console>/art/`** (e.g. `users/{owner}/meta/nes/art/MyGame-cover.png`) so it lives in the **metadata** area with JSON sidecars, not next to ROM binaries under `nes/`.

### ROM stream 404 mitigation
- **`GET /r2-rom`** may retry **similar object keys** (e.g. `__` vs `_`) when the exact key is missing — reduces “Network Error” when the app’s sanitized name differs slightly from the uploaded object name.
- **`GET /rom-proxy`** adds **`Cross-Origin-Resource-Policy: cross-origin`** for COEP-safe cross-origin ROM fetches.

### Cover URL ↔ R2 key fix
- Manual cover uploads now store **`/r2-rom?key=`** as the **console-relative** path (e.g. `gb/art/foo-cover.png`), matching how the worker scopes keys under `users/{owner}/`.
- **`/r2-rom`** also accepts legacy URLs that still embed the full `users/{owner}/...` key without double-prefixing.
- Upload **requires** a set Shared Sync Owner ID; FormData includes **`owner`** for reliable server-side resolution.

## Planned next implementation block (selected requirements)
- Netflix-style landing (`/`) and app shell (`/app`).
- Auth: email + Google.
- Multi-profile with single-user-first defaults.
- Avatar upload + preset selection.
- Per-profile favorites/save/meta preferences.
- Hash-based metadata matching (CRC32 + MD5/SHA1).
- Quiet scraper mode and rescrape-broken-only controls.
- Hero banner mode toggle (auto/custom).
- Cloud health panel + full backup/restore bundle.
