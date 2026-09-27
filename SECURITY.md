# Security Policy

## Reporting a vulnerability

If you believe you have found a vulnerability in Merge-TIFF, report it privately
rather than opening a public issue:

1. **Do not create a public GitHub issue or discussion.**
2. Use [GitHub Security Advisories](https://github.com/Shreyansh2203/Merge-TIFF/security/advisories/new),
   which opens a private thread with the maintainer.
3. Include the request that reproduces it, what you expected, what happened, and
   the environment you tested on.
4. You will get an initial response within **48 hours** and updates until it is
   resolved. Once it is fixed a security advisory will be published and the
   reporter credited.

Ordinary bug reports are welcome as plain issues — this policy is about
vulnerabilities, not about things that are simply broken.

## Threat model

`POST /api/merge` is an internet-facing, anonymous, stateless endpoint that
decodes attacker-supplied image bytes and hands the result back in the response
body. That shapes everything below.

**The request is entirely attacker-controlled.** The bytes of every part, the
number of parts, the field names, and every filename are. The response is
attacker-influenced too: it is a TIFF the attacker can shape, delivered from
this deployment's origin. The first thing a requester learns from a 4xx is
therefore a message this service composed, and a 5xx must never compose one.

**Files are never written to disk.** Uploads are decoded from memory and the
merged TIFF is built in memory, so there is no upload directory to race, fill,
or read back, and nothing to clean up after a failure.

**Per-request work is bounded in the application.** The request cap is applied
while the body is read; the file cap and both pixel caps are applied from the
TIFF header before any page is decoded; the response cap is applied while the
output is written, not after. `GET /health` publishes all of those limits, so
they are information the caller could have had anyway.

**Per-request *frequency* is not bounded in this repository.** There is no auth
and no rate limiter, by design — see the README's
[Limits and Behaviour](README.md#limits-and-behaviour). The bounds above cap the
cost of one request; nothing in the code caps how many requests arrive. Rate
limiting is a deployment setting (Vercel Firewall, or a reverse proxy in front
of a self-hosted copy) and is the first thing to add before putting this behind
a domain that attracts traffic.

**Availability of the site is a configuration property.** `vercel.json` pins
`"framework": "nextjs"` on purpose: a Python framework preset takes precedence
over file-based functions, and a Flask preset answers every request with its
bare 404 while the deployment still reports success. That pin, and the absence
of any file named like a Vercel framework entrypoint, are asserted by
`tests/test_deploy_config.py`.

## Out of scope

- Load or rate testing, and the availability impact of the unbounded request
  rate described above.
- Reports that a user could merge a set of files that should have merged
  differently; that is a correctness bug, not a vulnerability.
- Claims that the endpoint should require authentication. The design decision
  and its reasoning are recorded in the README; the argument is that the
  resource bounds make the per-request cost small, not that a public endpoint
  is harmless.

## Supported versions

This project has no released versions. Security fixes land on `main`.

| Branch  | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
