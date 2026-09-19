#!/usr/bin/env node
/**
 * Stage embedded assets into skills-embedded/ for npm packaging.
 *
 * Copies the generated output/ tree and install-manifest.json into
 * skills-embedded/ so the published package contains everything needed
 * to install without the repo's output/ directory.
 */

import { cpSync, mkdirSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');
const outputDir = resolve(root, 'output');
const embeddedDir = resolve(root, 'skills-embedded');

if (!existsSync(outputDir)) {
  console.error('ERROR: output/ directory does not exist. Run the generator first.');
  process.exit(1);
}

// Ensure skills-embedded/ exists, then copy output/ into it
mkdirSync(embeddedDir, { recursive: true });

// Copy the entire output/ tree into skills-embedded/
cpSync(outputDir, embeddedDir, { recursive: true });

console.log('Staged output/ → skills-embedded/');
