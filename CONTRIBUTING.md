# Contributing to Merge-TIFF

Thanks for taking a look. This file covers how to run the thing, how the two
parts of it fit together, and what CI will check before a change lands.

## Prerequisites

- Node.js >= 24. Next.js 16 documents 20.9 as its own minimum, but **Node 20
  went end-of-life on 2026-04-30**, so this project deliberately raises the
  floor to the Active LTS line. The floor is pinned in `engines.node` in
  `package.json`, in the committed `.node-version` file, and as
  `node-version: "24"` in both workflows; change all four together or not at
  all.
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
python -m pytest          # Flask + Pillow merge tests, with the coverage gate
npm run test:ui           # node --test, download-name and dev-rewrite config
npm run test:ui:coverage  # the same tests, with the coverage thresholds
npm run lint              # add -- --max-warnings=0 to match CI
npm run build             # next build (Turbopack)
pip-audit -r requirements.txt
pip-audit -r requirements-dev.txt
npm audit --audit-level=high
```

CI runs all of these on every push to `main` and every pull request, plus
`pip-audit` and `npm audit` again on a weekly schedule against the pinned
versions. `.github/workflows/security.yml` can be dispatched by hand from the
**Actions** tab — run it before merging a version bump. `requirements-dev.txt`
is audited alongside `requirements.txt` for the same reason
`requirements.txt` is: a developer tool is still a dependency somebody
installed.

The pytest suite builds its fixtures in `tmp_path` with Pillow, so there are no
binary test assets in the repository and none should be added. The JavaScript
tests use Node's built-in test runner; do not add a test framework for them.

## Coverage is measured here, and that is not the same as exempting code

`pytest-cov` (pinned in `requirements-dev.txt`) is wired into `pytest.ini` via
`addopts`, so plain `python -m pytest` both measures and gates: it fails below
`--cov-fail-under` and prints a `term-missing` table. On the JavaScript side
`npm run test:ui:coverage` is the same suite with
`--experimental-test-coverage` and a 100% threshold on lines, branches and
functions. Both thresholds sit at or just below what the suite measures today
(Python 96.10%, JavaScript 100% on the modules listed below), so the gate
reports a regression rather than a target that was never reached.

Two things follow from that, and they are not in tension:

- **Measurement is expected.** If you add code, the number is expected to move
  and the gate to notice. That is the point of having it.
- **Exclusion is not.** A `# pragma: no cover` in application code, or a
  `coverage: ignore` in an ESLint rule, is a way of making the number look
  better without testing anything, and it is still rejected below. The six
  uncovered Python statements are left uncovered and named in the README rather
  than annotated away.

The JavaScript threshold is scoped to the two modules that have tests —
`src/lib/downloadName.mjs` and `next.config.mjs`, named explicitly by
`--test-coverage-include` in the npm script. `node --test` can only measure what
it loads and has no DOM, so `src/app/page.js` is outside the number. Treat 100%
as "the tested modules are fully covered", and do not quote it as coverage of
the frontend.

## Known upstream blockers

**ESLint 10 is not installable against `next@16.3.6`.** `eslint-config-next`
sets `languageOptions.parser` to Next's bundled Babel ESLint parser for every
`.js`/`.jsx`/`.mjs` file and declares `globals` for them. ESLint 10's
`SourceCode.finalize` calls `scopeManager.addGlobals()` on that scope manager,
and neither the parser bundled with `next@16.3.6` nor `typescript-eslint`
(verified through 8.70.1) implements it — every linted file dies with
`TypeError: scopeManager.addGlobals is not a function` before any rule runs.
`eslint-config-next@16.3.6` itself only asks for `eslint >=9.0.0`, while
`eslint-plugin-import`, `eslint-plugin-jsx-a11y` and `eslint-plugin-react` still
cap their peer range at `^9`, so `npm install` also emits `ERESOLVE overriding
peer dependency` warnings. Dependabot will keep opening an `eslint-10.x` branch;
close it with a note rather than merging it, and bump `eslint` when
`eslint-config-next` ships a parser that implements `addGlobals`.

**The Dependabot branches are on stale bases.** Each one is a single commit
touching only the dependency files, but they were cut from older `main`
commits, so `git diff origin/main <branch>` also shows deletions that the PR
never intended — including dropping the `Lint Python` step from `ci.yml` and
rewriting the `test:ui` script. Diff against the branch's merge-base, or make
the change by hand. Never merge one blind.

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
  "Coverage pragmas" means `# pragma: no cover` in application code or a
  `coverage: ignore` in a lint rule — a way of excluding code from the number
  rather than testing it. It does **not** mean the coverage gate is off-limits:
  `pytest.ini` carries `--cov-fail-under` and `npm run test:ui:coverage` carries
  its thresholds on purpose, and neither is a weakened test.
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
