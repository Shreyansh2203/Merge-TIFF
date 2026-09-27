# Contributing to Merge-TIFF

Thanks for taking a look. This file covers how to run the thing, how the two
parts of it fit together, and what CI will check before a change lands.

## Prerequisites

- Node.js >= 20.9 (the Next.js 16 minimum)
- Python >= 3.12 (matches the Vercel Python runtime default)

## Running it locally

The app is two processes. There is no local "run everything" script, because
there is no local Next.js route for `/api/merge` — that route is the Python
function, and on Vercel the two are joined by configuration rather than by
code.

**Terminal 1 — the Python function:**

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python api/merge.py
```

That serves the API on <http://127.0.0.1:5328>. Check it with
`curl http://127.0.0.1:5328/health`.

**Terminal 2 — the Next.js frontend:**

```bash
npm install
npm run dev
```

That serves the UI on <http://localhost:3000>.

The two are joined for you: `next.config.mjs` carries a rewrite that sends
`/api/*` to <http://127.0.0.1:5328> in development, and it registers nothing when
`NODE_ENV` is `production`, so the deployed copy is routed only by
`vercel.json`. There is nothing to edit.

## About `AGENTS.md` and `CLAUDE.md`

They are vendored Next.js coding-agent guidance blocks — tooling for automated
agents, not a claim that a human wrote this project. `CLAUDE.md` is a one-line
`@AGENTS.md` include so the same block loads for both tools. Keep them in sync
with the upstream block if Next.js changes it.

## The Flask-vs-Next architecture, in one paragraph

The UI is a static Next.js page that holds no image data; the merging is a
Flask WSGI app in `api/merge.py` that Vercel builds as a file-based Python
function. Pillow is the thing that does the work, and there is no JavaScript
library in this project that writes multi-page TIFF. The consequence to keep in
mind when you touch `api/`: **Vercel infers a Python framework preset from a
matching dependency, and a framework preset takes precedence over file-based
functions** — the Flask app would answer every request including `/` and the
site would render Flask's bare 404 while the deploy still reported success. Two
things prevent that, and both must survive your changes: `vercel.json` pins
`"framework": "nextjs"`, and no file is named one of Vercel's framework
entrypoints (`app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py`,
`asgi.py`) at the project root or in `src/`, `app/`, or `api/`.
`tests/test_deploy_config.py` fails if either is undone.

## Running the checks

```bash
python -m ruff check .    # Python lint; the rule set is pinned in ruff.toml
python -m pytest          # Flask + Pillow merge tests
npm run test:ui           # node --test, download-name and dev-rewrite config
npm run lint              # add -- --max-warnings=0 to match CI
npm run build             # next build (Turbopack)
pip-audit -r requirements.txt
npm audit --audit-level=high
```

CI runs all of these on every push to `main` and every pull request, plus
`pip-audit` and `npm audit` again on a weekly schedule against the pinned
versions. `.github/workflows/security.yml` can be dispatched by hand from the
**Actions** tab — run it before merging a version bump.

The pytest suite builds its fixtures in `tmp_path` with Pillow, so there are no
binary test assets in the repository and none should be added. The JavaScript
tests use Node's built-in test runner; do not add a test framework for them.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/), lowercase,
imperative subject, and a scope where one applies:

```
fix(deploy): pin the Next.js preset and give the merge function its own route
feat(api): refuse a merge that would exceed the platform response ceiling
chore(deps): bump Flask and Werkzeug off their 2023 pins
ci: pin actions to commit SHAs and enable Dependabot
test(ui): cover the download filename invariants
docs: describe the response ceiling in the API table
```

Explain *why* in the body. A reviewer cannot see the deployment you just
checked, the advisory you read, or the failure you reproduced; they can see
the diff.

## Things that will be rejected

- A GitHub Action referenced by a mutable tag. Pin the 40-character commit
  SHA and keep the tag as a trailing `# vX.Y.Z` comment.
- A weakened test: no `skip`, no `xfail`, no coverage pragmas, no deleted
  assertions. If a check is wrong, fix the check and say why in the commit.
- A secret, a token, or a `.env` file. This project has no auth, on purpose.
- A rename that puts the Python function back at a framework-entrypoint name,
  or an edit to `vercel.json` that drops the `framework` pin.
- A new runtime dependency without a corresponding entry in
  `requirements.txt` or `package.json`, and an audit run showing it is clean.

## Deploying

Vercel deploys this repository on push to `main`. Before the first deploy to a
new project, read the first-deploy section of the [README](README.md#first-deploy-what-a-repository-cannot-check)
— the framework preset in the dashboard and a three-request smoke test are the
two things CI cannot check for you.
