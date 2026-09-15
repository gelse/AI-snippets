/**
 * Interactive prompts for the installer CLI.
 *
 * Uses readline to ask the user how to handle file collisions.
 */

import * as readline from 'node:readline';

export type PromptChoice = 'overwrite' | 'skip' | 'abort';

/**
 * Prompt the user when a destination file already exists.
 *
 * @param destPath - The path of the existing file
 * @param action - The action that would be taken (overwrite/merge)
 * @returns The user's choice
 */
export async function promptOverwrite(
  destPath: string,
  action: 'overwrite' | 'merge',
): Promise<PromptChoice> {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stderr,
  });

  const verb = action === 'merge' ? 'Merge into' : 'Overwrite';
  console.error(`\n  Destination exists: ${destPath}`);
  console.error(`  ${verb}?`);

  try {
    const answer = await new Promise<string>((resolve) => {
      rl.question('  [o]verwrite / [s]kip / [a]bort: ', resolve);
    });

    const normalized = answer.trim().toLowerCase();
    if (normalized === 'a' || normalized === 'abort') {
      return 'abort';
    }
    if (normalized === 's' || normalized === 'skip') {
      return 'skip';
    }
    // Default: overwrite
    return 'overwrite';
  } finally {
    rl.close();
  }
}
