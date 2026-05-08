# RetroVault PRD (Cloud Save/Load Sync + Page URLs)

## Overview
RetroVault is a Netflix-style retro game frontend that runs on Cloudflare Workers and uses Cloudflare R2 for cloud storage. This PRD covers the **cloud save state** behavior (save + load + sync) and the **URL-based page routing** foundation so pages have isolated locations (e.g. `/home`, `/roms`) with browser back/forward support.

## Goals
- **Cloud save states**: Save states are stored in **R2** and can be used across devices for the same user/owner.
- **Load behavior is reliable**: When a user loads a save state, it should load the latest state from R2 and avoid stale/cached results.
- **Netflix-like “continue” UX**: On launch, optionally prompt to load the cloud save (or auto-load when configured).
- **Page URLs**: Each view has a stable URL path (`/home`, `/library`, …) for direct navigation and isolated page state.

## Non-goals (for this build)
- Multi-slot UI beyond a numeric slot setting (1–9) and core slot wiring.
- Conflict-free “multi-device concurrent play” resolution (last-write-wins is acceptable).
- Server-side emulation or server-hosted cores (browser-based EmulatorJS only).
- User auth provider integration (no Firebase/Supabase).

## Users / Personas
- **Single player**: Wants seamless cloud saves between laptop/desktop.
- **Shared household device**: Multiple profiles may exist; each wants isolated saves.
- **Power user**: Wants “auto-load last save” and “reload after save” for quick iteration.

## Key Concepts & Data Model

### Owner-scoped namespace
- All R2 objects are stored **under an owner namespace** to isolate user data:
  - `users/{ownerId}/...` for user-owned ROMs and related objects.

### Save state object keying
- Save state objects are written to R2 under:
  - `saves/{console}/{stem}-slot{n}.state`
- The ROM metadata tracks:
  - `cloudSaveStateKey` (R2 object key)
  - `cloudSaveStateRev` and/or `cloudSaveStateUpdatedAt` (revision / cache-bust value)
  - `cloudSaveStateSlot` (slot number)
  - `cloudSaveStateUrl` (legacy/derived URL; should be treated as a convenience, not source of truth)

### R2 sidecar metadata
- ROM metadata sidecars in R2 are updated when save-state info changes so other devices can discover:
  - the latest `cloudSaveStateKey`/`rev` and related fields.

## User Stories

### Save: in-emulator “Save State” uploads to cloud
- As a user, when I click **Save State** inside the emulator, it should **upload immediately** to R2 (when enabled), so I don’t lose progress if the tab crashes.

### Save: quitting a ROM flushes pending save to cloud
- As a user, when I **exit the ROM**, any pending save state should be uploaded before the emulator is torn down.

### Load: prompt or auto-load on launch
- As a user, if a cloud save exists for the selected ROM, I can:
  - be prompted **“Load cloud save?”** at launch, or
  - choose “do not ask again” to **auto-load** when available.

### Load: clicking “Load State” syncs with cloud
- As a user, when I click **Load State** inside the emulator, it should load the **latest** cloud state from R2 and avoid cached/stale results.
- After load, the system should ensure local metadata and cloud metadata remain aligned (best-effort).

## Settings (Functional Requirements)
- **Enable Cloud Save to R2** (default on)
- **Save State Slot**: integer 1–9
- **Prompt to Load Cloud Save on Launch** (default on)
- **Reload after Save** (optional): after uploading, immediately reload the saved bytes into the emulator (for “auto play last play state” feel)

## Functional Requirements (Detailed)

### FR1 — Upload save state to R2
- When EmulatorJS produces a save-state byte buffer:
  - Upload it to `POST /r2-upload` with `owner`, `key`, and binary content.
  - Update local ROM record fields (`cloudSaveStateKey`, `rev`, slot, timestamps).
  - Persist ROM changes locally (IndexedDB) and to R2 sidecar metadata.
- Uploads must be **serialized/queued** to avoid race conditions on rapid saves.

### FR2 — Resolve load-state URL fresh from key+owner+rev
- When launching a ROM, if cloud save is available:
  - Prefer building the download URL from `cloudSaveStateKey` + `ownerId` + `rev` rather than relying on a stale stored URL string.

### FR3 — Load from R2 without caching
- When loading a cloud save state:
  - Fetch with `cache: 'no-store'` and include a cache-bust query param.
  - If fetch fails, load should be skipped gracefully (no crash).

### FR4 — Sync after load (best-effort)
- After a successful cloud load, when the upload queue is idle:
  - Re-upload the loaded bytes to R2 to ensure the system “converges” on a single latest rev and keeps sidecars consistent.
  - If upload is currently busy, defer to the existing “upload on exit” retry mechanisms.

### FR5 — URL-based view routing
- Views map to stable paths:
  - `/home`, `/systems`, `/library`, `/roms`, `/scraper`, `/settings`
- Switching views updates `history.pushState`.
- Back/forward triggers view updates via `popstate`.
- On first load, the view is derived from `window.location.pathname` without pushing a new history entry.

## Error Handling Requirements
- If no owner id is set/available, cloud save actions should:
  - show a clear toast and avoid corrupting local state.
- Network failures during upload:
  - must not crash the emulator UI.
  - should queue “retry on exit” behavior where possible.
- A missing/404 cloud save object:
  - should not prevent launching the game.

## Security / Privacy Requirements
- Owner IDs must be sanitized and never allow path traversal.
- All save-state download paths must remain owner-scoped.
- Avoid leaking cross-origin resources under COEP/CORP; proxy images when required.

## Acceptance Criteria (What “done” means)
- **AC1**: In-emulator Save State uploads to R2 and updates sidecar metadata.
- **AC2**: Exiting a ROM flushes pending saves to R2 before teardown.
- **AC3**: Launch prompt appears when cloud save exists (unless “don’t ask again” chosen).
- **AC4**: “Load State” fetches from R2 with cache bypass and loads into the emulator.
- **AC5**: After load, the system best-effort re-syncs/upload so rev+sidecar match.
- **AC6**: Navigating directly to `/roms` (etc.) opens the correct view; back/forward works.

## Implementation Notes (for engineers)
- Frontend is injected via `worker.js` `getHTML()` string patching; this is intentional to avoid separate build pipelines.
- Save state upload/download uses Worker endpoints (`/r2-upload`, `/r2-rom`) and relies on an owner id (`_rvOwnerId()`).

