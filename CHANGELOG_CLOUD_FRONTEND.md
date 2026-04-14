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
