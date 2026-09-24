import type { StreamFn } from "openclaw/plugin-sdk/agent-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ImageContent } from "../../../llm/types.js";
import type { AgentMessage } from "../../runtime/index.js";
import {
  createAssistant,
  createAssistantResultStream,
  testModel,
} from "../../sessions/agent-session-loop-correctness.test-support.js";
import { agentSessionQueuePromptContext } from "../../sessions/agent-session-prompting.js";
import {
  clearEmbeddedSessionPromptStates,
  getEmbeddedSessionPromptState,
} from "../session-prompt-state.js";
import { submitEmbeddedAttemptPrompt } from "./attempt-prompt-submit.js";
const sessionId = "attempt-prompt-submit-observation-test";
function createSession() {
  const state = {
    messages: [{ role: "user", content: "transcript prompt", timestamp: 1 }] as AgentMessage[],
  };
  const baseStreamFn: StreamFn = () => {
    throw new Error("stream function should not be called directly");
  };
  const originalTransformContext = async (messages: AgentMessage[]) => messages;
  const agent = {
    state,
    streamFn: baseStreamFn,
    transformContext: originalTransformContext,
    reset: () => {
      state.messages = [];
    },
  };
  const activeSession = {
    [agentSessionQueuePromptContext]: vi.fn(() => () => undefined),
    get messages() {
      return state.messages;
    },
    agent,
  };
  return { activeSession, baseStreamFn, originalTransformContext };
}

function createBaseInput() {
  const sessionPromptState = getEmbeddedSessionPromptState(sessionId);
  return {
    attempt: { sessionId },
    appendContext: "append context",
    contextTokenBudget: 8_000,
    images: [] as ImageContent[],
    modelPrompt: "model prompt",
    onFinalPromptText: vi.fn(),
    onSteeringAcknowledged: vi.fn(),
    persistToolResultProjections: vi.fn(async () => {}),
    prependContext: "prepend context",
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

afterEach(() => clearEmbeddedSessionPromptStates([sessionId]));
describe("primary submission observation", () => {
  it("observes only the first admitted foreground tool definitions, not compaction or later loop requests", async () => {
    const { activeSession } = createSession();
    const stream = vi.fn(() =>
      createAssistantResultStream(createAssistant(testModel, [{ type: "text", text: "ok" }])),
    );
    activeSession.agent.streamFn = stream;
    const observe = vi.fn();
    const tools = [
      {
        name: "message",
        description: "visible",
        parameters: { type: "object" as const, properties: {} },
      },
    ];
    await submitEmbeddedAttemptPrompt({
      ...createBaseInput(),
      activeSession,
      onPrimaryModelRequest: observe,
      promptActiveSession: async (_prompt, options) => {
        await activeSession.agent.streamFn(testModel, { messages: [] }, {});
        expect(observe).not.toHaveBeenCalled();
        options?.preflightResult?.(true);
        await activeSession.agent.streamFn(testModel, { messages: [], tools }, {});
        await activeSession.agent.streamFn(testModel, { messages: [], tools: [] }, {});
      },
    });
    expect(observe).toHaveBeenCalledExactlyOnceWith(tools);
    expect(activeSession.agent.streamFn).toBe(stream);
  });
  it.each(["preflight", "aborted"])(
    "does not report applied filtering for %s-only submission",
    async (kind) => {
      const { activeSession } = createSession();
      activeSession.agent.streamFn = vi.fn(() =>
        createAssistantResultStream(createAssistant(testModel, [])),
      );
      const observe = vi.fn();
      const execute = submitEmbeddedAttemptPrompt({
        ...createBaseInput(),
        activeSession,
        onPrimaryModelRequest: observe,
        promptActiveSession: async (_prompt, options) => {
          if (kind === "preflight") {
            options?.preflightResult?.(false);
            return;
          }
          options?.preflightResult?.(true);
          const controller = new AbortController();
          controller.abort(new Error("cancelled"));
          await activeSession.agent.streamFn(
            testModel,
            { messages: [] },
            { signal: controller.signal },
          );
        },
      });
      if (kind === "aborted") {
        await expect(execute).rejects.toThrow("cancelled");
      } else {
        await execute;
      }
      expect(observe).not.toHaveBeenCalled();
    },
  );
});
