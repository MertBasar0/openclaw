import { createRuntimeConfigReader } from "../../../config/runtime-snapshot.js";
import type { OpenClawConfig } from "../../../config/types.openclaw.js";
import { evaluateDecisionInRegistry } from "../../../decisions/runtime.js";
import { getPluginRegistryForContext } from "../../../plugins/runtime/gateway-request-scope.js";
import { isDecisionAssistanceEligible } from "../../decision-assistance.js";
import { resolveDecisionModelSetting } from "../../decision-model-setting.js";

type EvaluateAttemptDecisionToolPrefilterParams = {
  config: OpenClawConfig;
  agentId: string;
  supportsTurnScopedToolRestrictions?: boolean;
  assertActive: () => void;
  userMessage?: string;
  signal: AbortSignal;
};

/** Ordinary unavailability preserves tools; cancellation and contract errors remain terminal. */
export async function evaluateAttemptDecisionToolPrefilter(
  params: EvaluateAttemptDecisionToolPrefilterParams,
): Promise<{ shouldPruneTools: boolean; isCurrent?: () => boolean }> {
  params.signal.throwIfAborted();
  params.assertActive();
  const readConfig = createRuntimeConfigReader(params.config);
  const config = readConfig();
  if (
    !params.agentId.trim() ||
    params.supportsTurnScopedToolRestrictions !== true ||
    !isDecisionAssistanceEligible(config, params.agentId)
  ) {
    return { shouldPruneTools: false };
  }
  const userMessage = params.userMessage?.trim();
  // A named explicit evaluation is an action even if its supplied evidence is a greeting.
  if (!userMessage || /\bdecision_evaluate\b/i.test(userMessage)) {
    return { shouldPruneTools: false };
  }
  const selection = resolveDecisionModelSetting(config, params.agentId);
  const outcome = await evaluateDecisionInRegistry(
    {
      state: { userMessage },
      questions: {
        any_tool_needed: {
          type: "boolean",
          criteria: {
            true: "An action request requiring tools or a follow-up that needs missing context",
            false:
              "A self-contained greeting, farewell, thanks, conversation, joke, or general knowledge question",
          },
        },
      },
    },
    {
      agentId: params.agentId,
      purpose: "tool-prefilter.semantic-gate",
      rubricVersion: "3",
      timeoutMs: 500,
      signal: params.signal,
    },
    getPluginRegistryForContext(),
    config,
  );
  const isCurrent = () => {
    params.signal.throwIfAborted();
    params.assertActive();
    const current = readConfig();
    const currentSelection = resolveDecisionModelSetting(current, params.agentId);
    return (
      isDecisionAssistanceEligible(current, params.agentId) &&
      currentSelection?.provider === selection?.provider &&
      currentSelection?.model === selection?.model
    );
  };
  if (!isCurrent()) {
    return { shouldPruneTools: false };
  }
  const answer = outcome.status === "ok" ? outcome.result.answers.any_tool_needed : undefined;
  return answer?.type === "boolean" && answer.probabilityTrue < 0.35
    ? { shouldPruneTools: true, isCurrent }
    : { shouldPruneTools: false };
}
