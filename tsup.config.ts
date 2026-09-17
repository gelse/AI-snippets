import { defineConfig } from 'tsup';

export default defineConfig([
  {
    entry: { cli: 'src/cli.ts' },
    format: ['cjs'],
    outExtension: () => ({ js: '.cjs' }),
    target: 'node18',
    outDir: 'dist',
    bundle: true,
    splitting: false,
    clean: true,
    noExternal: ['yaml'],
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
