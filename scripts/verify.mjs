/**
 * Verify modes.json integrity and zoo emitter round-trip fidelity.
 *
 * Usage:
 *     node scripts/verify.mjs
 *
 * Exits non-zero with a clear message on failure.
 *
 * Keep in sync with scripts/verify.py.
 */

import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdtempSync, rmSync, readFileSync as readTempFileSync } from 'node:fs';
import { tmpdir } from 'node:os';

import { emitZoo } from './generate.mjs';
import yaml from 'yaml';

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = dirname(dirname(__filename));

// Required keys per mode (excluding optional 'deprecated')
const REQUIRED_MODE_KEYS = new Set([
  'slug',
  'name',
  'description',
  'roleDefinition',
  'whenToUse',
  'customInstructions',
  'groups',
  'source',
]);

const REQUIRED_TOP_KEYS = new Set(['customModes', 'skills']);

// ---------------------------------------------------------------------------
// pyRepr() — match Python repr for sets, lists, dicts (single-quoted)
// ---------------------------------------------------------------------------

function pyRepr(val) {
  if (val === null) return 'None';
  if (val === undefined) return 'None';
  if (typeof val === 'boolean') return val ? 'True' : 'False';
  if (typeof val === 'number') return String(val);
  if (typeof val === 'string') return "'" + val.replace(/\\/g, '\\\\').replace(/'/g, "\\'") + "'";
  if (Array.isArray(val)) return '[' + val.map(v => pyRepr(v)).join(', ') + ']';
  if (val instanceof Set) {
    const items = [...val].map(v => pyRepr(v)).join(', ');
    return '{' + items + '}';
  }
  if (typeof val === 'object') {
    const items = Object.entries(val)
      .map(([k, v]) => pyRepr(k) + ': ' + pyRepr(v))
      .join(', ');
    return '{' + items + '}';
  }
  return String(val);
}

function fail(msg) {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

function ok(msg) {
  console.log(`  OK: ${msg}`);
}

// ---------------------------------------------------------------------------
// (a) Structural validation of modes.json
// ---------------------------------------------------------------------------

function validateStructure() {
  console.log('[a] Structural validation');

  const jsonPath = join(REPO_ROOT, 'modes.json');
  let data;
  try {
    data = JSON.parse(readFileSync(jsonPath, 'utf-8'));
  } catch (exc) {
    if (exc.code === 'ENOENT') {
      fail('modes.json not found');
    }
    fail(`Invalid JSON: ${exc.message}`);
  }

  ok('Valid JSON');

  // Top-level keys
  const dataKeys = new Set(Object.keys(data));
  const missingTop = new Set([...REQUIRED_TOP_KEYS].filter(k => !dataKeys.has(k)));
  if (missingTop.size > 0) {
    fail(`Missing top-level keys: ${pyRepr(missingTop)}`);
  }
  ok(`Top-level keys present: ${JSON.stringify(Object.keys(data).sort())}`);

  // Modes
  const modes = data.customModes;
  if (!Array.isArray(modes) || modes.length === 0) {
    fail('customModes must be a non-empty list');
  }
  ok(`${modes.length} modes found`);

  const slugs = [];
  for (let i = 0; i < modes.length; i++) {
    const mode = modes[i];
    const slug = mode.slug || `<missing at index ${i}>`;
    if (!/^[a-z0-9-]+$/.test(slug)) {
      fail(`Mode slug '${slug}' must match ^[a-z0-9-]+$`);
    }
    slugs.push(slug);

    const modeKeys = new Set(Object.keys(mode));
    const missing = new Set([...REQUIRED_MODE_KEYS].filter(k => !modeKeys.has(k)));
    if (missing.size > 0) {
      fail(`Mode '${slug}' missing keys: ${pyRepr(missing)}`);
    }

    // Groups shape: list of strings or [str, dict]
    const groups = mode.groups || [];
    if (!Array.isArray(groups)) {
      fail(`Mode '${slug}' groups must be a list`);
    }
    for (const g of groups) {
      if (typeof g === 'string') continue;
      if (Array.isArray(g)) {
        if (g.length < 1 || typeof g[0] !== 'string') {
          fail(`Mode '${slug}' nested group must start with a string: ${pyRepr(g)}`);
        }
        if (g.length >= 2 && typeof g[1] !== 'object') {
          fail(`Mode '${slug}' nested group second element must be a dict: ${pyRepr(g)}`);
        }
      } else {
        fail(`Mode '${slug}' group entry must be string or list: ${pyRepr(g)}`);
      }
    }
  }

  ok('All modes have required keys and valid groups shape');

  // Unique slugs
  const seen = new Set();
  for (const s of slugs) {
    if (seen.has(s)) {
      fail(`Duplicate slug: ${s}`);
    }
    seen.add(s);
  }
  ok(`All ${slugs.length} slugs unique`);

  // Skills — accept skills/{name}.md (flat) or skills/{name}/SKILL.md (directory)
  const skills = data.skills || [];
  const validForms = {}; // name -> set of forms seen ("flat", "dir")
  for (const skill of skills) {
    if (!('name' in skill) || !('file' in skill)) {
      fail(`Skill entry missing 'name' or 'file': ${pyRepr(skill)}`);
    }
    const name = skill.name;
    if (!/^[a-z0-9-]+$/.test(name)) {
      fail(`Skill name '${name}' must match ^[a-z0-9-]+$`);
    }

    const flatPath = `skills/${name}.md`;
    const dirPath = `skills/${name}/SKILL.md`;

    let form;
    if (skill.file === flatPath) {
      form = 'flat';
    } else if (skill.file === dirPath) {
      form = 'dir';
    } else {
      fail(
        `Skill 'file' mismatch for '${name}': ` +
        `expected '${flatPath}' or '${dirPath}', ` +
        `got '${skill.file}'`
      );
    }

    if (!(name in validForms)) validForms[name] = new Set();
    validForms[name].add(form);

    const skillPath = join(REPO_ROOT, skill.file);
    try {
      readFileSync(skillPath);
    } catch {
      fail(`Skill file not found: ${skillPath}`);
    }
  }

  // Duplicate skill name check
  const seenNames = [];
  for (const skill of skills) {
    const name = skill.name;
    if (seenNames.includes(name)) {
      fail(`Duplicate skill name: '${name}'`);
    }
    seenNames.push(name);
  }

  // Flat + directory coexistence check
  for (const [name, forms] of Object.entries(validForms)) {
    if (forms.has('flat') && forms.has('dir')) {
      fail(
        `Skill '${name}' has both flat form (skills/${name}.md) ` +
        `and directory form (skills/${name}/SKILL.md) — ` +
        `use only one`
      );
    }
  }

  ok(`All ${skills.length} skill files exist; no duplicates or coexistence conflicts`);

  return data;
}

// ---------------------------------------------------------------------------
// (b) Round-trip: emit to zoo, load back, deep-compare
// ---------------------------------------------------------------------------

function roundTrip(data) {
  console.log('[b] Round-trip verification');

  const tmpDir = mkdtempSync(join(tmpdir(), 'verify-'));
  try {
    emitZoo(data, tmpDir);

    const roomodesPath = join(tmpDir, 'zoo', '.roomodes');
    let emitted;
    try {
      emitted = yaml.parse(readTempFileSync(roomodesPath, 'utf-8'));
    } catch {
      fail('Zoo emitter did not create .roomodes');
    }

    if (!emitted || !('customModes' in emitted)) {
      fail('Emitted .roomodes missing \'customModes\' key');
    }

    const emittedModes = emitted.customModes;
    const jsonModes = data.customModes;

    if (emittedModes.length !== jsonModes.length) {
      fail(
        `Mode count mismatch: emitted ${emittedModes.length} vs ` +
        `JSON ${jsonModes.length}`
      );
    }

    for (let i = 0; i < emittedModes.length; i++) {
      const em = emittedModes[i];
      const jm = jsonModes[i];
      const slug = jm.slug || `<index ${i}>`;

      // Strip 'deprecated' from JSON mode for comparison
      const jmClean = {};
      for (const [k, v] of Object.entries(jm)) {
        if (k !== 'deprecated') jmClean[k] = v;
      }

      const emKeys = new Set(Object.keys(em));
      const jmKeys = new Set(Object.keys(jmClean));

      if (emKeys.size !== jmKeys.size ||
          ![...emKeys].every(k => jmKeys.has(k))) {
        fail(
          `Mode '${slug}' key mismatch:\n` +
          `  emitted keys: ${JSON.stringify([...emKeys].sort())}\n` +
          `  expected keys: ${JSON.stringify([...jmKeys].sort())}`
        );
      }

      for (const [key, expected] of Object.entries(jmClean)) {
        if (JSON.stringify(em[key]) !== JSON.stringify(expected)) {
          fail(
            `Mode '${slug}' value mismatch for key '${key}':\n` +
            `  emitted: ${pyRepr(em[key])}\n` +
            `  expected: ${pyRepr(expected)}`
          );
        }
      }
    }

    ok(`All ${emittedModes.length} modes round-trip match (ignoring 'deprecated')`);
  } finally {
    rmSync(tmpDir, { recursive: true, force: true });
  }
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

function main() {
  const data = validateStructure();
  roundTrip(data);
  console.log('\nAll checks passed.');
}

main();
