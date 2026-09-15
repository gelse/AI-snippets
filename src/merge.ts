/**
 * YAML merge logic for custom_modes.yaml.
 *
 * When the manifest specifies merge: true for a modes file, the installer
 * parses the existing YAML, replaces entries whose slug matches the generated
 * modes, and keeps the user's other entries.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { parse as parseYaml, stringify as stringifyYaml } from 'yaml';

export interface MergeResult {
  /** Slugs from the generated modes that replaced existing entries */
  replaced: string[];
  /** Slugs from the user's file that were kept (not in generated modes) */
  kept: string[];
}

/**
 * Merge a generated modes YAML file into an existing one.
 *
 * - Reads generated modes from srcPath
 * - If destPath exists, reads it, replaces matching slugs, keeps user slugs
 * - If destPath doesn't exist, copies generated file to dest
 * - Writes the merged result to destPath
 * - Preserves YAML block scalar formatting via the yaml library
 *
 * @param srcPath - Path to the generated modes file
 * @param destPath - Path to the destination (existing or new) modes file
 * @returns Merge statistics
 */
export function mergeModesYaml(srcPath: string, destPath: string): MergeResult {
  const result: MergeResult = { replaced: [], kept: [] };

  const generated = readModesFile(srcPath);

  if (!existsSync(destPath)) {
    // No existing file — just copy
    mkdirSync(dirname(destPath), { recursive: true });
    writeFileSync(destPath, readFileSync(srcPath, 'utf-8'));
    result.replaced = generated.map((m) => m.slug);
    return result;
  }

  const existing = readModesFile(destPath);
  const generatedSlugs = new Set(generated.map((m) => m.slug));

  // Build merged list: start with existing, replace matching slugs
  const merged = new Map<string, Record<string, unknown>>();

  // Add existing entries first
  for (const entry of existing) {
    if (generatedSlugs.has(entry.slug)) {
      // Will be replaced by generated version
      continue;
    }
    merged.set(entry.slug, entry);
    result.kept.push(entry.slug);
  }

  // Add/replace with generated entries (preserving generated order)
  for (const entry of generated) {
    merged.set(entry.slug, entry);
    if (result.kept.includes(entry.slug)) {
      // This slug existed in user's file and was replaced
      result.kept = result.kept.filter((s) => s !== entry.slug);
      result.replaced.push(entry.slug);
    } else {
      result.replaced.push(entry.slug);
    }
  }

  // Write merged result preserving the customModes structure
  const mergedDoc = { customModes: Array.from(merged.values()) };
  mkdirSync(dirname(destPath), { recursive: true });
  writeFileSync(destPath, stringifyYaml(mergedDoc));

  return result;
}

interface ModeEntry {
  slug: string;
  [key: string]: unknown;
}

function readModesFile(filePath: string): ModeEntry[] {
  const content = readFileSync(filePath, 'utf-8');
  const doc = parseYaml(content) as Record<string, unknown>;
  const modes = doc['customModes'];
  if (!Array.isArray(modes)) {
    return [];
  }
  return modes.map((m: Record<string, unknown>) => ({
    slug: String(m['slug'] ?? ''),
    ...m,
  }));
}
