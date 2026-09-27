# Merge-TIFF

[![CI](https://github.com/Shreyansh2203/Merge-TIFF/actions/workflows/ci.yml/badge.svg)](https://github.com/Shreyansh2203/Merge-TIFF/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Next.js: 16](https://img.shields.io/badge/Next.js-16-black.svg)](package.json)
[![React: 19](https://img.shields.io/badge/React-19-61dafb.svg)](package.json)
[![Python: 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](api/index.py)

A web tool that merges multiple TIFF images into a single multi-page TIFF, in the browser. The page never sees your files: the browser uploads them to a serverless function that reassembles them with Pillow and streams one `.tif` back.

---

## Problem

Multi-page TIFFs are what scanners, microform readers, and geospatial tooling actually produce, but the common failure mode is a folder of single-page TIFFs and a viewer that only opens the first one. The usual remedies are a desktop GUI (not available on a locked-down machine), a commercial SDK, or an ImageMagick shell pipeline (not available where there is no shell).

Merge-TIFF does the one thing you need, in a browser tab, with no install and no account.

---

## Architecture

```mermaid
flowchart TD
    User([Browser]) -->|drag &amp; drop / picker| UI["Next.js 16 client component\nsrc/app/page.js"]
    UI -->|multipart POST /api/merge| Proxy["Vercel rewrite\nvercel.json"]
    Proxy --> Fn["Python function\napi/index.py"]
    Fn --> Flask[Flask app: /api/merge, /health]
    Flask --> Guard{Limits}
    Guard -->|bytes, file count, pixels| Reject["413 / 400"]
    Guard -->|accepted| Merge["merge_images()\nPillow AppendingTiffWriter"]
    Merge -->|application/image/tiff| UI
```

Two tiers, joined by one rewrite:

- **Tier 1 — Next.js 16 (App Router).** Renders the dropzone, owns file selection and client-side error state, and downloads the result as a blob. It is a static page; it holds no image data.
- **Tier 2 — Python function.** `api/index.py` is a Flask WSGI app. It enforces the upload limits, decodes with Pillow, and writes the multi-page TIFF.

The browser calls `/api/merge`, which `vercel.json` routes to the Python function. The rewrite selects the function; it does not rewrite the path the function sees, so Flask still matches on `/api/merge`. See [Deployment](#deployment-on-vercel).

---

## Features

- **Multi-page merge.** One output `.tif` with one page per uploaded file, in the order you added them.
- **Per-page provenance.** Every page carries its source filename in the TIFF `PageName` (270) and `PageDescription` (285) tags.
- **Honest failures.** A rejected file fails the whole request with the offending name. The endpoint never returns a "successful" merge that quietly dropped pages.
- **Upload limits.** Request bytes, file count, and decoded pixel count are all capped, so a single request cannot exhaust function memory.
- **Decompression-bomb defence.** `Image.MAX_IMAGE_PIXELS` is set explicitly and `Image.DecompressionBombError` is handled, so a tiny crafted TIFF cannot expand into gigabytes.
- **No error-detail leaks.** Failures are logged server-side; clients receive a generic message.
- **Accessible UI.** The dropzone is a real `<button>` with a visible focus ring, inline `role="alert"` / `role="status"` messaging, and no `alert()` dialogs.

---

## Requirements

- Node.js >= 20.9 (Next.js 16 minimum)
- Python >= 3.12 (matches the Vercel Python runtime default)

---

## Local Development

The two tiers run as separate processes in development. Run them in two terminals.

### 1. The Python function

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python api/index.py
```

That serves the API on <http://127.0.0.1:5328>:

```bash
curl http://127.0.0.1:5328/health
# {"max_files":20,"max_image_pixels":50000000,"max_request_bytes":4194304,"status":"ok"}
```

### 2. The Next.js frontend

```bash
npm install
npm run dev
```

That serves the UI on <http://localhost:3000>.

### 3. Point the frontend at the local function

`next dev` serves the app but has no `/api/merge` route of its own, so the browser's `fetch('/api/merge')` will 404 until you add a rewrite. Add this to a local, uncommitted `next.config.mjs` (or commit it if you prefer a proxy in development):

```js
async rewrites() {
  return [{ source: '/api/:path*', destination: 'http://127.0.0.1:5328/api/:path*' }];
}
```

---

## Quality Gates

```bash
npm run lint                        # ESLint via eslint-config-next
npm run build                       # next build
python -m pytest                    # Flask + Pillow merge tests
```

CI runs the same three on every push to `main` and every pull request, plus two extra gates:

- `npm audit --audit-level=high` — fails on a new high or critical advisory.
- `npm run lint -- --max-warnings=0` — lint *warnings* fail the build, not just errors. Locally `npm run lint` stays permissive; pass `-- --max-warnings=0` yourself to reproduce CI.

The pytest suite generates its fixtures in `tmp_path` with Pillow, so no binary test assets are committed.

---

## API

### `POST /api/merge`

`multipart/form-data` with one or more parts named `files`.

| Status | Meaning |
|---|---|
| `200` | Merged TIFF returned as `image/tiff`, `Content-Disposition: attachment` |
| `400` | No `files` field, no files selected, non-TIFF extension, unreadable or corrupt TIFF, unsupported page-mode combination, or more than 20 files |
| `413` | Request body exceeds 4 MB |
| `500` | Unexpected server fault (detail logged, never returned) |

All error responses are JSON: `{ "error": "<human-readable reason>" }`.

Example:

```bash
curl -X POST http://127.0.0.1:5328/api/merge \
  -F "files=@page1.tif" \
  -F "files=@page2.tif" \
  -o merged.tif
```

### `GET /health`

```json
{
  "status": "ok",
  "max_request_bytes": 4194304,
  "max_files": 20,
  "max_image_pixels": 50000000
}
```

---

## Limits and Behaviour

| Limit | Value | Rationale |
|---|---|---|
| Request body (this app) | 4 MB | `app.config["MAX_CONTENT_LENGTH"]`; returns `413` with a JSON error |
| Request body (Vercel) | 4.5 MB | Hard platform cap; over it the edge returns `413 FUNCTION_PAYLOAD_TOO_LARGE` |
| Response body (Vercel) | 4.5 MB | Same hard cap on the way out; over it the edge returns `500 FUNCTION_RESPONSE_PAYLOAD_TOO_LARGE` |
| Files per request (this app) | 20 | Bounds decode work per invocation |
| Decoded pixels per image (this app) | 50,000,000 | `Image.MAX_IMAGE_PIXELS`; error is raised past 2x this |
| Output compression | `tiff_adobe_deflate` | Lossless, and uniform because Pillow threads one `encoderinfo` per save |

Things worth knowing:

- **Vercel caps both directions at 4.5 MB, and this app's own request cap is lower at 4 MB.** The 4 MB application limit is deliberately set below the platform's 4.5 MB so that an oversized upload is rejected by this app with a clear JSON message, rather than being cut off at the edge with an opaque platform error.
- **The 4.5 MB response cap is the practical ceiling on a merge.** The merged TIFF is returned as a single in-memory body, not streamed, so a merge whose output exceeds 4.5 MB fails at the edge with a `500` even though the request was accepted and the merge itself succeeded. Fewer, smaller, or better-compressing pages raise this ceiling. This is a platform limit, not a bug in the app; removing it would require client-direct upload to Vercel Blob.
- **Output compression is uniform across every page.** Pillow threads a single `encoderinfo` per save, so the one `compression=` value passed to every `image.save()` on the shared `AppendingTiffWriter` applies to all pages. Per-page compression therefore cannot be preserved, and every page is written as Adobe Deflate.
- **Mixed modes and sizes are supported.** Differing colour modes, bit depths, and page sizes round-trip correctly, because each page is written with its own minimal tag set rather than inheriting the first page's tags. The one unsupported combination is bilevel (`1`) together with palette (`P`/`PA`), which returns `400` with instructions.
- **One page per uploaded file.** A multi-page TIFF that you upload is contributed as a single page — its frames are not expanded, so a 50-frame scan becomes one page of the output. Upload the frames as separate files to get 50 pages.
- **Untrusted input.** Files are decoded in memory and never written to disk.

---

## Deployment on Vercel

1. Import the repository at [vercel.com/new](https://vercel.com/new). Keep the framework preset on **Next.js**.
2. `requirements.txt` is read automatically and Flask, Pillow, and Werkzeug are installed into the Python function.
3. `api/index.py` is treated as a file-based Python function. Vercel serves it at its file path and loads the module-level `app` variable, which is this project's WSGI callable.
4. `vercel.json` routes `/api/(.*)` and `/health` to that function. Vercel rewrites change which function handles a request, not the path the function observes, so Flask's own `/api/merge` and `/health` routes match.
5. The `if __name__ == "__main__"` block in `api/index.py` is dead on Vercel — the module is imported, not run as a script — and exists only for local development.

### Required first-deploy check: the framework preset

**This is the one failure mode that can take the entire site down, and it cannot be detected from the repository. It must be confirmed against a real deployment.**

#### Why the risk is concrete

This repository satisfies both conditions of Vercel's Python *framework* preset detection:

- `requirements.txt` names a framework Vercel recognises — `Flask==3.0.3`.
- `api/index.py` exposes a top-level variable named `app` that is a Flask instance. `index.py` is one of the exact entrypoint filenames Vercel searches, and `api/` is one of the directories it searches them in.

Vercel's own documentation states that [a Python framework preset takes precedence over file-based functions](https://vercel.com/docs/functions/runtimes/python/api-directory#framework-preset-precedence): when a preset is detected, the framework application handles **all** requests and the files under `/api` stop becoming separate Functions. This project is a Next.js site that depends on that file-based function, so a Flask preset selection breaks the site outright.

#### The exact check to perform

Immediately after the first deploy completes:

1. Open the project at <https://vercel.com/dashboard> → **Merge-TIFF** → **Settings** → **Build & Deployment**.
2. Read the **Framework Preset** field.
3. **It must read `Next.js`.** If it reads `Flask`, the deployment is broken — apply the remedy below before doing anything else.

#### The exact symptom to look for

If the Flask preset was selected, Flask receives every request including `/`. No Flask route matches `/`, so the browser renders Flask's built-in error page: a bare, unstyled `404 Not Found` on an empty white page — no dropzone, no styles, no page content.

Two things make this easy to misdiagnose:

- **The deployment reports success.** There is no failed build, no error banner, and nothing in the deploy logs points at the cause.
- **`/health` and `/api/merge` may still respond**, because Flask *does* serve those two paths. If you only test the API, the site looks healthy while the actual user-facing page is a 404. Always check `GET /` first.

A correct deployment shows the styled dropzone page with the heading **TIFF Merger**.

#### The exact remedy

1. **Settings** → **Build & Deployment** → **Framework Preset** → select **Next.js**.
2. **Redeploy.** Changing the preset does not rebuild already-built output, so the fix does not take effect until a new build runs. Use **Deployments** → the most recent deployment → **⋯** → **Redeploy**, or push an empty commit.
3. Re-run the smoke test below, starting with `GET /`.

#### Smoke test

Run all three against the deployed URL. All three must behave as listed.

| Check | Expected |
|---|---|
| `GET /` | `200`, styled page containing the heading `TIFF Merger`. A bare unstyled 404 means the framework preset is wrong — see the remedy above. |
| `GET /health` | `200` with `content-type: application/json` and body `{"max_files":20,"max_image_pixels":50000000,"max_request_bytes":4194304,"status":"ok"}` |
| `POST /api/merge` with two `.tif` parts | `200` with `content-type: image/tiff` and `content-disposition` naming `merged_output.tif`; the body opens as a 2-page TIFF |

```bash
curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' https://<your-domain>/
curl -sS https://<your-domain>/health
curl -sS -X POST https://<your-domain>/api/merge \
  -F "files=@page1.tif" \
  -F "files=@page2.tif" \
  -o merged.tif
```

---

## Open items and recommendations

- **The framework preset is the one unverifiable-from-CI risk.** Nothing in this repository or its CI can detect a wrong preset; it needs one manual check per new Vercel project, as described in [Required first-deploy check](#required-first-deploy-check-the-framework-preset). If the project is ever recreated on Vercel, repeat the check — it is not a one-time event.
- **There is no authentication or rate limiting on `/api/merge`.** It is intentionally public and unauthenticated: adding auth would require a committed secret or edge-level work that was left out of scope. The resource bounds (4 MB, 20 files, 50M pixels) are the only protection, and they bound per-request cost rather than request rate.
- **A merge whose output exceeds 4.5 MB cannot be served from this architecture.** The 4.5 MB response cap is enforced by Vercel below the application. Lifting it means client-direct upload to Vercel Blob, which is a redesign rather than a config change.
- **There is no Python dependency audit in CI.** Node advisories are gated by `npm audit --audit-level=high`; the Python side has no equivalent, so a Pillow or Werkzeug advisory would only be found by remembering to check. Adding `pip-audit` as a CI step is the obvious follow-up.

---

## License

[MIT License](LICENSE).
