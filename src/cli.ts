#!/usr/bin/env node
/**
 * @gelse/ai-snippets installer CLI.
 *
 * Reads the bundled install-manifest.json and embedded skills tree,
 * then installs generated artifacts for the chosen tool.
 *
 * Usage:
 *   ai-snippets install <tool> [--global|--local] [--skills-only|--agents-only] [--dry-run] [--yes]
 *   ai-snippets                          (interactive wizard)
 */

import { runInstall } from './installer.js';

// ---------------------------------------------------------------------------
// Argument parsing (zero-dep)
// ---------------------------------------------------------------------------

interface CliArgs {
  command?: string;
  tool?: string;
  scope: 'global' | 'local';
  filter: 'all' | 'skills-only' | 'agents-only';
  dryRun: boolean;
  yes: boolean;
}

function parseArgs(argv: string[]): CliArgs {
  const args = argv.slice(2); // skip node, script
  const result: CliArgs = {
    scope: 'global',
    filter: 'all',
    dryRun: false,
    yes: false,
  };

  let i = 0;
  // First positional arg may be "install" (the subcommand)
  if (i < args.length && args[i] === 'install') {
    result.command = 'install';
    i++;
  }

  // Next positional arg is the tool name (if not a flag)
  if (i < args.length && !args[i].startsWith('-')) {
    result.tool = args[i];
    i++;
  }

  // Remaining args are flags
  for (; i < args.length; i++) {
    const arg = args[i];
    switch (arg) {
      case '--global':
        result.scope = 'global';
        break;
      case '--local':
        result.scope = 'local';
        break;
      case '--skills-only':
        result.filter = 'skills-only';
        break;
      case '--agents-only':
        result.filter = 'agents-only';
        break;
      case '--dry-run':
        result.dryRun = true;
        break;
      case '--yes':
      case '-y':
        result.yes = true;
        break;
      case '--help':
      case '-h':
        printHelp();
        process.exit(0);
      default:
        console.error(`Unknown argument: ${arg}`);
        printHelp();
        process.exit(1);
    }
  }

  return result;
}

function printHelp(): void {
  console.log(`Usage: ai-snippets [install] <tool> [options]

Install generated skills and agent modes for an AI coding tool.

Tools: zoo, kilo, opencode, claude

Options:
  --global          Install to global tool config directory (default)
  --local           Install to local (project) tool config directory
  --skills-only     Install only skills (skip agent modes)
  --agents-only     Install only agent modes (skip skills)
  --dry-run         Show what would be installed without writing files
  --yes, -y         Overwrite existing files without prompting
  -h, --help        Show this help message

If no tool is specified, an interactive wizard will guide you.

Examples:
  ai-snippets install zoo --global
  ai-snippets install claude --local --dry-run
  ai-snippets install opencode --global --skills-only --yes`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const args = parseArgs(process.argv);

  // No tool specified → interactive wizard will be handled by runInstall
  await runInstall(args);
}

main().catch((err: unknown) => {
  if (err instanceof Error && err.message === 'USER_ABORT') {
    process.exit(1);
  }
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(1);
});
