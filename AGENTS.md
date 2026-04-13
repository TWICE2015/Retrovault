# RetroVault

A browser-based retro game frontend built as a single Cloudflare Worker (`worker.js`). It serves a full SPA that lets users upload, manage, and play classic console ROMs using EmulatorJS.

## Cursor Cloud specific instructions

### Architecture

- The entire app is a single `worker.js` file that embeds the HTML/CSS/JS frontend as base64 chunks and exposes API endpoints for R2 storage, CORS proxying, and scraper integration.
- There is no build step, no `package.json`, and no `node_modules`. The only dependency is the `wrangler` CLI for local development.
- `wrangler.toml` configures the Worker name, entry point, and the `ROM_BUCKET` R2 binding used for cloud storage.

### Running the dev server

```
npx wrangler dev worker.js --local --port 8787
```

This starts a local Cloudflare Workers runtime with a simulated R2 bucket at `http://localhost:8787`. The `--local` flag keeps everything on the machine (no Cloudflare account needed). Local R2 data is stored in `.wrangler/state/`.

### Key API endpoints

All endpoints are path-based on the same origin (no `/api/` prefix):

- `/r2-upload` — ROM file upload (POST, multipart)
- `/r2-list` — List uploaded ROMs (GET)
- `/r2-meta-save` — Save ROM metadata (POST)
- `/r2-meta-list` — List ROM metadata (GET)
- `/bios/*` — BIOS file management (GET/HEAD)
- `/scraper-proxy` — CORS proxy for artwork scrapers
- `/lb-search` — LaunchBox game database search

### Gotchas

- There is no linting or test framework configured in this repo. The codebase is a single vanilla JS file with no transpilation.
- The HTML is base64-encoded inside `worker.js` as `CHUNKS[]`. To modify the frontend, you must decode the chunks, edit the HTML, re-encode, and update the chunks. Alternatively, extract `index.html` from `RetroVault-v2-Fixed.zip` for reference.
- EmulatorJS cores are loaded from `cdn.emulatorjs.org` at runtime, so an internet connection is needed for actual game playback.
- N64 and PSX emulation require `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` headers (already set by the Worker).
- Supabase, Firebase, and scraper integrations are optional — configured at runtime by the user through the app's Settings UI.
