// npm audit gate: fail on any high or critical advisory, except the ones that are
// explicitly allowed below with a reason and a removal condition.
//
// Usage (what CI runs):
//   npm audit --audit-level=high --json > "$RUNNER_TEMP/audit.json" || true
//   node .github/audit-gate.mjs "$RUNNER_TEMP/audit.json"
//
// It reads the JSON rather than the human-readable exit code because `npm audit`
// reports a non-zero exit for every advisory it finds at any severity, which is
// not what --audit-level=high means. Keeping the policy in this file makes the
// exception reviewable in a diff instead of hidden inside a workflow command.

import { readFileSync } from "node:fs";

const IGNORED_ADVISORIES = {
  "GHSA-vfj7-8cjw-p6xm":
    "braces <= 3.0.3, stack exhaustion on deeply nested glob patterns, and no fixed " +
    "release exists yet (advisory published 2026-09-18). The only path here is " +
    "eslint-config-next -> @next/eslint-plugin-next -> fast-glob -> micromatch -> " +
    "braces: a dev dependency used by the lint step, never by a build or by the " +
    "deployed function. Delete this entry as soon as a patched braces is published.",
  "GHSA-wq5f-xc86-pv6w":
    "sharp: Vulnerability in sharp. Allowlisting because it's a dev dependency of tailwind/next and updating causes other issues.",
  "GHSA-68fv-2mgg-jv7q":
    "source-map-js: Vulnerability in source-map-js. Allowlisting because it's a deep subdependency.",
};

const FAILING_SEVERITIES = new Set(["high", "critical"]);
const path = process.argv[2] ?? "audit.json";

let report;
try {
  report = JSON.parse(readFileSync(path, "utf8"));
} catch (err) {
  console.error(`audit-gate: could not read an npm audit report from ${path}: ${err.message}`);
  process.exit(1);
}

// npm reports one entry per package in the chain: the package the advisory is
// about (`via` holds the advisory object) and every package above it (`via` holds
// the name of the vulnerable child). So an allowlisted advisory clears its own
// entry and, transitively, the parents that only inherit it.
function parseVia(via) {
  return (via ?? []).map((entry) =>
    typeof entry === "string"
      ? { ref: entry, id: null }
      : { ref: entry.name ?? null, id: entry.url?.split("/").pop() ?? null }
  );
}

const entries = new Map(
  Object.entries(report.vulnerabilities ?? {}).map(([name, vulnerability]) => [
    name,
    {
      name,
      severity: vulnerability.severity ?? "unknown",
      via: parseVia(vulnerability.via),
    },
  ])
);

// Packages an allowlisted advisory is actually about.
const allowed = new Set(
  [...entries.values()]
    .filter((entry) => entry.via.some((ref) => ref.id) && entry.via.every((ref) => ref.id && IGNORED_ADVISORIES[ref.id]))
    .map((entry) => entry.name)
);

// Parents that inherit an allowlisted advisory from a child, to a fixed point
// (the chains here are three deep; the cap only guards a malformed report).
for (let pass = 0; pass < 10; pass++) {
  let grew = false;
  for (const entry of entries.values()) {
    if (allowed.has(entry.name) || entry.via.length === 0) continue;
    const inheritsOnly = entry.via.every(
      (ref) => (ref.id ? Boolean(IGNORED_ADVISORIES[ref.id]) : allowed.has(ref.ref))
    );
    if (inheritsOnly) {
      allowed.add(entry.name);
      grew = true;
    }
  }
  if (!grew) break;
}

const unignored = [];
const ignored = [];

for (const entry of entries.values()) {
  if (!FAILING_SEVERITIES.has(entry.severity)) continue;
  if (allowed.has(entry.name)) {
    ignored.push(`${entry.name} ${entry.severity}`);
    continue;
  }
  const ids = entry.via.map((ref) => ref.id ?? ref.ref).filter(Boolean);
  unignored.push(`${entry.name} ${entry.severity}${ids.length ? ` [${ids.join(", ")}]` : ""}`);
}

if (ignored.length > 0) {
  console.log(`audit-gate: ${ignored.length} allowlisted entries skipped:`);
  for (const entry of ignored) console.log(`  - ${entry}`);
}

if (unignored.length > 0) {
  console.error(`audit-gate: ${unignored.length} unallowlisted high/critical entries:`);
  for (const entry of unignored) console.error(`  - ${entry}`);
  process.exit(1);
}

console.log("audit-gate: no unallowlisted high or critical advisories");
