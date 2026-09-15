/**
 * Result-shaping helpers for Codex app-server attempt terminal text, replay
 * safety, startup failures, and malformed image errors.
 */
import {
  formatErrorMessage,
  type AgentMessage,
  type EmbeddedRunAttemptParamsV2 as EmbeddedRunAttemptParams,
} from "openclaw/plugin-sdk/agent-harness-runtime";
import type { CodexSystemPromptReport } from "./attempt-context.js";
import type { CodexAttemptTimeout } from "./attempt-deadlines.js";
import { attemptTerminal, type EmbeddedRunAttemptResult } from "./attempt-terminal.js";
import { readMirrorIdentity } from "./upstream-prompt-provenance.js";
import { buildCodexUserPromptMessage } from "./user-prompt-message.js";

/** Joins terminal assistant text blocks into the final attempt answer. */
export function collectTerminalAssistantText(result: EmbeddedRunAttemptResult): string {
  return result.assistantTexts.join("\n\n").trim();
}

/** Reports the owner's deadline without guessing whether native work finished. */
export function buildCodexAppServerPromptTimeoutOutcome(
  timeout: CodexAttemptTimeout | undefined,
): EmbeddedRunAttemptResult["promptTimeoutOutcome"] {
  if (!timeout) {
    return undefined;
  }
  return {
    message:
      timeout.kind === "execution"
        ? "Codex reached the configured execution time limit. Some work may already have been performed; verify the current state before continuing."
        : "Codex finished its turn, but OpenClaw could not finish processing the result. Some work may already have been performed; verify the current state before continuing.",
    replayInvalid: true,
    livenessState: "abandoned",
  };
}

/** Explains why an incomplete app-server turn cannot be safely replayed. */
export function resolveCodexAppServerReplayBlockedReason(
  result: EmbeddedRunAttemptResult,
):
  | NonNullable<EmbeddedRunAttemptResult["codexAppServerFailure"]>["replayBlockedReason"]
  | undefined {
  if (result.replayMetadata.hadPotentialSideEffects) {
    return "potential_side_effect";
  }
  if (result.assistantTexts.some((text) => text.trim().length > 0)) {
    return "assistant_output";
  }
  if (
    result.toolMetas.length > 0 ||
    result.clientToolCalls ||
    result.lastToolError ||
    result.didSendDeterministicApprovalPrompt
  ) {
    return "tool_activity";
  }
  if (result.itemLifecycle.startedCount > 0 || result.itemLifecycle.activeCount > 0) {
    return "active_item";
  }
  return undefined;
}

/** Builds an attempt result for failures before the app-server turn starts. */
export function buildCodexTurnStartFailureResult(params: {
  params: EmbeddedRunAttemptParams;
  message: string;
  promptError?: unknown;
  messagesSnapshot: AgentMessage[];
  systemPromptReport: CodexSystemPromptReport;
}): EmbeddedRunAttemptResult {
  return {
    terminal: attemptTerminal.normalize({
      promptError: params.promptError ?? params.message,
      promptErrorSource: "prompt",
    }),
    sessionIdUsed: params.params.sessionId,
    messagesSnapshot: params.messagesSnapshot,
    assistantTexts: [],
    toolMetas: [],
    lastAssistant: undefined,
    currentAttemptAssistant: undefined,
    didSendViaMessagingTool: false,
    messagingToolSentTexts: [],
    messagingToolSentMediaUrls: [],
    messagingToolSentTargets: [],
    messagingToolSourceReplyPayloads: [],
    cloudCodeAssistFormatError: false,
    replayMetadata: {
      hadPotentialSideEffects: false,
      replaySafe: true,
    },
    itemLifecycle: {
      startedCount: 0,
      completedCount: 0,
      activeCount: 0,
    },
    systemPromptReport: params.systemPromptReport,
  };
}

/** Detects app-server errors caused by invalid image payload data. */
export function isInvalidCodexImagePayloadError(message: unknown): boolean {
  if (typeof message !== "string" || !message.trim()) {
    return false;
  }
  const normalizedMessage = message.replace(/[_-]+/gu, " ");
  return (
    /\b(?:invalid|malformed)\b[\s\S]{0,120}\b(?:image|image url|base64)\b/iu.test(
      normalizedMessage,
    ) ||
    /\b(?:image|image url|base64)\b[\s\S]{0,120}\b(?:invalid|malformed)\b/iu.test(normalizedMessage)
  );
}

/** Builds failure metadata when an app-server turn closes unexpectedly or times out. */
export function buildCodexAppServerFailure(params: {
  clientClosedPromptError?: unknown;
  clientClosedDiagnostic?: unknown;
  timeout?: CodexAttemptTimeout;
  result: EmbeddedRunAttemptResult;
  transport: string;
  threadId: string;
  turnId: string;
}): EmbeddedRunAttemptResult["codexAppServerFailure"] {
  const kind = params.clientClosedPromptError
    ? "client_closed_before_turn_completed"
    : params.timeout?.kind === "settlement"
      ? "turn_settlement_timeout"
      : undefined;
  if (!kind) {
    return undefined;
  }
  const replayBlockedReason = resolveCodexAppServerReplayBlockedReason(params.result);
  const failureDiagnostics =
    kind === "client_closed_before_turn_completed" && params.clientClosedDiagnostic
      ? { transportError: params.clientClosedDiagnostic }
      : params.timeout?.kind === "settlement"
        ? { timeoutMs: params.timeout.timeoutMs }
        : undefined;
  return {
    kind,
    transport: params.transport,
    threadId: params.threadId,
    turnId: params.turnId,
    replaySafe: kind === "client_closed_before_turn_completed" && replayBlockedReason === undefined,
    ...(replayBlockedReason ? { replayBlockedReason } : {}),
    ...(failureDiagnostics ? { diagnostics: failureDiagnostics } : {}),
  };
}

/** Applies final stopReason and errorMessage to this turn's assistant messages in snapshot. */
export function applyTerminalOutcomeToAssistantMessages(params: {
  result: EmbeddedRunAttemptResult;
  activeTurnId: string;
  finalAborted: boolean;
  finalPromptError: unknown;
}): void {
  for (const message of [
    params.result.lastAssistant,
    params.result.currentAttemptAssistant,
    params.result.messagesSnapshot.find(
      (candidate) => readMirrorIdentity(candidate) === `${params.activeTurnId}:assistant`,
    ),
  ]) {
    if (message?.role === "assistant") {
      const providerRefusal = message.diagnostics?.some(
        (diagnostic) => diagnostic.type === "provider_refusal",
      );
      if (!providerRefusal || params.finalAborted || params.finalPromptError) {
        message.stopReason = params.finalAborted
          ? "aborted"
          : params.finalPromptError
            ? "error"
            : "stop";
        message.errorMessage = params.finalPromptError
          ? formatErrorMessage(params.finalPromptError)
          : undefined;
      }
    }
  }
}

/** Determines if an attempt produced a successful, non-interrupted final answer text. */
export function isCompletedFinalAnswer(params: {
  result: EmbeddedRunAttemptResult;
  turnSucceeded: boolean;
  finalAborted: boolean;
  effectiveTimedOut: boolean;
  finalPromptError: unknown;
  localCompletionRequested?: boolean;
}): boolean {
  return (
    collectTerminalAssistantText(params.result).trim().length > 0 &&
    params.turnSucceeded &&
    !params.finalAborted &&
    !params.effectiveTimedOut &&
    !params.finalPromptError &&
    !params.localCompletionRequested
  );
}

/** Clears stale yield metadata when an attempt has completed with a final answer. */
export function clearCompletedFinalAnswerYield(
  toolState: { yieldDetected?: boolean; yieldMessage?: unknown; yieldAcknowledgment?: unknown },
  result: EmbeddedRunAttemptResult,
): void {
  toolState.yieldDetected = false;
  toolState.yieldMessage = undefined;
  toolState.yieldAcknowledgment = undefined;
  result.yieldDetected = false;
  result.yieldAcknowledgment = undefined;
}

/** Attaches final metadata, plugin handoff messages, and diagnostic properties to the attempt result. */
export function finalizeCodexAttemptResult(params: {
  result: EmbeddedRunAttemptResult;
  systemPromptReport: CodexSystemPromptReport;
  turnSucceeded: boolean;
  attemptParams: EmbeddedRunAttemptParams;
  runtimeModelSelection?: EmbeddedRunAttemptResult["runtimeModelSelection"];
  yieldAcknowledgment?: unknown;
  codexAppServerFailure?: EmbeddedRunAttemptResult["codexAppServerFailure"];
  promptTimeoutOutcome?: EmbeddedRunAttemptResult["promptTimeoutOutcome"];
  assistantTranscriptOwned?: boolean;
  assistantTranscriptIdempotencyKey?: string;
  terminalAnchor?: EmbeddedRunAttemptResult["contextEngineTerminalAnchor"];
  settledTurnFinalizationContext?: unknown;
  runtimeArtifact?: unknown;
  runtimeContinuationStarted?: boolean;
  finalAborted: boolean;
  effectiveTimedOut: boolean;
  finalPromptError: unknown;
  preparedAuthBinding?: { fingerprint: string };
}): EmbeddedRunAttemptResult {
  return Object.assign(params.result, {
    ...(params.runtimeModelSelection
      ? { runtimeModelSelection: params.runtimeModelSelection }
      : {}),
    ...(params.turnSucceeded && params.attemptParams.pluginRuntimeRefreshPending?.()
      ? {
          pluginRuntimeRefreshMessages:
            params.attemptParams.suppressNextUserMessagePersistence &&
            !params.attemptParams.pluginRuntimeRefreshMessages
              ? [
                  params.attemptParams.userTurnTranscriptRecorder?.getPersistedMessage?.() ??
                    buildCodexUserPromptMessage(params.attemptParams),
                  ...params.result.messagesSnapshot,
                ]
              : params.result.messagesSnapshot,
        }
      : {}),
    ...(params.yieldAcknowledgment ? { yieldAcknowledgment: params.yieldAcknowledgment } : {}),
    ...(params.codexAppServerFailure
      ? { codexAppServerFailure: params.codexAppServerFailure }
      : {}),
    ...(params.promptTimeoutOutcome ? { promptTimeoutOutcome: params.promptTimeoutOutcome } : {}),
    ...(params.assistantTranscriptOwned ? { assistantTranscriptOwned: true } : {}),
    ...(params.assistantTranscriptIdempotencyKey
      ? { assistantTranscriptIdempotencyKey: params.assistantTranscriptIdempotencyKey }
      : {}),
    ...(params.terminalAnchor ? { contextEngineTerminalAnchor: params.terminalAnchor } : {}),
    ...(params.settledTurnFinalizationContext
      ? { settledTurnFinalizationContext: params.settledTurnFinalizationContext }
      : {}),
    ...(params.runtimeArtifact ? { runtimeArtifact: params.runtimeArtifact } : {}),
    ...(params.runtimeContinuationStarted ? { runtimeContinuationStarted: true } : {}),
    ...(!params.finalAborted &&
    !params.effectiveTimedOut &&
    !params.finalPromptError &&
    params.preparedAuthBinding
      ? { authBindingFingerprint: params.preparedAuthBinding.fingerprint }
      : {}),
    systemPromptReport: params.systemPromptReport,
  });
}
