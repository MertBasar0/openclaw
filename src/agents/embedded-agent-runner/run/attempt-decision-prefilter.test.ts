import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearRuntimeConfigSnapshot,
  setRuntimeConfigSnapshot,
} from "../../../config/runtime-snapshot.js";
import type { OpenClawConfig } from "../../../config/types.openclaw.js";
import { AgentDefaultsBaseSchema } from "../../../config/zod-schema.agent-defaults-base.js";
import type { evaluateDecisionInRegistry } from "../../../decisions/runtime.js";
import type { DecisionOutcome } from "../../../decisions/types.js";
import { evaluateAttemptDecisionToolPrefilter } from "./attempt-decision-prefilter.js";

const mocks = vi.hoisted(() => ({ evaluate: vi.fn<typeof evaluateDecisionInRegistry>() }));
vi.mock("../../../decisions/runtime.js", () => ({ evaluateDecisionInRegistry: mocks.evaluate }));
vi.mock("../../../plugins/runtime/gateway-request-scope.js", () => ({
  getPluginRegistryForContext: () => null,
}));

function config(optIn = true, model: string | undefined = "fixture/model"): OpenClawConfig {
  return {
    agents: {
      defaults: AgentDefaultsBaseSchema.parse({
        experimental: { decisionAssistance: optIn },
        decisionModel: model,
      }),
    },
  };
}
const answer = (probabilityTrue = 0.1): DecisionOutcome => ({
  status: "ok",
  provenance: { providerId: "fixture", rubricVersion: "3", runtimeGeneration: "test" },
  result: { model: "model", answers: { any_tool_needed: { type: "boolean", probabilityTrue } } },
});
function params(cfg = config()) {
  return {
    config: cfg,
    agentId: "main",
    supportsTurnScopedToolRestrictions: true,
    assertActive: vi.fn(),
    userMessage: "Hello",
    signal: new AbortController().signal,
  };
}
beforeEach(() => {
  mocks.evaluate.mockReset().mockResolvedValue(answer());
});
afterEach(clearRuntimeConfigSnapshot);

describe("Decision tool prefilter admission", () => {
  it.each([
    [false, undefined],
    [false, "fixture/model"],
    [true, undefined],
  ] as const)("does not dispatch with opt-in %s and model %s", async (enabled, model) => {
    const cfg = config(enabled);
    cfg.agents!.defaults!.decisionModel = model;
    expect(await evaluateAttemptDecisionToolPrefilter(params(cfg))).toEqual({
      shouldPruneTools: false,
    });
    expect(mocks.evaluate).not.toHaveBeenCalled();
  });
  it.each([false, undefined])(
    "does not dispatch without explicit harness support %s",
    async (support) => {
      expect(
        await evaluateAttemptDecisionToolPrefilter({
          ...params(),
          supportsTurnScopedToolRestrictions: support,
        }),
      ).toEqual({ shouldPruneTools: false });
      expect(mocks.evaluate).not.toHaveBeenCalled();
    },
  );
  it("preserves explicit empty agent override and requires the owning agent", async () => {
    const cfg = config();
    cfg.agents!.entries = { quiet: { decisionModel: "" } };
    for (const agentId of ["quiet", ""]) {
      expect(await evaluateAttemptDecisionToolPrefilter({ ...params(cfg), agentId })).toEqual({
        shouldPruneTools: false,
      });
    }
    expect(mocks.evaluate).not.toHaveBeenCalled();
  });
  it("submits the actual Boolean rubric, trusted owner, signal and runtime deadline", async () => {
    const input = params();
    expect(await evaluateAttemptDecisionToolPrefilter(input)).toMatchObject({
      shouldPruneTools: true,
    });
    expect(mocks.evaluate).toHaveBeenCalledWith(
      {
        state: { userMessage: "Hello" },
        questions: {
          any_tool_needed: {
            type: "boolean",
            criteria: { true: expect.any(String), false: expect.any(String) },
          },
        },
      },
      {
        agentId: "main",
        purpose: "tool-prefilter.semantic-gate",
        rubricVersion: "3",
        timeoutMs: 500,
        signal: input.signal,
      },
      null,
      input.config,
    );
    expect(input.assertActive).toHaveBeenCalledTimes(2);
  });
  it.each([0.35, 0.9])("retains tools at probability %s", async (probability) => {
    mocks.evaluate.mockResolvedValue(answer(probability));
    expect(await evaluateAttemptDecisionToolPrefilter(params())).toEqual({
      shouldPruneTools: false,
    });
  });
  it.each(["deadline", "not-configured", "transport"] as const)(
    "skips ordinary %s unavailability",
    async (reason) => {
      mocks.evaluate.mockResolvedValue({ status: "unavailable", reason });
      expect(await evaluateAttemptDecisionToolPrefilter(params())).toEqual({
        shouldPruneTools: false,
      });
    },
  );
  it("never classifies a named explicit decision_evaluate request", async () => {
    expect(
      await evaluateAttemptDecisionToolPrefilter({
        ...params(),
        userMessage: "Use decision_evaluate on Hello",
      }),
    ).toEqual({ shouldPruneTools: false });
    expect(mocks.evaluate).not.toHaveBeenCalled();
  });
  it("rechecks published eligibility at final proposal acceptance", async () => {
    const cfg = config();
    setRuntimeConfigSnapshot(cfg);
    const proposal = await evaluateAttemptDecisionToolPrefilter(params(cfg));
    expect(proposal.isCurrent?.()).toBe(true);
    setRuntimeConfigSnapshot(config(false));
    expect(proposal.isCurrent?.()).toBe(false);
  });
  it("does not infer from an empty request", async () => {
    expect(await evaluateAttemptDecisionToolPrefilter({ ...params(), userMessage: "  " })).toEqual({
      shouldPruneTools: false,
    });
    expect(mocks.evaluate).not.toHaveBeenCalled();
  });
  it.each(["opt-out", "model-change"])(
    "rejects stale pruning after %s publication",
    async (change) => {
      const cfg = config();
      setRuntimeConfigSnapshot(cfg);
      mocks.evaluate.mockImplementation(async () => {
        setRuntimeConfigSnapshot(
          change === "opt-out" ? config(false) : config(true, "fixture/other"),
        );
        return answer();
      });
      expect(await evaluateAttemptDecisionToolPrefilter(params(cfg))).toEqual({
        shouldPruneTools: false,
      });
    },
  );
  it("preserves explicit prepared config scope independently of the global runtime", async () => {
    setRuntimeConfigSnapshot(config(false));
    const input = params();
    expect(await evaluateAttemptDecisionToolPrefilter(input)).toMatchObject({
      shouldPruneTools: true,
    });
    expect(mocks.evaluate.mock.calls[0]?.[3]).toBe(input.config);
  });
  it("never dispatches after abort or closed authority", async () => {
    const input = params();
    const controller = new AbortController();
    controller.abort(new Error("cancelled"));
    await expect(
      evaluateAttemptDecisionToolPrefilter({ ...input, signal: controller.signal }),
    ).rejects.toThrow("cancelled");
    input.assertActive.mockImplementation(() => {
      throw new Error("closed");
    });
    await expect(evaluateAttemptDecisionToolPrefilter(input)).rejects.toThrow("closed");
    expect(mocks.evaluate).not.toHaveBeenCalled();
  });
  it("preserves unexpected contract errors and late owner cancellation", async () => {
    mocks.evaluate.mockRejectedValueOnce(new Error("contract failure"));
    await expect(evaluateAttemptDecisionToolPrefilter(params())).rejects.toThrow(
      "contract failure",
    );
    const input = params();
    mocks.evaluate.mockImplementation(async () => {
      input.assertActive.mockImplementation(() => {
        throw new Error("closed");
      });
      return answer();
    });
    await expect(evaluateAttemptDecisionToolPrefilter(input)).rejects.toThrow("closed");
  });
});
