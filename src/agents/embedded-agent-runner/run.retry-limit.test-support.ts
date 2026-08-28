import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import { makeAttemptResult } from "./run.overflow-compaction.fixture.js";
import {
  mockedBuildAgentRuntimePlan,
  mockedRunEmbeddedAttempt,
  overflowBaseRunParams,
  resetSharedRunIntegrationHarnessMocks,
} from "./run.overflow-compaction.harness.js";
import { loadSharedRunIntegrationHarness } from "./run.shared-integration-harness.test-support.js";

let runEmbeddedAgent: Awaited<ReturnType<typeof loadSharedRunIntegrationHarness>>;

describe("runEmbeddedAgent retry-limit metadata", () => {
  beforeAll(async () => {
    runEmbeddedAgent = await loadSharedRunIntegrationHarness();
  });

  beforeEach(() => {
    resetSharedRunIntegrationHarnessMocks();
  });

  it("reports the latest physical attempt after ordinary retry-budget exhaustion", async () => {
    let physicalAttempt = 0;
    mockedBuildAgentRuntimePlan.mockImplementation(() => {
      physicalAttempt += 1;
      const isLatestAttempt = physicalAttempt === 32;
      return {
        auth: {
          authProfileProviderForAuth: isLatestAttempt ? "physical-provider" : "stale-provider",
          providerForAuth: isLatestAttempt ? "physical-provider" : "stale-provider",
        },
        observability: {
          resolvedRef: isLatestAttempt
            ? "physical-provider/physical-model"
            : "stale-provider/stale-model",
          provider: isLatestAttempt ? "physical-provider" : "stale-provider",
          modelId: isLatestAttempt ? "physical-model" : "stale-model",
          harnessId: "codex",
          credentialSource: isLatestAttempt
            ? {
                kind: "direct",
                evidence: "environment",
                authorization: "ambient",
              }
            : { kind: "profile" },
        },
      } as never;
    });
    mockedRunEmbeddedAttempt.mockResolvedValue(
      makeAttemptResult({
        preflightRecovery: {
          route: "truncate_tool_results_only",
          source: "mid-turn",
          handled: true,
          truncatedCount: 0,
        },
      }),
    );

    const result = await runEmbeddedAgent({
      ...overflowBaseRunParams,
      runId: "run-retry-limit-physical-attempt-meta",
    });

    expect(mockedRunEmbeddedAttempt).toHaveBeenCalledTimes(32);
    expect(result.meta.error?.kind).toBe("retry_limit");
    expect(result.meta.agentMeta).toMatchObject({
      provider: "physical-provider",
      model: "physical-model",
      credentialSource: {
        kind: "direct",
        evidence: "environment",
        authorization: "ambient",
      },
    });
    expect(Object.keys(result.meta.agentMeta?.credentialSource ?? {}).toSorted()).toEqual([
      "authorization",
      "evidence",
      "kind",
    ]);
  });
});
