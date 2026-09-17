// Repairs tool policy scopes that set both allow and alsoAllow, which config validation rejects.
import { isRecord } from "@openclaw/normalization-core/record-coerce";
import { uniqueStrings } from "@openclaw/normalization-core/string-normalization";
import {
  defineLegacyConfigMigration,
  type LegacyConfigMigrationSpec,
} from "../../../config/legacy.shared.js";
import { isToolPolicyPath, TOOL_POLICY_ROOTS } from "./legacy-tool-policy-scopes.js";

function readGrantList(
  scope: Record<string, unknown>,
  key: "allow" | "alsoAllow",
): string[] | null {
  const list = scope[key];
  if (!Array.isArray(list) || list.length === 0) {
    return null;
  }
  return list.every((entry) => typeof entry === "string") ? (list as string[]) : null;
}

function visitConflictingToolPolicies(
  value: unknown,
  path: string[],
  merge: boolean,
  matchedPaths: string[],
): void {
  if (Array.isArray(value)) {
    for (const [index, entry] of value.entries()) {
      visitConflictingToolPolicies(entry, [...path, String(index)], merge, matchedPaths);
    }
    return;
  }
  if (!isRecord(value)) {
    return;
  }
  if (isToolPolicyPath(path)) {
    const allow = readGrantList(value, "allow");
    const alsoAllow = readGrantList(value, "alsoAllow");
    if (allow && alsoAllow) {
      matchedPaths.push(path.join("."));
      if (merge) {
        value.allow = uniqueStrings([...allow, ...alsoAllow]);
        delete value.alsoAllow;
      }
    }
  }
  for (const [key, entry] of Object.entries(value)) {
    visitConflictingToolPolicies(entry, [...path, key], merge, matchedPaths);
  }
}

/** Reports tool policy scopes that set both allow and alsoAllow, without changing them. */
export function findConflictingToolPolicyPaths(value: unknown, path: string[] = []): string[] {
  const matchedPaths: string[] = [];
  visitConflictingToolPolicies(value, path, false, matchedPaths);
  return matchedPaths;
}

export const LEGACY_CONFIG_MIGRATIONS_RUNTIME_TOOL_POLICY_CONFLICTS: LegacyConfigMigrationSpec[] = [
  defineLegacyConfigMigration({
    id: "tools.allow-also-allow-conflict",
    describe: "Merge tool policy alsoAllow grants into allow when a scope sets both",
    legacyRules: TOOL_POLICY_ROOTS.map((root) => ({
      path: [root],
      message:
        'Tool policy sets both allow and alsoAllow in the same scope; run "openclaw doctor --fix" to merge alsoAllow into allow.',
      match: (value) => findConflictingToolPolicyPaths(value, [root]).length > 0,
    })),
    apply: (raw, changes) => {
      if (!isRecord(raw)) {
        return;
      }
      const merged: string[] = [];
      for (const root of TOOL_POLICY_ROOTS) {
        visitConflictingToolPolicies(raw[root], [root], true, merged);
      }
      for (const path of merged) {
        changes.push(`Merged ${path}.alsoAllow into ${path}.allow.`);
      }
    },
  }),
];
