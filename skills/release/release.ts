/**
 * Release automation CLI for the AI-snippets workspace.
 *
 * Runs in the TARGET repo (CWD).  Zero-dependency Node.js ≥ 18.
 *
 * Tag-target rule:
 *     The release tag always points at the HEAD of origin/main after the
 *     testing→main promotion PR is merged.  Tags are formatted as vX.Y.Z
 *     (one leading 'v' prefix).
 *
 * Version normalization:
 *     Any version input (X.Y.Z, vX.Y.Z, etc.) is normalized by stripping a
 *     single leading 'v'.  Internal comparisons use bare X.Y.Z; tags are
 *     always vX.Y.Z.
 *
 * Usage:
 *     npx tsx skills/release/release.ts <subcommand> [options]
 *
 * Subcommands:
 *     preflight [--version X]   Validate repo state and optional version.
 *     changes   [--base TAG] [--out FILE]  Draft changelog notes.
 *     check-version --version X  Validate version ordering.
 *     finalize  --version X --notes FILE [--commit SHA]  Tag and create release.
 *     post-verify --version X   Verify release was published correctly.
 *
 * Keep in sync with skills/release/release.py.
 */

import { execFileSync, spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

// ---------------------------------------------------------------------------
// Helpers (mirroring scripts/verify.py style)
// ---------------------------------------------------------------------------

const _VERSION_RE: RegExp = /^\d+\.\d+\.\d+$/;
const _COMMIT_RE: RegExp = /^[0-9a-f]{7,40}$/;

function fail(msg: string): void {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

function ok(msg: string): void {
  console.log(`  OK: ${msg}`);
}

/** Minimal shlex.join replacement for display purposes. */
function shlexJoin(cmd: string[]): string {
  return cmd.map(arg => {
    if (/^[a-zA-Z0-9._\/-]+$/.test(arg)) return arg;
    return "'" + arg.replace(/'/g, "'\\''") + "'";
  }).join(' ');
}

function run(
  cmd: string[],
  opts: { capture?: boolean; check?: boolean } = {},
): { status: number; stdout: string; stderr: string } {
  const { capture = true, check = true } = opts;
  const display = shlexJoin(cmd);
  console.log(`  $ ${display}`);
  const result = spawnSync(cmd[0], cmd.slice(1), {
    encoding: 'utf-8',
    stdio: capture ? ['pipe', 'pipe', 'pipe'] : ['inherit', 'inherit', 'inherit'],
  });
  if (check && result.status !== 0) {
    const stderr = capture ? (result.stderr || '').trim() : '';
    fail(`Command failed (exit ${result.status}): ${display}\n${stderr}`);
  }
  return result;
}

function normalizeVersion(v: string): string {
  const stripped = v.startsWith('v') ? v.slice(1) : v;
  if (!_VERSION_RE.test(stripped)) {
    fail(
      `Invalid version '${v}': must match X.Y.Z ` +
      `(e.g. 1.2.3 or v1.2.3)`
    );
  }
  return stripped;
}

function parseVersionTuple(v: string): [number, number, number] {
  return v.split('.').map(Number) as [number, number, number];
}

function validateCommit(sha: string): void {
  if (!_COMMIT_RE.test(sha)) {
    fail(
      `Invalid commit SHA '${sha}': must be 7-40 hex characters`
    );
  }
}

function tagName(v: string): string {
  return `v${v}`;
}

// ---------------------------------------------------------------------------
// Subcommand: preflight
// ---------------------------------------------------------------------------

interface PreflightArgs {
  version?: string;
}

function cmdPreflight(args: PreflightArgs): void {
  console.log('[preflight] Validating release prerequisites\n');

  // Dirty tree check
  let result = run(['git', 'status', '--porcelain']);
  if (result.stdout.trim()) {
    fail('Working tree is dirty — commit or stash changes first');
  }

  // Current branch
  result = run(['git', 'branch', '--show-current']);
  const branch = result.stdout.trim();
  if (branch !== 'testing') {
    fail(`Must be on 'testing' branch, currently on '${branch}'`);
  }
  ok("On 'testing' branch");

  // Fetch all remotes and tags
  run(['git', 'fetch', '--all', '--tags']);

  // Sync with origin/testing
  result = run(['git', 'rev-parse', 'HEAD']);
  const localHead = result.stdout.trim();
  result = run(['git', 'rev-parse', 'origin/testing']);
  const remoteHead = result.stdout.trim();
  if (localHead !== remoteHead) {
    fail(
      `Local testing (${localHead.slice(0, 8)}) differs from ` +
      `origin/testing (${remoteHead.slice(0, 8)}) — git pull first`
    );
  }
  ok(`Local testing synced with origin/testing (${localHead.slice(0, 8)})`);

  // Check origin/main exists
  result = run(
    ['git', 'rev-parse', '-q', '--verify', 'refs/remotes/origin/main'],
    { check: false },
  );
  if (result.status !== 0) {
    fail(
      "Branch 'origin/main' does not exist — cannot promote " +
      "releases to main"
    );
  }
  ok('origin/main exists');

  // Check origin/main is an ancestor of origin/testing
  result = run(
    ['git', 'merge-base', '--is-ancestor', 'origin/main', 'origin/testing'],
    { check: false },
  );
  if (result.status !== 0) {
    fail(
      "origin/main is not an ancestor of origin/testing — promotion " +
      "PR would not be clean; sync main with testing first"
    );
  }
  ok('origin/main is ancestor of origin/testing (promotion will be clean)');

  // Previous tag — filter to valid release tags only
  result = run(['git', 'tag', '-l', 'v*']);
  const rawTags = result.stdout.trim().split('\n').map((t: string) => t.trim()).filter(Boolean);
  const tags: string[] = [];
  for (const t of rawTags) {
    const ver = t.slice(1); // strip leading 'v'
    if (_VERSION_RE.test(ver)) {
      tags.push(t);
    } else {
      console.log(`  WARN: skipping non-release tag '${t}'`);
    }
  }
  let lastTag: string | null = null;
  if (tags.length > 0) {
    const tagsSorted = tags.sort(
      (a: string, b: string) => {
        const ta = parseVersionTuple(a.slice(1));
        const tb = parseVersionTuple(b.slice(1));
        return tb[0] - ta[0] || tb[1] - ta[1] || tb[2] - ta[2];
      }
    );
    lastTag = tagsSorted[0];
    const lastVersion = lastTag.slice(1);
    ok(`Previous tag: ${lastTag} (version ${lastVersion})`);
  } else {
    ok('No existing tags — this is the first release');
  }

  if (args.version) {
    const v = normalizeVersion(args.version);
    const t = tagName(v);

    // Tag must not exist locally
    if (tags.includes(t)) {
      fail(`Tag '${t}' already exists locally`);
    }

    // Tag must not exist on remote
    result = run(['git', 'ls-remote', '--tags', 'origin', t]);
    if (result.stdout.trim()) {
      fail(`Tag '${t}' already exists on remote`);
    }

    // gh release must not exist
    const ghResult = spawnSync('gh', ['release', 'view', t], {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    if (ghResult.status === 0) {
      fail(`GitHub release '${t}' already exists`);
    }

    // pyproject.toml version check
    const pyprojectPath = 'pyproject.toml';
    if (existsSync(pyprojectPath)) {
      const pyprojectVersion = readPyprojectVersion(pyprojectPath);
      if (pyprojectVersion) {
        ok(`pyproject.toml version: ${pyprojectVersion}`);
      } else {
        ok('pyproject.toml has no version field (will be set)');
      }
    } else {
      ok('No pyproject.toml found (will be created)');
    }

    console.log(`\n  Proposed version: ${v}`);
    console.log(`  Tag: ${t}`);
  }

  if (lastTag) {
    console.log(`  Last tag: ${lastTag}`);
  } else {
    console.log('  Last tag: (none — first release)');
  }

  console.log('\nPreflight passed.');
}

// ---------------------------------------------------------------------------
// Subcommand: changes
// ---------------------------------------------------------------------------

interface ChangesArgs {
  base?: string;
  out?: string;
}

function cmdChanges(args: ChangesArgs): void {
  console.log('[changes] Drafting changelog notes\n');

  let base = args.base;
  let baseTag: string | null = null;
  let baseDate: string | null = null;
  let commits: string[] = [];
  let prLines: string[] = [];

  if (base) {
    base = normalizeVersion(base);
    baseTag = tagName(base);

    // Validate the base tag exists
    let result = run(
      ['git', 'rev-parse', '-q', '--verify', `refs/tags/${baseTag}`],
    );
    if (result.status !== 0) {
      fail(`Base tag '${baseTag}' does not exist`);
    }
    ok(`Base tag: ${baseTag}`);

    // Compute tag date in a separate call
    result = run(['git', 'log', '-1', '--format=%aI', baseTag]);
    baseDate = result.stdout.trim();
    ok(`Base tag date: ${baseDate}`);

    // Commits since base tag
    result = run(['git', 'log', `${baseTag}..HEAD`, '--oneline', '--no-decorate']);
    commits = result.stdout.trim().split('\n').map((l: string) => l.trim()).filter(Boolean);
    console.log(`  Found ${commits.length} commits since ${baseTag}`);

    // Merged PRs after base tag date
    result = run([
      'gh', 'pr', 'list', '--state', 'merged', '--base', 'testing',
      '--limit', '100', '--json', 'number,title,mergedAt',
      '--jq',
      `[.[] | select(.mergedAt >= "${baseDate}" | todate)]` +
      ` | .[] | "- #\\(.number) \\(.title)"`,
    ]);
    prLines = result.stdout.trim().split('\n').map((l: string) => l.trim()).filter(Boolean);
  } else {
    console.log('  First release — full history');
    // All commits from root
    let result = run(['git', 'log', '--oneline', '--no-decorate']);
    commits = result.stdout.trim().split('\n').map((l: string) => l.trim()).filter(Boolean);
    console.log(`  Found ${commits.length} total commits`);

    // All merged PRs
    result = run([
      'gh', 'pr', 'list', '--state', 'merged', '--base', 'testing',
      '--limit', '100', '--json', 'number,title',
      '--jq', '.[] | "- #\\(.number) \\(.title)"',
    ]);
    prLines = result.stdout.trim().split('\n').map((l: string) => l.trim()).filter(Boolean);
  }

  // Build markdown draft
  const lines: string[] = [];
  if (base) {
    lines.push(`## Commits (${baseTag}..HEAD)\n`);
  } else {
    lines.push('## Commits (full history)\n');
  }

  if (commits.length > 0) {
    for (const c of commits) {
      lines.push(`- ${c}`);
    }
  } else {
    lines.push('- (no commits found)');
  }
  lines.push('');

  lines.push('## Pull Requests\n');
  lines.push(...prLines);
  if (prLines.length === 0) {
    lines.push('- (no merged PRs found)');
  }
  lines.push('');

  const draft = lines.join('\n');

  if (args.out) {
    writeFileSync(args.out, draft);
    console.log(`\n  Draft written to: ${args.out}`);
  } else {
    console.log('\n--- Changelog Draft ---');
    console.log(draft);
    console.log('--- End Draft ---');
  }

  console.log('Changes draft complete.');
}

// ---------------------------------------------------------------------------
// Subcommand: check-version
// ---------------------------------------------------------------------------

interface CheckVersionArgs {
  version: string;
}

function cmdCheckVersion(args: CheckVersionArgs): void {
  console.log('[check-version] Validating version\n');

  const v = normalizeVersion(args.version);
  const t = tagName(v);

  const vTuple = parseVersionTuple(v);
  ok(`Version format valid: ${v}`);

  // Ordering check against last tag — skip non-release tags with warning
  let result = run(['git', 'tag', '-l', 'v*']);
  const rawTags = result.stdout.trim().split('\n').map((t: string) => t.trim()).filter(Boolean);
  const releaseTags: string[] = [];
  for (const tg of rawTags) {
    const ver = tg.slice(1);
    if (_VERSION_RE.test(ver)) {
      releaseTags.push(tg);
    } else {
      console.log(`  WARN: skipping non-release tag '${tg}'`);
    }
  }

  if (releaseTags.length > 0) {
    const releaseTagsSorted = releaseTags.sort(
      (a: string, b: string) => {
        const ta = parseVersionTuple(a.slice(1));
        const tb = parseVersionTuple(b.slice(1));
        return tb[0] - ta[0] || tb[1] - ta[1] || tb[2] - ta[2];
      }
    );
    const lastTag = releaseTagsSorted[0];
    const lastVersion = lastTag.slice(1);
    const lastTuple = parseVersionTuple(lastVersion);

    if (vTuple[0] < lastTuple[0] ||
        (vTuple[0] === lastTuple[0] && vTuple[1] < lastTuple[1]) ||
        (vTuple[0] === lastTuple[0] && vTuple[1] === lastTuple[1] && vTuple[2] <= lastTuple[2])) {
      fail(
        `Version ${v} is not greater than last tag ${lastTag} ` +
        `(${lastVersion})`
      );
    }
    ok(`Version ${v} > last tag ${lastTag}`);
  } else {
    ok('No existing tags — version ordering not applicable');
  }

  // Tag existence check
  result = run(['git', 'ls-remote', '--tags', 'origin', t]);
  if (result.stdout.trim()) {
    fail(`Tag '${t}' already exists on remote`);
  }
  ok(`Tag '${t}' does not yet exist`);

  console.log(`\nVersion ${v} (tag ${t}) is valid.`);
}

// ---------------------------------------------------------------------------
// Subcommand: finalize
// ---------------------------------------------------------------------------

interface FinalizeArgs {
  version: string;
  notes: string;
  commit?: string;
}

function cmdFinalize(args: FinalizeArgs): void {
  console.log('[finalize] Creating release\n');

  const v = normalizeVersion(args.version);
  const t = tagName(v);

  // Fetch origin
  run(['git', 'fetch', 'origin']);

  // Ancestry guard: origin/testing must be in origin/main
  let result = run(
    ['git', 'merge-base', '--is-ancestor', 'origin/testing', 'origin/main'],
    { check: false },
  );
  if (result.status !== 0) {
    fail(
      "origin/main does not contain origin/testing HEAD — merge " +
      "the testing→main promotion PR first"
    );
  }
  ok('origin/main contains origin/testing (ancestry OK)');

  // Ancestry guard: if --commit specified, validate before checkout
  if (args.commit) {
    validateCommit(args.commit);
    result = run(
      ['git', 'merge-base', '--is-ancestor', args.commit, 'origin/main'],
      { check: false },
    );
    if (result.status !== 0) {
      fail(
        `Commit '${args.commit}' is not contained in origin/main — ` +
        "the release tag must point at a commit on main"
      );
    }
  }

  // Dirty-tree guard
  result = run(['git', 'status', '--porcelain']);
  if (result.stdout.trim()) {
    fail('Working tree is dirty — commit or stash changes first');
  }

  // Checkout main
  run(['git', 'checkout', 'main']);

  // Pull ff-only
  run(['git', 'pull', '--ff-only']);

  // Determine target commit
  let target: string;
  if (args.commit) {
    target = args.commit;
    // Verify the commit exists
    run(['git', 'cat-file', '-t', target]);
    ok(`Using provided commit: ${target}`);
  } else {
    result = run(['git', 'rev-parse', 'origin/main']);
    target = result.stdout.trim();
    ok(`Using HEAD of origin/main: ${target.slice(0, 8)}`);
  }

  // Sanity: pyproject version == v
  const pyprojectPath = 'pyproject.toml';
  if (existsSync(pyprojectPath)) {
    const pyprojectVersion = readPyprojectVersion(pyprojectPath);
    if (pyprojectVersion && normalizeVersion(pyprojectVersion) !== v) {
      fail(
        `pyproject.toml version '${pyprojectVersion}' does not match ` +
        `release version '${v}'`
      );
    }
    ok(`pyproject.toml version consistent: ${pyprojectVersion}`);
  }

  // Check if tag already exists on remote (resumable finalize)
  result = run(['git', 'tag', '-l', t]);
  const localTagExists = Boolean(result.stdout.trim());

  result = run(['git', 'ls-remote', '--tags', 'origin', t]);
  const remoteTagExists = Boolean(result.stdout.trim());

  const tagAlreadyPushed = localTagExists || remoteTagExists;

  if (tagAlreadyPushed) {
    // Check if GitHub release already exists
    const ghResult = spawnSync('gh', ['release', 'view', t], {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    if (ghResult.status === 0) {
      fail(
        `Tag '${t}' and GitHub release both already exist — ` +
        `nothing to do`
      );
    }
    // Tag exists but no release — resumable path
    if (remoteTagExists) {
      ok(`Tag '${t}' exists on remote but no GitHub release — ` +
         'skipping tag creation, proceeding to release');
    } else {
      // Local tag exists but wasn't pushed yet — push it
      run(['git', 'push', 'origin', t]);
      ok(`Pushed tag ${t} to origin (skipping local creation)`);
    }
  } else {
    // Create tag
    run(['git', 'tag', '-a', t, target, '-m', `Release ${t}`]);
    ok(`Created tag ${t} at ${target.slice(0, 8)}`);

    // Push tag
    run(['git', 'push', 'origin', t]);
    ok(`Pushed tag ${t} to origin`);
  }

  // Read notes
  if (!existsSync(args.notes)) {
    fail(`Notes file not found: ${args.notes}`);
  }

  // Create GitHub release
  const ghCreateResult = spawnSync('gh', [
    'release', 'create', t,
    '--target', target,
    '--title', `Release ${t}`,
    '--notes-file', args.notes,
  ], {
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  if (ghCreateResult.status !== 0) {
    const stderr = (ghCreateResult.stderr || '').trim();
    fail(
      `gh release create failed: ${stderr}\n\n` +
      `The tag '${t}' is already pushed.  To recover:\n` +
      `  - Re-run finalize (it will skip tag creation and retry the ` +
      `release).\n` +
      `  - Or run manually:\n` +
      `    gh release create ${t} --target ${target} ` +
      `--notes-file ${args.notes}`
    );
  }
  const releaseUrl = ghCreateResult.stdout.trim();
  ok(`GitHub release created: ${releaseUrl}`);

  console.log(`\n  Tagged commit: ${target}`);
  console.log(`  Tag: ${t}`);
  console.log(`  Release: ${releaseUrl}`);
  console.log('\nFinalize complete.');
}

// ---------------------------------------------------------------------------
// Subcommand: post-verify
// ---------------------------------------------------------------------------

interface PostVerifyArgs {
  version: string;
}

function cmdPostVerify(args: PostVerifyArgs): void {
  console.log('[post-verify] Verifying release\n');

  const v = normalizeVersion(args.version);
  const t = tagName(v);

  // Expected commit = HEAD of origin/main
  run(['git', 'fetch', 'origin']);
  let result = run(['git', 'rev-parse', 'origin/main']);
  const expected = result.stdout.trim();
  ok(`Expected commit (origin/main HEAD): ${expected.slice(0, 8)}`);

  // Tag points at expected commit — peel annotated tags
  // Use refs/tags/<t>* pattern to include the ^{} peeled line
  result = run(['git', 'ls-remote', 'origin', `refs/tags/${t}*`]);
  const output = result.stdout.trim();
  if (!output) {
    fail(`Tag '${t}' not found on remote`);
  }

  // Resolve the peeled commit SHA:
  //   1. Prefer refs/tags/vX.Y.Z^{} (dereferenced, for annotated tags)
  //   2. Fall back to refs/tags/vX.Y.Z (lightweight or raw)
  let peeledLine: string | null = null;
  let plainLine: string | null = null;
  for (const line of output.split('\n')) {
    const parts = line.split(/\s+/);
    if (parts.length >= 2) {
      const ref = parts[1];
      if (ref === `refs/tags/${t}^{}`) {
        peeledLine = line;
      } else if (ref === `refs/tags/${t}`) {
        plainLine = line;
      }
    }
  }

  const chosenLine = peeledLine || plainLine;
  if (!chosenLine) {
    fail(`Tag '${t}' not found in ls-remote output`);
  }

  const tagSha = chosenLine.split(/\s+/)[0];
  const tagType = peeledLine ? 'peeled' : 'direct';
  ok(`Tag '${t}' resolved (${tagType}): ${tagSha.slice(0, 8)}`);

  if (tagSha !== expected) {
    fail(
      `Tag '${t}' points at ${tagSha.slice(0, 8)}, expected ${expected.slice(0, 8)}`
    );
  }
  ok(`Tag '${t}' points at ${tagSha.slice(0, 8)} (matches origin/main)`);

  // Ancestry guard: origin/testing must be in origin/main
  result = run(
    ['git', 'merge-base', '--is-ancestor', 'origin/testing', 'origin/main'],
    { check: false },
  );
  if (result.status !== 0) {
    fail(
      "origin/testing is not contained in origin/main — " +
      "promotion PR not merged?"
    );
  }
  ok('origin/testing is contained in origin/main');

  // gh release exists
  const ghResult = spawnSync('gh', [
    'release', 'view', t, '--json', 'url',
  ], {
    encoding: 'utf-8',
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  if (ghResult.status !== 0) {
    fail(`gh release view failed for '${t}'`);
  }
  const releaseData = JSON.parse(ghResult.stdout);
  const releaseUrl = releaseData.url || '';
  ok(`GitHub release exists: ${releaseUrl}`);

  // Branch and tree state
  result = run(['git', 'branch', '--show-current']);
  const branch = result.stdout.trim();
  if (branch !== 'main') {
    fail(`Expected branch 'main', currently on '${branch}'`);
  }
  ok("On 'main' branch");

  result = run(['git', 'status', '--porcelain']);
  if (result.stdout.trim()) {
    fail('Working tree is dirty');
  }
  ok('Working tree is clean');

  result = run(['git', 'rev-parse', 'HEAD']);
  const localHead = result.stdout.trim();
  if (localHead !== expected) {
    fail(
      `Local HEAD (${localHead.slice(0, 8)}) differs from ` +
      `origin/main (${expected.slice(0, 8)})`
    );
  }
  ok(`Local == origin/main (${localHead.slice(0, 8)})`);

  console.log(`\n  Version: ${v}`);
  console.log(`  Tag: ${t}`);
  console.log(`  Tagged commit: ${expected}`);
  console.log(`  Release URL: ${releaseUrl}`);
  console.log(`  Branch: ${branch} (clean, synced)`);
  console.log('\nPost-verify passed.');
}

// ---------------------------------------------------------------------------
// TOML reader — scoped to [project] table only
// ---------------------------------------------------------------------------

function readPyprojectVersion(path: string): string {
  const content = readFileSync(path, 'utf-8');
  const lines = content.split('\n');

  // Find [project] table header
  let inProject = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (/^\[project\]\s*$/.test(trimmed)) {
      inProject = true;
      continue;
    }
    if (inProject && /^\[/.test(trimmed)) {
      break; // next table header — exit [project] scope
    }
    if (inProject) {
      const m = trimmed.match(/^version\s*=\s*["']([^"']+)["']/);
      if (m) return m[1];
    }
  }
  return '';
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

interface ParsedArgs {
  positional: string[];
  args: Record<string, string | undefined>;
}

function parseArgs(argv: string[]): ParsedArgs {
  const args: Record<string, string | undefined> = {};
  const positional: string[] = [];
  const raw = argv.slice(2);

  for (let i = 0; i < raw.length; i++) {
    const arg = raw[i];
    if (arg === '--version' || arg === '--base' || arg === '--out' ||
        arg === '--notes' || arg === '--commit') {
      if (i + 1 < raw.length) {
        args[arg.slice(2)] = raw[++i];
      }
    } else if (arg === '--help' || arg === '-h') {
      printUsage();
      process.exit(0);
    } else {
      positional.push(arg);
    }
  }

  return { positional, args };
}

function printUsage(): void {
  console.error(`usage: npx tsx skills/release/release.ts <subcommand> [options]

subcommands:
  preflight [--version X]        Validate repo state before release
  changes   [--base TAG] [--out FILE]  Draft changelog notes
  check-version --version X      Validate version format and ordering
  finalize  --version X --notes FILE [--commit SHA]  Tag and create release
  post-verify --version X        Verify release was published correctly`);
}

function main(): void {
  const { positional, args } = parseArgs(process.argv);

  if (positional.length !== 1) {
    printUsage();
    process.exit(2);
  }

  const command = positional[0];

  switch (command) {
    case 'preflight':
      cmdPreflight(args as PreflightArgs);
      break;
    case 'changes':
      cmdChanges(args as ChangesArgs);
      break;
    case 'check-version':
      if (!args.version) {
        console.error("error: the following arguments are required: --version");
        process.exit(2);
      }
      cmdCheckVersion(args as unknown as CheckVersionArgs);
      break;
    case 'finalize':
      if (!args.version || !args.notes) {
        console.error("error: the following arguments are required: --version, --notes");
        process.exit(2);
      }
      cmdFinalize(args as unknown as FinalizeArgs);
      break;
    case 'post-verify':
      if (!args.version) {
        console.error("error: the following arguments are required: --version");
        process.exit(2);
      }
      cmdPostVerify(args as unknown as PostVerifyArgs);
      break;
    default:
      printUsage();
      process.exit(2);
  }
}

main();