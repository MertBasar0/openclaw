import { afterEach, describe, expect, it, vi } from "vitest";
import type { ImageContent } from "../../../llm/types.js";
import {
  createTestSession,
  registerAgentSessionLoopTestLifecycle,
} from "../../sessions/agent-session-loop-correctness.test-support.js";
import {
  clearEmbeddedSessionPromptStates,
  getEmbeddedSessionPromptState,
} from "../session-prompt-state.js";
import { submitEmbeddedAttemptPrompt } from "./attempt-prompt-submit.js";

registerAgentSessionLoopTestLifecycle();

const sessionId = "attempt-prompt-submit-replay-boundary-test";

function createBaseInput() {
  const sessionPromptState = getEmbeddedSessionPromptState(sessionId);
  return {
    attempt: { sessionId },
    contextTokenBudget: 8_000,
    images: [] as ImageContent[],
    modelPrompt: "model prompt",
    onFinalPromptText: vi.fn(),
    onSteeringAcknowledged: vi.fn(),
    persistToolResultProjections: vi.fn(async () => {}),
    runtimeOnly: false,
    sessionPromptState,
    systemPrompt: "system prompt",
    toolResultAggregateMaxChars: 8_000,
    toolResultMaxChars: 4_000,
    toolResultPromptProjectionState: sessionPromptState.toolResults,
    trajectoryRecorder: null,
    transcriptLeafId: null,
    transcriptPrompt: "transcript prompt",
  };
}

afterEach(() => {
  clearEmbeddedSessionPromptStates([sessionId]);
});

describe("submitEmbeddedAttemptPrompt replay boundary", () => {
  it("rebases the prompt boundary onto the normalized replay history", async () => {
    // Replay normalization drops transcript-only OpenClaw entries. A boundary
    // captured before it then outruns the messages that remain, so the deferred
    // tool loop classifies the current input and new tool results as history and
    // drops them from the next model call.
    const { session } = await createTestSession({});
    const mirror = {
      role: "assistant",
      content: [{ type: "text", text: "delivered" }],
      openclawDeliveryMirror: { kind: "channel-final" },
      timestamp: Date.now(),
    } as unknown as (typeof session.messages)[number];
    const kept = [
      { role: "user", content: "earlier request", timestamp: Date.now() },
      { role: "user", content: "later request", timestamp: Date.now() },
    ] as unknown as (typeof session.messages)[number][];
    // One removable entry sitting between entries the normalizer keeps.
    session.agent.state.messages = [...session.messages, kept[0]!, mirror, kept[1]!];
    const capturedBoundary = session.messages.length;
    expect(capturedBoundary).toBeGreaterThanOrEqual(3);

    const onReplayNormalized = vi.fn<(count: number) => void>();
    await submitEmbeddedAttemptPrompt({
      ...createBaseInput(),
      activeSession: session,
      prePromptMessageCount: capturedBoundary,
      onReplayNormalized,
      promptActiveSession: (prompt, options) => session.prompt(prompt, options),
    });

    // The dropped mirror must come off the boundary, not off the pending suffix.
    expect(onReplayNormalized).toHaveBeenCalledWith(capturedBoundary - 1);
  });
});
