# Merge-TIFF

<div align="center">

[![Build Status](https://img.shields.io/github/actions/workflow/status/Shreyansh2203/Merge-TIFF/ci.yml?branch=main&label=CI&logo=github-actions&style=for-the-badge)](https://github.com/Shreyansh2203/Merge-TIFF/actions)
[![CodeQL](https://img.shields.io/github/actions/workflow/status/Shreyansh2203/Merge-TIFF/codeql.yml?branch=main&label=CodeQL&logo=github&style=for-the-badge)](https://github.com/Shreyansh2203/Merge-TIFF/security/code-scanning)
[![Security](https://img.shields.io/github/actions/workflow/status/Shreyansh2203/Merge-TIFF/security.yml?branch=main&label=Security&logo=shield&style=for-the-badge)](https://github.com/Shreyansh2203/Merge-TIFF/security)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js)](https://nextjs.org/)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Vercel Ready](https://img.shields.io/badge/Vercel-Ready-black?style=for-the-badge&logo=vercel)](https://vercel.com/)

</div>

<details open>
<summary><b>Table of Contents</b></summary>

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Security](#-security)
- [Contributing](#-contributing)
- [License](#-license)

</details>

---

## Overview

**Merge-TIFF** is a production-grade TIFF image merging service with a Next.js frontend and a Python/Flask backend API. Upload multiple TIFF/TIFF files, merge them into a single output file, and download the result — all with built-in rate limiting, pixel-budget guards, and serverless-friendly request/response size caps.

Built for deployment on Vercel (frontend) + any Python-compatible host (API), with serverless-aware limits that respect the 4.5 MB edge payload ceiling.

---

## Features

| Feature | Description |
|---------|-------------|
| **Multi-file merge** | Upload up to 20 TIFF/TIFF images per request |
| **Pixel budget** | 50 MP total decoded-pixel budget enforced from the TIFF header before any page is decoded |
| **Request/Response caps** | 4 MB request + 4 MB response limits (under the 4.5 MB Vercel edge ceiling) |
| **Rate limiting** | 30 requests per 60-second rolling window per client IP |
| **Filename sanitization** | Unsafe bytes stripped from uploaded filenames before embedding in output TIFF tags |
| **Deflate compression** | Adobe Deflate compression on merged output |
| **Health endpoint** | `GET /health` returns service status, limits, and budgets |
| **Type-safe frontend** | Next.js 16 + React 19 + TypeScript, ESLint + Prettier configured |
| **100% test coverage** | UI + E2E + API test suites with enforced coverage gates |

---

## Tech Stack

<details>
<summary><b>Frontend</b></summary>

- [Next.js 16](https://nextjs.org/) — App Router, serverless-first
- [React 19](https://react.dev/) + React DOM
- [TypeScript 6](https://www.typescriptlang.org/)
- [Tailwind CSS 4](https://tailwindcss.com/)
- [ESLint](https://eslint.org/) + [Prettier](https://prettier.io/)
- [Vitest](https://vitest.dev/) + [Playwright](https://playwright.dev/) (unit + E2E)

</details>

<details>
<summary><b>Backend API</b></summary>

- [Python 3.12+](https://www.python.org/)
- [Flask](https://flask.palletsprojects.com/) — REST API (`/api/merge`, `/health`)
- [Pillow](https://python-pillow.org/) — TIFF encoding/decoding
- [Werkzeug](https://werkzeug.palletsprojects.com/) — request/response size enforcement

</details>

---

## Project Structure

```
Merge-TIFF/
├── api/
│   └── merge.py              # Flask API: /api/merge, /health
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── globals.css
│   │   └── favicon.ico
│   └── lib/
│       └── downloadName.ts   # client-side filename sanitization
├── tests/
│   ├── test_api.py
│   ├── test_deploy_config.py
│   ├── test_merge_images.py
│   ├── e2e/
│   └── js/
├── .github/workflows/
│   ├── ci.yml
│   ├── codeql.yml
│   └── security.yml
├── next.config.mjs
├── package.json
├── tsconfig.json
├── vercel.json
├── Dockerfile
├── pytest.ini
├── ruff.toml
└── LICENSE
```

---

## Quick Start

### Prerequisites

- Node.js ≥ 24
- Python 3.12+

### Frontend (Next.js)

```bash
cd Merge-TIFF

# Install dependencies
npm install

# Run dev server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

### Backend API (Flask)

```bash
cd Merge-TIFF

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the API (http://localhost:5328 by default)
python api/merge.py
```

### Run everything with Docker

```bash
docker build -t merge-tiff .
docker run -p 3000:3000 -p 5328:5328 merge-tiff
```

---

## Configuration

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `PORT` | `5328` | Backend API port |
| `MAX_REQUEST_BYTES` | `4194304` (4 MB) | Max upload request body |
| `MAX_RESPONSE_BYTES` | `4194304` (4 MB) | Max merged output body |
| `MAX_FILES` | `20` | Max TIFF files per request |
| `MAX_IMAGE_PIXELS` | `50000000` (50 MP) | Total decoded pixel budget |
| `MAX_TOTAL_IMAGE_PIXELS` | `50000000` (50 MP) | Hard pixel cap per request |
| `RATE_LIMIT_REQUESTS` | `30` | Requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate-limit window in seconds |

Set these in your hosting provider (Vercel environment variables, Render env, Docker `-e`, etc.).

---

## API Reference

### `POST /api/merge`

Merge uploaded TIFF files into a single TIFF.

**Form Data**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | `file[]` | Yes | TIFF/TIFF images (max 20) |

**Response** — `image/tiff` file download named `merged_output.tif`

**Errors**

| Status | Meaning |
|--------|---------|
| `400` | Bad request (no files, invalid TIFF, unsafe filename) |
| `413` | Payload too large (request or response exceeds caps) |
| `429` | Rate limit exceeded |
| `500` | Server error during merge |

### `GET /health`

Service health and configuration snapshot.

```json
{
  "status": "ok",
  "max_files": 20,
  "max_image_pixels": 50000000,
  "max_total_image_pixels": 50000000,
  "max_request_bytes": 4194304,
  "max_response_bytes": 4194304
}
```

---

## Testing

```bash
# Frontend unit + UI tests
npm run test:ui

# Frontend E2E (Playwright)
npm run test:e2e

# Backend API tests
cd Merge-TIFF
pip install -r requirements.txt  # includes pytest group
pytest tests/ -q
```

Coverage gate: UI tests enforce 100% line/function coverage on `src/lib/**` and `src/app/page.tsx`.

---

## Deployment

| Platform | Target | Config |
|----------|--------|--------|
| **Vercel** | Frontend | `vercel.json` + `next.config.mjs` |
| **Render / Railway / Fly** | Backend API | `Dockerfile` or `python api/merge.py` |
| **Docker** | Full stack | `docker build -t merge-tiff .` |

On Vercel, set `RATE_LIMIT_REQUESTS`, `MAX_FILES`, and pixel budgets as project environment variables. Put an edge rate limiter (Vercel WAF / Cloudflare) in front of `/api/merge` if running more than one function instance.

---

## Security

- ✅ Filename sanitization strips control bytes and path separators before writing TIFF tags
- ✅ Request/response size caps prevent 413 FUNCTION_PAYLOAD_TOO_LARGE at the edge
- ✅ Pixel budget prevents decompression-bomb memory exhaustion
- ✅ Rate limiting per client IP
- ✅ CodeQL + Dependency Review on every push
- ✅ Bandit + Vulture on Python codebase

See [SECURITY policy](https://github.com/Shreyansh2203/Merge-TIFF/security/policy) for disclosure instructions.

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Run lint + format + typecheck:
   ```bash
   npm run lint && npm run format:check && npm run typecheck
   pip install ruff && ruff check api/ && ruff format --check api/
   ```
4. Run tests (`npm run test:ui` + `pytest tests/`)
5. Commit and open a Pull Request

See [CONTRIBUTING guidelines](https://github.com/Shreyansh2203/Merge-TIFF/blob/main/CONTRIBUTING.md) for details.

---

## License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Made with ❤️ by [Shreyansh Srivastava](https://github.com/Shreyansh2203)**

[![GitHub stars](https://img.shields.io/github/stars/Shreyansh2203/Merge-TIFF?style=social)](https://github.com/Shreyansh2203/Merge-TIFF/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Shreyansh2203/Merge-TIFF?style=social)](https://github.com/Shreyansh2203/Merge-TIFF/network)

</div>