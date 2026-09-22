import type { OpenClawConfig } from "../../../config/types.openclaw.js";
import { evaluateDecision } from "../../../decisions/runtime.js";
import { isDecisionAssistanceEligible } from "../../decision-assistance.js";
import { log } from "../logger.js";

export type EvaluateAttemptDecisionToolPrefilterParams = {
  config: OpenClawConfig;
  agentId?: string;
  userMessage?: string;
  signal?: AbortSignal;
  threshold?: number;
  timeoutMs?: number;
};

export type AttemptDecisionToolPrefilterResult = {
  shouldPruneTools: boolean;
};

const DEFAULT_TOOL_PROBABILITY_THRESHOLD = 0.35;
const DEFAULT_DECISION_TIMEOUT_MS = 500;
const TOOL_PREFILTER_PURPOSE = "tool-prefilter.semantic-gate";
const TOOL_PREFILTER_RUBRIC_VERSION = "1";

/**
 * Evaluates whether an embedded agent turn is purely conversational and can omit
 * external tool definitions from the model prompt context.
 *
 * Fails open: missing configuration, timeouts, or evaluation errors preserve all tools.
 * Preserves terminal cancellation if the attempt abort signal is aborted.
 */
export async function evaluateAttemptDecisionToolPrefilter(
  params: EvaluateAttemptDecisionToolPrefilterParams,
): Promise<AttemptDecisionToolPrefilterResult> {
  params.signal?.throwIfAborted();

  const rawMessage = params.userMessage?.trim();
  if (!rawMessage) {
    return { shouldPruneTools: false };
  }

  if (!params.config || !isDecisionAssistanceEligible(params.config, params.agentId ?? "")) {
    return { shouldPruneTools: false };
  }

  const threshold = params.threshold ?? DEFAULT_TOOL_PROBABILITY_THRESHOLD;
  const timeoutMs = params.timeoutMs ?? DEFAULT_DECISION_TIMEOUT_MS;

  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), timeoutMs);
  const evaluationSignal = params.signal
    ? AbortSignal.any([params.signal, controller.signal])
    : controller.signal;

  try {
    const outcome = await evaluateDecision(
      {
        state: { userMessage: rawMessage },
        questions: {
          any_tool_needed: {
            type: "boolean",
            instructions:
              "Does this user prompt require executing an external tool (such as bash, git, file reading/writing, web search, database operations, or APIs), or can it be answered purely as conversational knowledge/dialogue?",
            criteria: {
              true: "User prompt requires external tools, code execution, search, or filesystem/API operations",
              false:
                "Can be answered purely as conversational knowledge, greetings, or dialogue without external tools",
            },
          },
        },
      },
      {
        agentId: params.agentId,
        purpose: TOOL_PREFILTER_PURPOSE,
        rubricVersion: TOOL_PREFILTER_RUBRIC_VERSION,
        timeoutMs,
        signal: evaluationSignal,
      },
    );

    if (outcome.status === "ok") {
      const answer = outcome.result.answers.any_tool_needed;
      if (answer && answer.type === "boolean" && typeof answer.probabilityTrue === "number") {
        const prob = answer.probabilityTrue;
        if (prob < threshold) {
          log.info(
            `[decision-prefilter] Pure conversation detected (tool probability: ${(prob * 100).toFixed(1)}% < ${(threshold * 100).toFixed(1)}%). Pruning tools to save context.`,
          );
          return { shouldPruneTools: true };
        }
      }
    }
  } catch (err) {
    if (params.signal?.aborted) {
      params.signal.throwIfAborted();
    }
    log.warn(`[decision-prefilter] Decision evaluation failed, failing open: ${String(err)}`);
  } finally {
    clearTimeout(timeoutHandle);
  }

  return { shouldPruneTools: false };
}
