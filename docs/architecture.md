# Architecture

## Overview

Merge-TIFF is a serverless TIFF image merging service with a Next.js frontend and a Python/Flask backend API.

## Components

### Frontend (Next.js 16 + React 19)
- App Router with client-side image upload
- TypeScript + Tailwind CSS 4
- Playwright E2E tests

### Backend API (Flask + Pillow)
- `/api/merge` (POST) — Merges uploaded TIFF files
- `/health` (GET) — Service health and configuration

### Processing Pipeline
1. Validate request size (≤ 4 MB)
2. Check file count (≤ 20)
3. Read TIFF headers, enforce pixel budget (50 MP total)
4. Decode and merge pages with Adobe Deflate compression
5. Sanitize filenames before embedding in TIFF tags
6. Return merged TIFF (≤ 4 MB response)

## Deployment

- Frontend: Vercel (serverless)
- Backend: Vercel Python functions or any Python host
- Docker: Full stack container

## Security

- Rate limiting: 30 req/60s per IP
- Request/response size caps: 4 MB each
- Pixel budget: 50 MP total decoded pixels
- Filename sanitization: control bytes stripped