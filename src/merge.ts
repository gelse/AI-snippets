/**
 * YAML merge logic for custom_modes.yaml.
 *
 * When the manifest specifies merge: true for a modes file, the installer
 * parses the existing YAML, replaces entries whose slug matches the generated
 * modes, and keeps the user's other entries.
 *
 * Uses yaml.parseDocument() + String(doc) to preserve sibling top-level keys,
 * leading `---`, comments, and YAML formatting that parse/stringify loses.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import {
  parseDocument,
  YAMLMap,
  YAMLSeq,
  Scalar,
  isMap,
  isSeq,
} from 'yaml';

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
 * - If destPath exists, reads it with parseDocument, replaces matching slugs,
 *   keeps user slugs, preserves sibling keys/comments/--- marker
 * - If destPath doesn't exist, copies generated file to dest
 * - Writes the merged result to destPath
 *
 * @param srcPath - Path to the generated modes file
 * @param destPath - Path to the destination (existing or new) modes file
 * @returns Merge statistics
 */
export function mergeModesYaml(srcPath: string, destPath: string): MergeResult {
  const result: MergeResult = { replaced: [], kept: [] };

  // Parse generated file to get YAML node items
  const genContent = readFileSync(srcPath, 'utf-8');
  const genDoc = parseDocument(genContent);
  const genSeq = getCustomModesSeq(genDoc);
  const genItems = genSeq ? [...genSeq.items] : [];

  if (!existsSync(destPath)) {
    // No existing file — just copy
    mkdirSync(dirname(destPath), { recursive: true });
    writeFileSync(destPath, genContent);
    for (const item of genItems) {
      const slug = getSlugFromItem(item);
      if (slug) result.replaced.push(slug);
    }
    return result;
  }

  // Parse existing file preserving structure (comments, ---, sibling keys)
  const existingContent = readFileSync(destPath, 'utf-8');
  const doc = parseDocument(existingContent);

  // Get or create the customModes sequence in the document
  let seq: YAMLSeq;

  if (doc.contents && isMap(doc.contents)) {
    const existingSeq = doc.contents.get('customModes');
    if (existingSeq && isSeq(existingSeq)) {
      seq = existingSeq;
    } else {
      // customModes key missing — create an empty sequence and set it
      seq = new YAMLSeq();
      doc.contents.set(new Scalar('customModes') as any, seq as any);
    }
  } else {
    // Empty or comment-only file — create a new mapping with customModes
    seq = new YAMLSeq();
    const map = new YAMLMap();
    map.add({ key: new Scalar('customModes'), value: seq } as any);
    doc.contents = map as any;
  }

  // Build slug→index map for existing entries
  const existingSlugs = new Map<string, number>();
  for (let i = 0; i < seq.items.length; i++) {
    const slug = getSlugFromItem(seq.items[i]);
    if (slug) {
      existingSlugs.set(slug, i);
    }
  }

  const generatedSlugs = new Set(
    genItems.map((item) => getSlugFromItem(item)).filter(Boolean) as string[],
  );

  // Remove existing entries whose slugs will be replaced by generated ones
  // (iterate backwards to keep indices stable during splice)
  for (const slug of generatedSlugs) {
    if (existingSlugs.has(slug)) {
      const idx = existingSlugs.get(slug)!;
      seq.items.splice(idx, 1);
      result.replaced.push(slug);
      existingSlugs.delete(slug);
    }
  }

  // Track user entries that were kept (not in generated modes)
  for (const slug of existingSlugs.keys()) {
    result.kept.push(slug);
  }

  // Append generated entries (as YAML nodes, preserving structure)
  for (const item of genItems) {
    seq.items.push(item);
    const slug = getSlugFromItem(item);
    if (slug && !result.replaced.includes(slug)) {
      result.replaced.push(slug);
    }
  }

  mkdirSync(dirname(destPath), { recursive: true });
  writeFileSync(destPath, String(doc));

  return result;
}

/**
 * Get the customModes YAMLSeq from a parsed document.
 */
function getCustomModesSeq(doc: ReturnType<typeof parseDocument>): YAMLSeq | null {
  if (!doc.contents || !isMap(doc.contents)) {
    return null;
  }
  const val = doc.contents.get('customModes');
  return val && isSeq(val) ? val : null;
}

/**
 * Extract the slug string from a YAML node item (a YAMLMap entry in the sequence).
 */
function getSlugFromItem(item: unknown): string | null {
  if (isMap(item)) {
    const slugVal = item.get('slug');
    if (slugVal != null) {
      return String(slugVal);
    }
  }
  return null;
}
