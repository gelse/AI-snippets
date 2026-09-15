/**
 * Core installation logic for the ai-snippets CLI.
 *
 * Reads the bundled manifest and embedded skills tree, then installs
 * artifacts for the chosen tool into the target directories.
 */

import { readFileSync, existsSync, mkdirSync, cpSync, writeFileSync, readdirSync } from 'node:fs';
import { join, dirname, resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as readline from 'node:readline';
import { promptOverwrite } from './prompt.js';
import { mergeModesYaml } from './merge.js';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CliArgs {
  command?: string;
  tool?: string;
  scope: 'global' | 'local';
  filter: 'all' | 'skills-only' | 'agents-only';
  dryRun: boolean;
  yes: boolean;
}

interface ArtifactSpec {
  /** Tool name from the manifest (zoo, kilo, etc.) */
  tool: string;
  /** Key in the tool's manifest entry: 'modes', 'modesDir', or 'skillsDir' */
  kind: string;
  /** Source path relative to skills-embedded/ */
  src: string;
  /** Destination path (absolute, resolved at runtime) */
  dest: string;
  /** Whether this is a directory or a single file */
  isDir: boolean;
  /** Whether to merge (only for modes with merge: true) */
  merge: boolean;
}

interface InstallPlan {
  artifacts: ArtifactSpec[];
  manifest: Manifest;
}

interface Manifest {
  package: string;
  tools: Record<string, ToolEntry>;
}

interface ToolEntry {
  modes?: ArtifactConfig;
  modesDir?: ArtifactConfig;
  skillsDir?: ArtifactConfig;
}

interface ArtifactConfig {
  src: string;
  local: string | null;
  global: string | null;
  merge?: boolean;
}

interface InstallResult {
  installed: string[];
  skipped: string[];
  merged: string[];
  replacedSlugs: string[];
  keptSlugs: string[];
}

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

/** Resolve the root of the installed package (where skills-embedded/ lives). */
function packageRoot(): string {
  // When running from dist/cli.js, the package root is one level up.
  // Works both in-repo (dist/) and when installed (node_modules/@gelse/ai-snippets/dist/).
  return resolve(dirname(fileURLToPath(import.meta.url)), '..');
}

function loadManifest(root: string): Manifest {
  const manifestPath = join(root, 'skills-embedded', 'install-manifest.json');
  if (!existsSync(manifestPath)) {
    throw new Error(`install-manifest.json not found at ${manifestPath}`);
  }
  return JSON.parse(readFileSync(manifestPath, 'utf-8')) as Manifest;
}

function expandHome(p: string): string {
  if (p.startsWith('~')) {
    const home = process.env['HOME'] ?? process.env['USERPROFILE'] ?? '';
    return join(home, p.slice(1));
  }
  return p;
}

// ---------------------------------------------------------------------------
// Plan building
// ---------------------------------------------------------------------------

function buildPlan(args: CliArgs, root: string): InstallPlan {
  const manifest = loadManifest(root);
  const toolName = args.tool ?? '';

  if (!toolName) {
    // Will be resolved interactively by the caller
    return { artifacts: [], manifest };
  }

  const toolEntry = manifest.tools[toolName];
  if (!toolEntry) {
    const available = Object.keys(manifest.tools).join(', ');
    throw new Error(`Unknown tool "${toolName}". Available: ${available}`);
  }

  const artifacts = collectArtifacts(toolName, toolEntry, args, root);
  return { artifacts, manifest };
}

function collectArtifacts(
  toolName: string,
  entry: ToolEntry,
  args: CliArgs,
  root: string,
): ArtifactSpec[] {
  const artifacts: ArtifactSpec[] = [];
  const scopeKey = args.scope;
  const embeddedRoot = join(root, 'skills-embedded');

  // Modes (single file with optional merge)
  if (entry.modes && (args.filter === 'all' || args.filter === 'agents-only')) {
    const dest = entry.modes[scopeKey];
    if (dest) {
      artifacts.push({
        tool: toolName,
        kind: 'modes',
        src: entry.modes.src,
        dest: expandHome(dest),
        isDir: false,
        merge: entry.modes.merge ?? false,
      });
    }
  }

  // ModesDir (directory)
  if (entry.modesDir && (args.filter === 'all' || args.filter === 'agents-only')) {
    const dest = entry.modesDir[scopeKey];
    if (dest) {
      artifacts.push({
        tool: toolName,
        kind: 'modesDir',
        src: entry.modesDir.src,
        dest: expandHome(dest),
        isDir: true,
        merge: false,
      });
    }
  }

  // SkillsDir (directory)
  if (entry.skillsDir && (args.filter === 'all' || args.filter === 'skills-only')) {
    const dest = entry.skillsDir[scopeKey];
    if (dest) {
      artifacts.push({
        tool: toolName,
        kind: 'skillsDir',
        src: entry.skillsDir.src,
        dest: expandHome(dest),
        isDir: true,
        merge: false,
      });
    }
  }

  return artifacts;
}

// ---------------------------------------------------------------------------
// Dry-run display
// ---------------------------------------------------------------------------

function planSummary(plan: InstallPlan, args: CliArgs): string {
  const lines: string[] = [];
  lines.push(`Tool: ${args.tool ?? '(interactive)'}`);
  lines.push(`Scope: ${args.scope}`);
  lines.push(`Filter: ${args.filter}`);
  if (args.dryRun) {
    lines.push('Mode: DRY RUN (no files will be written)');
  }
  lines.push('');
  lines.push('Actions:');

  for (const art of plan.artifacts) {
    const srcPath = join(plan.artifacts.length > 0 ? packageRoot() : '', 'skills-embedded', art.src);
    const exists = existsSync(art.dest);
    if (art.isDir) {
      if (exists) {
        lines.push(`  [update] ${art.dest}/  ←  skills-embedded/${art.src}/`);
      } else {
        lines.push(`  [create] ${art.dest}/  ←  skills-embedded/${art.src}/`);
      }
    } else {
      if (exists) {
        if (art.merge) {
          lines.push(`  [merge]  ${art.dest}  ←  skills-embedded/${art.src}`);
        } else {
          lines.push(`  [overwrite] ${art.dest}  ←  skills-embedded/${art.src}`);
        }
      } else {
        lines.push(`  [create] ${art.dest}  ←  skills-embedded/${art.src}`);
      }
    }
  }

  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// Installation execution
// ---------------------------------------------------------------------------

async function installArtifacts(
  plan: InstallPlan,
  args: CliArgs,
): Promise<InstallResult> {
  const result: InstallResult = {
    installed: [],
    skipped: [],
    merged: [],
    replacedSlugs: [],
    keptSlugs: [],
  };

  const root = packageRoot();

  for (const art of plan.artifacts) {
    const srcPath = join(root, 'skills-embedded', art.src);
    const destExists = existsSync(art.dest);

    // Dry-run: just count, no prompts
    if (args.dryRun) {
      if (destExists && art.merge) {
        result.merged.push(art.dest);
      } else {
        result.installed.push(art.dest);
      }
      continue;
    }

    if (destExists && !args.yes) {
      const action = art.merge ? 'merge' : 'overwrite';
      const choice = await promptOverwrite(art.dest, action);
      if (choice === 'skip') {
        result.skipped.push(art.dest);
        continue;
      }
      if (choice === 'abort') {
        throw new Error('USER_ABORT');
      }
      // choice === 'overwrite'
    } else if (destExists && args.yes) {
      // --yes implies overwrite
    }

    if (art.isDir) {
      mkdirSync(art.dest, { recursive: true });
      cpSync(srcPath, art.dest, { recursive: true });
      result.installed.push(art.dest);
    } else if (art.merge) {
      const { replaced, kept } = mergeModesYaml(srcPath, art.dest);
      result.replacedSlugs.push(...replaced);
      result.keptSlugs.push(...kept);
      result.merged.push(art.dest);
    } else {
      mkdirSync(dirname(art.dest), { recursive: true });
      cpSync(srcPath, art.dest);
      result.installed.push(art.dest);
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Summary report
// ---------------------------------------------------------------------------

function printSummary(result: InstallResult, dryRun: boolean): void {
  console.log('');
  console.log('─'.repeat(50));
  if (dryRun) {
    console.log('DRY RUN SUMMARY (no files were written)');
    console.log('─'.repeat(50));
  } else {
    console.log('INSTALL SUMMARY');
    console.log('─'.repeat(50));
  }

  if (result.installed.length > 0) {
    console.log(`  Installed/updated: ${result.installed.length}`);
  }
  if (result.skipped.length > 0) {
    console.log(`  Skipped: ${result.skipped.length}`);
  }
  if (result.merged.length > 0) {
    console.log(`  Merged: ${result.merged.length}`);
  }
  if (result.replacedSlugs.length > 0) {
    console.log(`  Replaced slugs: ${result.replacedSlugs.join(', ')}`);
  }
  if (result.keptSlugs.length > 0) {
    console.log(`  Kept user slugs: ${result.keptSlugs.join(', ')}`);
  }

  if (
    result.installed.length === 0 &&
    result.skipped.length === 0 &&
    result.merged.length === 0
  ) {
    console.log('  Nothing to install.');
  }

  console.log('─'.repeat(50));
}

// ---------------------------------------------------------------------------
// Public entry point
// ---------------------------------------------------------------------------

export async function runInstall(args: CliArgs): Promise<void> {
  const root = packageRoot();
  const manifest = loadManifest(root);

  // Interactive wizard if no tool specified
  let toolName = args.tool;
  if (!toolName) {
    toolName = await interactiveWizard(manifest, args);
    if (!toolName) {
      console.log('Aborted.');
      process.exit(1);
    }
    args.tool = toolName;
  } else {
    // Validate tool
    if (!manifest.tools[toolName]) {
      const available = Object.keys(manifest.tools).join(', ');
      console.error(`Error: Unknown tool "${toolName}". Available: ${available}`);
      process.exit(1);
    }
  }

  // Build plan
  const plan = buildPlan(args, root);

  if (plan.artifacts.length === 0) {
    console.log('No artifacts to install for the given scope/filter combination.');
    process.exit(0);
  }

  // Print plan
  console.log(planSummary(plan, args));
  console.log('');

  // Execute
  const result = await installArtifacts(plan, args);
  printSummary(result, args.dryRun);
}

// ---------------------------------------------------------------------------
// Interactive wizard
// ---------------------------------------------------------------------------

async function interactiveWizard(
  manifest: Manifest,
  args: CliArgs,
): Promise<string | null> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stderr,
  });

  const tools = Object.keys(manifest.tools);

  // Step 1: Choose tool
  console.error('\nAvailable tools:');
  tools.forEach((t, i) => console.error(`  ${i + 1}. ${t}`));
  console.error('');

  const toolIdx = await ask(rl, `Select tool [1-${tools.length}]: `);
  const idx = parseInt(toolIdx, 10) - 1;
  if (isNaN(idx) || idx < 0 || idx >= tools.length) {
    rl.close();
    return null;
  }
  const tool = tools[idx];

  // Step 2: Choose scope
  console.error('');
  console.error('  1. Global (tool-wide config)');
  console.error('  2. Local (project-level config)');
  const scopeIdx = await ask(rl, 'Select scope [1-2]: ');
  const scope = scopeIdx === '2' ? 'local' : 'global';
  args.scope = scope as 'global' | 'local';

  // Step 3: Confirm
  console.error('');
  console.error(`Installing ${tool} (${args.scope})...`);
  const confirm = await ask(rl, 'Proceed? [Y/n]: ');
  rl.close();

  if (confirm.toLowerCase() === 'n' || confirm.toLowerCase() === 'no') {
    return null;
  }

  return tool;
}

function ask(rl: readline.Interface, question: string): Promise<string> {
  return new Promise((resolve) => {
    rl.question(question, (answer: string) => {
      resolve(answer.trim());
    });
  });
}
