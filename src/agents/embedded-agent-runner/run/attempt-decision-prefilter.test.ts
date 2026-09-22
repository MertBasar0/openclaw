import { beforeEach, describe, expect, it, vi } from "vitest";
import type { OpenClawConfig } from "../../../config/types.openclaw.js";
import type { DecisionOutcome } from "../../../decisions/types.js";
import { isDecisionAssistanceEligible } from "../../decision-assistance.js";
import { evaluateAttemptDecisionToolPrefilter } from "./attempt-decision-prefilter.js";

const mockEvaluateDecision = vi.fn<() => Promise<DecisionOutcome>>();

vi.mock("../../../decisions/runtime.js", () => ({
  evaluateDecision: () => mockEvaluateDecision(),
}));

const testProvenance = {
  providerId: "test-provider",
  rubricVersion: "1",
  runtimeGeneration: "test-gen-1",
};

describe("evaluateAttemptDecisionToolPrefilter", () => {
  const configWithDecisionAndLabs: OpenClawConfig = {
    agents: {
      defaults: {
        experimental: {
          decisionAssistance: true,
        },
        decisionModel: "fast-judge/v1",
      },
    },
  };

  const configWithDecisionWithoutLabs: OpenClawConfig = {
    agents: {
      defaults: {
        decisionModel: "fast-judge/v1",
      },
    },
  };

  const configWithoutDecision: OpenClawConfig = {
    agents: {
      defaults: {},
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Labs gating", () => {
    it("returns shouldPruneTools false and dispatches zero inference when Labs consent is absent despite configured decisionModel", async () => {
      const result = await evaluateAttemptDecisionToolPrefilter({
        config: configWithDecisionWithoutLabs,
        userMessage: "What is the capital of France?",
      });
      expect(result).toEqual({ shouldPruneTools: false });
      expect(mockEvaluateDecision).not.toHaveBeenCalled();
    });

    it("returns shouldPruneTools false when Labs flag is explicitly false", async () => {
      const configWithLabsDisabled: OpenClawConfig = {
        agents: {
          defaults: {
            experimental: {
              decisionAssistance: false,
            },
            decisionModel: "fast-judge/v1",
          },
        },
      };
      const result = await evaluateAttemptDecisionToolPrefilter({
        config: configWithLabsDisabled,
        userMessage: "What is the capital of France?",
      });
      expect(result).toEqual({ shouldPruneTools: false });
      expect(mockEvaluateDecision).not.toHaveBeenCalled();
    });

    it("evaluates eligibility accurately across scopes and overrides", async () => {
      expect(isDecisionAssistanceEligible(configWithoutDecision, "main")).toBe(false);
      expect(isDecisionAssistanceEligible(configWithDecisionWithoutLabs, "main")).toBe(false);
      expect(isDecisionAssistanceEligible(configWithDecisionAndLabs, "main")).toBe(true);

      const configWithAgentOptOut: OpenClawConfig = {
        agents: {
          defaults: {
            experimental: { decisionAssistance: true },
            decisionModel: "fast-judge/v1",
          },
          entries: {
            "agent-opt-out": { decisionModel: "" },
          },
        },
      };

      expect(isDecisionAssistanceEligible(configWithAgentOptOut, "agent-opt-out")).toBe(false);
      expect(isDecisionAssistanceEligible(configWithAgentOptOut, "other-agent")).toBe(true);

      const resultOptOut = await evaluateAttemptDecisionToolPrefilter({
        config: configWithAgentOptOut,
        agentId: "agent-opt-out",
        userMessage: "What is the capital of France?",
      });
      expect(resultOptOut).toEqual({ shouldPruneTools: false });
      expect(mockEvaluateDecision).not.toHaveBeenCalled();
    });
  });

  it("returns shouldPruneTools false when user message is empty or whitespace", async () => {
    const resultEmpty = await evaluateAttemptDecisionToolPrefilter({
      config: configWithDecisionAndLabs,
      userMessage: "",
    });
    expect(resultEmpty).toEqual({ shouldPruneTools: false });

    const resultWhitespace = await evaluateAttemptDecisionToolPrefilter({
      config: configWithDecisionAndLabs,
      userMessage: "   \n\t  ",
    });
    expect(resultWhitespace).toEqual({ shouldPruneTools: false });
    expect(mockEvaluateDecision).not.toHaveBeenCalled();
  });

  it("returns shouldPruneTools false when no decision model is configured", async () => {
    const result = await evaluateAttemptDecisionToolPrefilter({
      config: configWithoutDecision,
      userMessage: "Hello, how are you?",
    });
    expect(result).toEqual({ shouldPruneTools: false });
    expect(mockEvaluateDecision).not.toHaveBeenCalled();
  });

  it("prunes tools when decision model detects pure conversation below threshold", async () => {
    mockEvaluateDecision.mockResolvedValueOnce({
      status: "ok",
      provenance: testProvenance,
      result: {
        model: "fast-judge/v1",
        answers: {
          any_tool_needed: {
            type: "boolean",
            probabilityTrue: 0.12,
          },
        },
      },
    });

    const result = await evaluateAttemptDecisionToolPrefilter({
      config: configWithDecisionAndLabs,
      userMessage: "What is the capital of France?",
    });

    expect(result).toEqual({ shouldPruneTools: true });
    expect(mockEvaluateDecision).toHaveBeenCalledTimes(1);
  });

  it("retains tools when decision model indicates tools are needed", async () => {
    mockEvaluateDecision.mockResolvedValueOnce({
      status: "ok",
      provenance: testProvenance,
      result: {
        model: "fast-judge/v1",
        answers: {
          any_tool_needed: {
            type: "boolean",
            probabilityTrue: 0.85,
          },
        },
      },
    });

    const result = await evaluateAttemptDecisionToolPrefilter({
      config: configWithDecisionAndLabs,
      userMessage: "Run git status and show untracked files",
    });

    expect(result).toEqual({ shouldPruneTools: false });
  });

  it("respects custom probability threshold", async () => {
    mockEvaluateDecision.mockResolvedValueOnce({
      status: "ok",
      provenance: testProvenance,
      result: {
        model: "fast-judge/v1",
        answers: {
          any_tool_needed: {
            type: "boolean",
            probabilityTrue: 0.45,
          },
        },
      },
    });

    // Default threshold is 0.35 -> 0.45 >= 0.35 -> should not prune
    // With custom threshold 0.50 -> 0.45 < 0.50 -> should prune
    const result = await evaluateAttemptDecisionToolPrefilter({
      config: configWithDecisionAndLabs,
      userMessage: "Can you explain this function?",
      threshold: 0.5,
    });

    expect(result).toEqual({ shouldPruneTools: true });
  });

  it("fails open when decision provider is unavailable", async () => {
    mockEvaluateDecision.mockResolvedValueOnce({
      status: "unavailable",
      reason: "rate-limited",
    });

    const result = await evaluateAttemptDecisionToolPrefilter({
      config: configWithDecisionAndLabs,
      userMessage: "Hello world",
    });

    expect(result).toEqual({ shouldPruneTools: false });
  });

  it("fails open when evaluateDecision throws an ordinary error", async () => {
    mockEvaluateDecision.mockRejectedValueOnce(new Error("Network timeout"));

    const result = await evaluateAttemptDecisionToolPrefilter({
      config: configWithDecisionAndLabs,
      userMessage: "Hello world",
    });

    expect(result).toEqual({ shouldPruneTools: false });
  });

  describe("cancellation binding", () => {
    it("throws immediately when signal is already aborted before evaluation", async () => {
      const abortController = new AbortController();
      abortController.abort(new Error("Attempt cancelled"));

      await expect(
        evaluateAttemptDecisionToolPrefilter({
          config: configWithDecisionAndLabs,
          userMessage: "Hello world",
          signal: abortController.signal,
        }),
      ).rejects.toThrow();

      expect(mockEvaluateDecision).not.toHaveBeenCalled();
    });

    it("rethrows terminal cancellation when signal is aborted during evaluation", async () => {
      const abortController = new AbortController();
      mockEvaluateDecision.mockImplementationOnce(async () => {
        abortController.abort(new Error("Terminal attempt abort"));
        throw new Error("Evaluation aborted");
      });

      await expect(
        evaluateAttemptDecisionToolPrefilter({
          config: configWithDecisionAndLabs,
          userMessage: "Hello world",
          signal: abortController.signal,
        }),
      ).rejects.toThrow();
    });
  });
});
