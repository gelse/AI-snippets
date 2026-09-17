/**
 * Interactive prompts for the installer CLI.
 *
 * Uses readline to ask the user how to handle file collisions.
 * Handles piped/stdin by buffering all incoming lines so they are not lost
 * between sequential question() calls.
 */

import * as readline from 'node:readline';

export type PromptChoice = 'overwrite' | 'skip' | 'abort';

/**
 * Create a shared readline context that buffers all incoming lines.
 * This ensures piped stdin answers are not lost between sequential prompts.
 */
export interface ReadlineContext {
  rl: readline.Interface;
  /** Ask a question, consuming the next buffered line or waiting for one. */
  ask: (question: string) => Promise<string>;
  /** Clean up — close the underlying interface. */
  close: () => void;
}

export function createReadlineContext(): ReadlineContext {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stderr,
  });

  // Buffer for lines that arrive between question() calls
  const lineBuffer: string[] = [];
  // Queue of pending ask() callers waiting for a line
  const waiters: Array<(line: string) => void> = [];
  let closed = false;

  rl.on('line', (line: string) => {
    if (waiters.length > 0) {
      const waiter = waiters.shift()!;
      waiter(line);
    } else {
      lineBuffer.push(line);
    }
  });

  rl.on('close', () => {
    closed = true;
    // Resolve all pending waiters with empty string
    while (waiters.length > 0) {
      const waiter = waiters.shift()!;
      waiter('');
    }
  });

  function ask(question: string): Promise<string> {
    // Print the prompt to stderr (matching readline.question behavior)
    process.stderr.write(question);
    return new Promise<string>((resolve) => {
      if (lineBuffer.length > 0) {
        // Already have a buffered line — use it immediately
        resolve(lineBuffer.shift()!.trim());
      } else if (closed) {
        // Interface already closed — return empty
        resolve('');
      } else {
        // Wait for next line from stdin
        waiters.push((line: string) => {
          resolve(line.trim());
        });
      }
    });
  }

  function close(): void {
    rl.close();
  }

  return { rl, ask, close };
}

/**
 * Prompt the user when a destination file already exists.
 *
 * @param destPath - The path of the existing file
 * @param action - The action that would be taken (overwrite/merge)
 * @param ctx - A shared ReadlineContext (caller manages lifecycle)
 * @returns The user's choice
 * @throws Error on EOF/empty input in non-interactive mode
 */
export async function promptOverwrite(
  destPath: string,
  action: 'overwrite' | 'merge',
  ctx: ReadlineContext,
): Promise<PromptChoice> {
  const verb = action === 'merge' ? 'Merge into' : 'Overwrite';
  console.error(`\n  Destination exists: ${destPath}`);
  console.error(`  ${verb}?`);

  const answer = await ctx.ask('  [o]verwrite / [s]kip / [a]bort: ');

  const normalized = answer.toLowerCase();
  if (normalized === 'a' || normalized === 'abort') {
    return 'abort';
  }
  if (normalized === 's' || normalized === 'skip') {
    return 'skip';
  }
  // Empty/EOF: non-TTY → error, TTY → default to overwrite
  if (normalized === '') {
    if (!process.stdin.isTTY) {
      throw new Error(
        'Unexpected end of input — cannot prompt for overwrite in non-interactive mode. Use --yes or provide answers via stdin.',
      );
    }
    return 'overwrite';
  }
  // Default: overwrite
  return 'overwrite';
}
