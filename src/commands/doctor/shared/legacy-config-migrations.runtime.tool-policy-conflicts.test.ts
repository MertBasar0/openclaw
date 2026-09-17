// Covers doctor repair for tool policy scopes that set both allow and alsoAllow.
import { describe, expect, it } from "vitest";
import { validateConfigObjectWithPlugins } from "../../../config/validation.js";
import { LEGACY_CONFIG_MIGRATIONS } from "./legacy-config-migrations.js";

// Exercise the registered migration list so the test fails if the repair is never wired in.
function runRegisteredMigrations(raw: unknown): { config: unknown; changes: string[] } {
  const next = structuredClone(raw) as Record<string, unknown>;
  const changes: string[] = [];
  for (const migration of LEGACY_CONFIG_MIGRATIONS) {
    migration.apply(next, changes);
  }
  return { config: next, changes };
}

function isValid(config: unknown): boolean {
  return validateConfigObjectWithPlugins(config, { pluginValidation: "core-only" }).ok === true;
}

describe("tool policy allow/alsoAllow conflict repair", () => {
  it("repairs a top-level tools policy that sets both lists without a profile", () => {
    const raw = { tools: { allow: ["message", "read"], alsoAllow: ["exec"] } };
    expect(isValid(raw)).toBe(false);

    const res = runRegisteredMigrations(raw);

    expect(res.changes).toContain("Merged tools.alsoAllow into tools.allow.");
    expect(isValid(res.config)).toBe(true);
    const tools = (res.config as { tools: { allow: string[]; alsoAllow?: string[] } }).tools;
    expect(tools.allow).toEqual(["message", "read", "exec"]);
    expect(tools).not.toHaveProperty("alsoAllow");
  });

  it("repairs the conflict when the scope already selects the full profile", () => {
    const raw = { tools: { profile: "full", allow: ["message"], alsoAllow: ["exec"] } };
    expect(isValid(raw)).toBe(false);

    const res = runRegisteredMigrations(raw);

    expect(isValid(res.config)).toBe(true);
    expect((res.config as { tools: { allow: string[] } }).tools.allow).toEqual(["message", "exec"]);
  });

  it("repairs per-agent and per-provider tool policy scopes", () => {
    const raw = {
      tools: { byProvider: { openai: { allow: ["message"], alsoAllow: ["exec"] } } },
      agents: { entries: { main: { tools: { allow: ["message"], alsoAllow: ["read"] } } } },
    };
    expect(isValid(raw)).toBe(false);

    const res = runRegisteredMigrations(raw);

    expect(res.changes).toEqual(
      expect.arrayContaining([
        "Merged tools.byProvider.openai.alsoAllow into tools.byProvider.openai.allow.",
        "Merged agents.entries.main.tools.alsoAllow into agents.entries.main.tools.allow.",
      ]),
    );
    expect(isValid(res.config)).toBe(true);
  });

  it("leaves the profile-bound repair to own its scopes", () => {
    const raw = {
      tools: {
        profile: "messaging",
        allow: ["message"],
        alsoAllow: ["exec"],
        exec: { security: "allowlist" },
      },
    };

    const res = runRegisteredMigrations(raw);

    // The profile-bound owner rewrites the scope; this repair must not merge it a second time.
    expect(res.changes).toContain(
      'Set tools.profile to "full" so tools.allow controls explicit configured-section grants directly.',
    );
    expect(
      res.changes.filter((change) => change.startsWith("Merged tools.alsoAllow")),
    ).toHaveLength(1);
    expect(isValid(res.config)).toBe(true);
  });

  it("does not touch a scope that sets only one of the lists", () => {
    const raw = { tools: { alsoAllow: ["exec"] } };

    const res = runRegisteredMigrations(raw);

    expect(res.changes).toEqual([]);
    expect(res.config).toEqual(raw);
  });

  it("leaves plugin-owned config untouched", () => {
    const raw = {
      plugins: {
        entries: { acme: { config: { tools: { allow: ["message"], alsoAllow: ["exec"] } } } },
      },
    };

    const res = runRegisteredMigrations(raw);

    expect(res.changes).toEqual([]);
    expect(res.config).toEqual(raw);
  });
});
