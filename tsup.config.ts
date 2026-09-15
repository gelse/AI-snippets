import { defineConfig } from 'tsup';

export default defineConfig([
  {
    entry: { cli: 'src/cli.ts' },
    format: ['esm'],
    target: 'node18',
    outDir: 'dist',
    bundle: true,
    splitting: false,
    clean: true,
  },
  {
    entry: { release: 'skills/release/release.ts' },
    format: ['esm'],
    target: 'node18',
    outDir: 'dist',
    bundle: false,
    clean: false,
  },
]);
