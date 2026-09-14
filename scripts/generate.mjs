/**
 * Generate mode/skill artifacts for Zoo Code, Kilo Code, OpenCode, and Claude Code.
 *
 * Usage:
 *     node scripts/generate.mjs {zoo|kilo|opencode|claude} [--out output]
 *
 * Keep in sync with scripts/generate.py.
 */

import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync, copyFileSync, statSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import yaml from 'yaml';

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = dirname(dirname(__filename));
const _SAFE_FILENAME_RE = /^[a-z0-9._-]+$/;

// ---------------------------------------------------------------------------
// YAML helpers — use yaml package (stringify for dump)

function loadModes() {
  const p = join(REPO_ROOT, 'modes.json');
  return JSON.parse(readFileSync(p, 'utf-8'));
}

function loadSkillContent(skillFile) {
  const p = join(REPO_ROOT, skillFile);
  return readFileSync(p, 'utf-8');
}

function copySkillExtraFiles(skill, destDir) {
  const name = skill.name;
  const srcDir = join(REPO_ROOT, 'skills', name);
  if (skill.file !== `skills/${name}/SKILL.md`) return;
  if (!existsSync(srcDir) || !statSync(srcDir).isDirectory()) return;

  const entries = readdirSync(srcDir);
  for (const entry of entries.sort()) {
    if (entry === 'SKILL.md') continue;
    const full = join(srcDir, entry);
    if (!statSync(full).isFile()) continue;
    // Skip dotfiles and unsafe filenames
    if (entry.startsWith('.') || !_SAFE_FILENAME_RE.test(entry)) continue;
    mkdirSync(destDir, { recursive: true });
    copyFileSync(full, join(destDir, entry));
  }
}

// ---------------------------------------------------------------------------
// Frontmatter helpers
// ---------------------------------------------------------------------------

function findFrontmatterEnd(content) {
  const idx = content.indexOf('---', 3);
  if (idx === -1) {
    console.error("ERROR: Frontmatter starts with '---' but closing '---' not found.");
    process.exit(1);
  }
  return idx;
}

function ensureSkillFrontmatter(content, skillName) {
  if (content.startsWith('---\n')) {
    const end = findFrontmatterEnd(content);
    let frontmatter = content.substring(3, end).trim();
    let body = content.substring(end + 3);
    if (body.startsWith('\n')) body = body.substring(1);

    const hasName = /^name:/m.test(frontmatter);
    const hasDesc = /^description:/m.test(frontmatter);

    let additions = '';
    if (!hasName) additions += `\nname: ${skillName}`;
    if (!hasDesc) additions += `\ndescription: ${skillName}`;

    if (additions) {
      frontmatter += additions;
      return `---\n${frontmatter}\n---\n${body}`;
    }
    return content;
  } else {
    const fm = `name: ${skillName}\ndescription: ${skillName}`;
    return `---\n${fm}\n---\n${content}`;
  }
}

function extractSkillDescription(content) {
  if (content.startsWith('---\n')) {
    const end = findFrontmatterEnd(content);
    const fm = content.substring(3, end);
    const m = fm.match(/^description:\s*(.+)$/m);
    if (m) return m[1].trim();
  }
  return '';
}

function extractBodyAfterFrontmatter(content) {
  if (content.startsWith('---\n')) {
    const end = findFrontmatterEnd(content);
    let body = content.substring(end + 3);
    if (body.startsWith('\n')) body = body.substring(1);
    return body;
  }
  return content;
}

function hasEditGroup(groups) {
  for (const g of groups) {
    if (g === 'edit') return true;
    if (Array.isArray(g) && g.length > 0 && g[0] === 'edit') return true;
  }
  return false;
}

function modeToDict(mode) {
  const result = {};
  for (const [k, v] of Object.entries(mode)) {
    if (k !== 'deprecated') result[k] = v;
  }
  return result;
}

// ---------------------------------------------------------------------------
// Zoo Code emitter
// ---------------------------------------------------------------------------

export function emitZoo(data, outDir) {
  const zooDir = join(outDir, 'zoo');
  rmSync(zooDir, { recursive: true, force: true });
  mkdirSync(zooDir, { recursive: true });

  const customModes = data.customModes.map(m => modeToDict(m));
  const roomodes = { customModes };

  writeFileSync(join(zooDir, '.roomodes'), yaml.stringify(roomodes));

  const skillsDir = join(zooDir, 'skills');
  mkdirSync(skillsDir, { recursive: true });
  for (const skill of data.skills) {
    let content = loadSkillContent(skill.file);
    content = ensureSkillFrontmatter(content, skill.name);
    writeFileSync(join(skillsDir, `${skill.name}.md`), content);
    // Companion files for directory-form skills go in skills/<name>/
    copySkillExtraFiles(skill, join(skillsDir, skill.name));
  }

  console.log(`  zoo: ${join(zooDir, '.roomodes')} + ${data.skills.length} skills`);
}

// ---------------------------------------------------------------------------
// Kilo Code emitter
// ---------------------------------------------------------------------------

function emitKilo(data, outDir) {
  const kiloDir = join(outDir, 'kilo');
  rmSync(kiloDir, { recursive: true, force: true });
  mkdirSync(kiloDir, { recursive: true });

  const customModes = data.customModes.map(m => modeToDict(m));
  const kilocodemodes = { customModes };

  writeFileSync(join(kiloDir, '.kilocodemodes'), yaml.stringify(kilocodemodes));

  const skillsDir = join(kiloDir, 'skills');
  mkdirSync(skillsDir, { recursive: true });
  for (const skill of data.skills) {
    let content = loadSkillContent(skill.file);
    content = ensureSkillFrontmatter(content, skill.name);
    writeFileSync(join(skillsDir, `${skill.name}.md`), content);
    // Companion files for directory-form skills go in skills/<name>/
    copySkillExtraFiles(skill, join(skillsDir, skill.name));
  }

  console.log(`  kilo: ${join(kiloDir, '.kilocodemodes')} + ${data.skills.length} skills`);
}

// ---------------------------------------------------------------------------
// OpenCode emitter
// ---------------------------------------------------------------------------

function emitOpencode(data, outDir) {
  const ocDir = join(outDir, 'opencode');
  rmSync(ocDir, { recursive: true, force: true });
  const agentsDir = join(ocDir, 'agents');
  mkdirSync(agentsDir, { recursive: true });

  let count = 0;
  for (const mode of data.customModes) {
    if (mode.deprecated) continue;

    const { slug, description: desc, whenToUse: when, roleDefinition: role } = mode;
    const instructions = mode.customInstructions || '';
    const groups = mode.groups || [];

    const frontmatter = {
      description: `${desc} (Use when: ${when})`,
      mode: 'subagent',
    };

    if (!hasEditGroup(groups)) {
      frontmatter.permission = { edit: 'deny' };
    }

    const body = instructions ? `${role}\n\n${instructions}` : role;

    const fmStr = yaml.stringify(frontmatter);
    const content = `---\n${fmStr}---\n${body}\n`;

    writeFileSync(join(agentsDir, `${slug}.md`), content);
    count++;
  }

  const skillDir = join(ocDir, 'skill');
  mkdirSync(skillDir, { recursive: true });
  for (const skill of data.skills) {
    const raw = loadSkillContent(skill.file);
    const skillDesc = extractSkillDescription(raw);
    const body = extractBodyAfterFrontmatter(raw);

    const frontmatter = { name: skill.name };
    if (skillDesc) frontmatter.description = skillDesc;

    const fmStr = yaml.stringify(frontmatter);
    writeFileSync(
      join(skillDir, `${skill.name}.md`),
      `---\n${fmStr}---\n${body}\n`
    );
    // Companion files for directory-form skills go in skill/<name>/
    copySkillExtraFiles(skill, join(skillDir, skill.name));
  }

  console.log(`  opencode: ${count} agents + ${data.skills.length} skills in ${ocDir}`);
}

// ---------------------------------------------------------------------------
// Claude Code emitter
// ---------------------------------------------------------------------------

function emitClaude(data, outDir) {
  const claudeDir = join(outDir, 'claude');
  rmSync(claudeDir, { recursive: true, force: true });
  const agentsDir = join(claudeDir, 'agents');
  mkdirSync(agentsDir, { recursive: true });

  let count = 0;
  for (const mode of data.customModes) {
    if (mode.deprecated) continue;

    const { slug, description: desc, whenToUse: when, roleDefinition: role } = mode;
    const instructions = mode.customInstructions || '';

    const frontmatter = {
      name: slug,
      description: `${desc} (Use when: ${when})`,
    };

    const body = instructions ? `${role}\n\n${instructions}` : role;

    const fmStr = yaml.stringify(frontmatter);
    const content = `---\n${fmStr}---\n${body}\n`;

    writeFileSync(join(agentsDir, `${slug}.md`), content);
    count++;
  }

  for (const skill of data.skills) {
    const skillDir = join(claudeDir, 'skills', skill.name);
    mkdirSync(skillDir, { recursive: true });

    const raw = loadSkillContent(skill.file);
    const skillDesc = extractSkillDescription(raw);
    const body = extractBodyAfterFrontmatter(raw);

    const frontmatter = { name: skill.name };
    if (skillDesc) frontmatter.description = skillDesc;

    const fmStr = yaml.stringify(frontmatter);
    writeFileSync(
      join(skillDir, 'SKILL.md'),
      `---\n${fmStr}---\n${body}\n`
    );
    // Companion files for directory-form skills go beside SKILL.md
    copySkillExtraFiles(skill, skillDir);
  }

  console.log(`  claude: ${count} agents + ${data.skills.length} skills in ${claudeDir}`);
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

const EMITTERS = {
  zoo: emitZoo,
  kilo: emitKilo,
  opencode: emitOpencode,
  claude: emitClaude,
};

function main() {
  const args = process.argv.slice(2);

  // Parse arguments
  let tool = null;
  let outDir = join(REPO_ROOT, 'output');

  const positional = [];
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--out' && i + 1 < args.length) {
      outDir = join(REPO_ROOT, args[++i]);
    } else {
      positional.push(args[i]);
    }
  }

  if (positional.length !== 1 || !EMITTERS[positional[0]]) {
    console.error(
      `usage: node scripts/generate.mjs {${Object.keys(EMITTERS).join('|')}} [--out output]`
    );
    process.exit(2);
  }

  tool = positional[0];
  const data = loadModes();

  // Defense-in-depth: validate all skill names before processing
  for (const skill of data.skills) {
    if (!/^[a-z0-9-]+$/.test(skill.name)) {
      console.error(
        `ERROR: Invalid skill name '${skill.name}' — must match ^[a-z0-9-]+$`
      );
      process.exit(1);
    }
  }

  console.log(`Generating ${tool} artifacts...`);
  EMITTERS[tool](data, outDir);
  console.log('Done.');
}

// Run CLI only when executed directly (not when imported by verify.mjs)
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main();
}
