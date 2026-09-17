import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SessionManager } from "../../../agents/sessions/session-manager.js";
import { formatSqliteSessionFileMarker } from "../../../config/sessions/legacy-sqlite-marker.js";
import {
  appendTranscriptMessage,
  loadTranscriptEvents,
  upsertSessionEntryCore,
} from "../../../config/sessions/session-accessor.js";
import { closeOpenClawAgentDatabasesForTest } from "../../../state/openclaw-agent-db.js";
import { ensureClientVoiceAgentSessionEntry } from "../../../talk/client-voice-session.js";
import { clientVoiceSessionTesting } from "../../../talk/client-voice-session.test-support.js";
import type { RealtimeVoiceBridgeCreateRequest } from "../../../talk/provider-types.js";
import {
  createOpenClawTestState,
  type OpenClawTestState,
} from "../../../test-utils/openclaw-test-state.js";
import * as chatSendHandler from "../../server-methods/chat-send-handler.js";
import { controlBridge, controlContext } from "../client-gateway-control.test-support.js";
import { talkClientHandlers } from "../handlers/client.js";
import { prepareTalkSessionTarget } from "../session-target.js";
import {
  acquireTalkRealtimeRelayVoiceBarrier,
  createTalkRealtimeRelaySession,
  releaseTalkRealtimeRelayVoiceBarrier,
} from "./index.js";
import { closeRelaySession, resetTalkRealtimeRelayContinuity } from "./operations.js";
import { clearRelayAgentToolCall } from "./provider-results.js";
import { relaySessions, type RelaySession } from "./state.js";
import { enqueueRelayVoiceTranscript } from "./voice.js";

describe("openclaw#150204: talk relay transcript barrier regression", () => {
  let state: OpenClawTestState;
  let relaySessionId: string | undefined;
  let ownedRelay: RelaySession | undefined;
  const connId = "relay-barrier-test-client";
  const agentId = "main";
  const sessionKey = "agent:main:main";

  beforeEach(async () => {
    state = await createOpenClawTestState({ label: "relay-barrier", applyEnv: true });
    await ensureClientVoiceAgentSessionEntry({ agentId, sessionKey });
  });

  afterEach(async () => {
    if (ownedRelay) {
      await closeRelaySession(ownedRelay, "completed");
      ownedRelay = undefined;
    }
    clientVoiceSessionTesting.reset();
    closeOpenClawAgentDatabasesForTest();
    await state.cleanup();
  });

  function extractMessageText(content: unknown): string {
    if (typeof content === "string") {
      return content;
    }
    if (
      Array.isArray(content) &&
      content[0] &&
      typeof content[0] === "object" &&
      "text" in content[0]
    ) {
      return (content[0] as { text: string }).text;
    }
    return String(content);
  }

  function createRelayHarness() {
    const cfg = { agents: { entries: { main: { default: true } } } };
    let bridgeRequest: RealtimeVoiceBridgeCreateRequest | undefined;
    const session = createTalkRealtimeRelaySession({
      cfg,
      context: controlContext(),
      connId,
      sessionTarget: prepareTalkSessionTarget(cfg, sessionKey),
      controlSource: "delegation",
      provider: {
        id: "relay-barrier-provider",
        label: "Relay barrier provider",
        isConfigured: () => true,
        createBridge: (options) => {
          bridgeRequest = options;
          return controlBridge();
        },
      },
      providerConfig: {},
      instructions: "Answer briefly.",
      tools: [],
    });
    relaySessionId = session.relaySessionId;
    const relay = relaySessions.get(relaySessionId);
    if (!relay || !bridgeRequest) {
      throw new Error("expected a registered native relay");
    }
    ownedRelay = relay;
    return { relay, bridgeRequest, session };
  }

  it.each(["assistant", "user"] as const)(
    "pre-fix reproduction: %s transcript landing before run adoption moves anchor and fails adoption",
    async (role) => {
      const { relay } = createRelayHarness();
      const scope = {
        agentId,
        sessionId: "main",
        sessionKey,
        storePath: relay.sessionTarget.storePath,
      };

      await upsertSessionEntryCore(scope, {
        sessionFile: formatSqliteSessionFileMarker(scope),
        sessionId: scope.sessionId,
        updatedAt: 1,
      });

      // 1. Flush existing writes before consult (what current unpatched code does)
      await relay.voiceTranscriptQueue.flush();

      // 2. Pre-persist the keyed consult user turn
      const idempotencyKey = `talk-call1-${Date.now()}`;
      const consultUserMessage = {
        role: "user" as const,
        content: "What is on the calendar tomorrow?",
        idempotencyKey,
        excludeFromContext: true,
        timestamp: Date.now(),
      };
      await appendTranscriptMessage(scope, {
        eventId: "keyed-consult-turn",
        message: consultUserMessage,
        now: Date.now(),
      });

      // 3. Realtime voice transcript arrives from model or user before adoption
      enqueueRelayVoiceTranscript(
        relay,
        role,
        role === "assistant" ? "Checking now..." : "Wait a sec",
      );

      // On unpatched code, the queue executes immediately without holding.
      // Wait for the queue to drain into SQLite:
      await relay.voiceTranscriptQueue.flush();

      // 4. Embedded agent run starts and attempts keyed adoption
      const sessionManager = SessionManager.openBounded(scope, {
        maxBytes: 100_000,
        maxEvents: 100,
      });

      // EXPECTED PRE-FIX REPRO:
      // Fails with "Session transcript keyed user is outside the current turn" because
      // the voice transcript appended after the keyed turn moved the anchor!
      expect(() => sessionManager.appendMessage(consultUserMessage)).toThrow(
        "Session transcript keyed user is outside the current turn",
      );
    },
  );

  it.each(["assistant", "user"] as const)(
    "post-fix: %s transcript arriving during consult is held by barrier, adoption succeeds, and held speech drains upon settlement",
    async (role) => {
      const { relay } = createRelayHarness();
      const scope = {
        agentId,
        sessionId: "main",
        sessionKey,
        storePath: relay.sessionTarget.storePath,
      };

      await upsertSessionEntryCore(scope, {
        sessionFile: formatSqliteSessionFileMarker(scope),
        sessionId: scope.sessionId,
        updatedAt: 1,
      });

      // 1. Acquire barrier for consult
      const callId = `call-barrier-${role}`;
      const barrier = await acquireTalkRealtimeRelayVoiceBarrier({
        relaySessionId: relay.id,
        connId,
        callId,
      });
      expect(barrier.active).toBe(true);

      // 2. Pre-persist the keyed consult user turn
      const idempotencyKey = `talk-${callId}-${Date.now()}`;
      const consultUserMessage = {
        role: "user" as const,
        content: "What is on the calendar tomorrow?",
        idempotencyKey,
        excludeFromContext: true,
        timestamp: Date.now(),
      };
      await appendTranscriptMessage(scope, {
        eventId: "keyed-consult-turn",
        message: consultUserMessage,
        now: Date.now(),
      });

      // 3. Realtime voice transcript arrives from model or user while barrier is held
      const speechText = role === "assistant" ? "Checking now..." : "Wait a sec";
      expect(enqueueRelayVoiceTranscript(relay, role, speechText)).toBe(true);
      expect(barrier.heldCount).toBe(1);

      // 4. Embedded agent run starts and adopts the keyed user turn - this MUST NOT throw!
      const sessionManager = SessionManager.openBounded(scope, {
        maxBytes: 100_000,
        maxEvents: 100,
      });
      expect(() => sessionManager.appendMessage(consultUserMessage)).not.toThrow();

      // Consult agent appends its assistant response
      sessionManager.appendMessage({
        role: "assistant",
        content: [{ type: "text", text: "You have an all-hands meeting tomorrow at 10 AM." }],
        api: "chat",
        provider: "test",
        model: "test-model",
        usage: {
          input: 0,
          output: 0,
          cacheRead: 0,
          cacheWrite: 0,
          totalTokens: 0,
          cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
        },
        stopReason: "stop",
        timestamp: Date.now(),
      });

      // 5. Consult settles (tool call completes or results are accepted)
      releaseTalkRealtimeRelayVoiceBarrier({
        relaySessionId: relay.id,
        connId,
        callId,
      });
      expect(barrier.active).toBe(false);

      // 6. Held transcripts drain into SQLite in FIFO order
      await relay.voiceTranscriptQueue.flush();

      // Verify transcript messages in SQLite:
      // Order must be: consultUserMessage -> consult assistant response -> speechText!
      const events = (await loadTranscriptEvents(scope)) as Array<{
        type?: string;
        message?: { role?: string; content?: unknown };
      }>;
      const messages = events
        .filter((e) => e.type === "message" && e.message)
        .map((e) => e.message!);

      expect(messages).toHaveLength(3);
      expect(messages[0]?.role).toBe("user");
      expect(extractMessageText(messages[0]?.content)).toBe("What is on the calendar tomorrow?");
      expect(messages[1]?.role).toBe("assistant");
      expect(extractMessageText(messages[1]?.content)).toBe(
        "You have an all-hands meeting tomorrow at 10 AM.",
      );
      expect(messages[2]?.role).toBe(role);
      expect(extractMessageText(messages[2]?.content)).toBe(speechText);
    },
  );

  it("spoken confirmation readiness observes user speech synchronously while barrier holds persistence", async () => {
    const { relay } = createRelayHarness();
    const callId = "call-confirmation-1";
    await acquireTalkRealtimeRelayVoiceBarrier({
      relaySessionId: relay.id,
      connId,
      callId,
    });

    let observedText = "";
    const observeUserTranscriptMock = vi.fn((text: string) => {
      observedText = text;
      return undefined;
    });
    relay.confirmationReadiness.observeUserTranscript = observeUserTranscriptMock;

    enqueueRelayVoiceTranscript(relay, "user", "yes please proceed");

    // The confirmation observer was invoked synchronously at admission:
    expect(observeUserTranscriptMock).toHaveBeenCalledWith("yes please proceed", true);
    expect(observedText).toBe("yes please proceed");

    releaseTalkRealtimeRelayVoiceBarrier({ relaySessionId: relay.id, connId, callId });
    await relay.voiceTranscriptQueue.flush();
  });

  it("edge 1: approaching queue capacity force-releases barrier to prevent failSession", async () => {
    const { relay } = createRelayHarness();
    const failSessionSpy = vi.spyOn(relay, "failSession");
    const callId = "call-overflow-1";
    const barrier = await acquireTalkRealtimeRelayVoiceBarrier({
      relaySessionId: relay.id,
      connId,
      callId,
    });
    expect(barrier.active).toBe(true);

    // Enqueue transcripts until capacity threshold (38 items)
    for (let i = 0; i < 38; i++) {
      enqueueRelayVoiceTranscript(relay, "user", `speech chunk ${i}`);
    }

    // Barrier must have force-released to drain queue before overflow
    expect(barrier.active).toBe(false);
    expect(failSessionSpy).not.toHaveBeenCalled();

    // Subsequent appends continue to be accepted without overflow
    expect(enqueueRelayVoiceTranscript(relay, "assistant", "still working")).toBe(true);
    expect(failSessionSpy).not.toHaveBeenCalled();

    await relay.voiceTranscriptQueue.flush();
  });

  it("edge 2: closing relay while barrier is held completes without hanging or deadlock", async () => {
    const { relay } = createRelayHarness();
    const callId = "call-close-deadlock-1";
    const barrier = await acquireTalkRealtimeRelayVoiceBarrier({
      relaySessionId: relay.id,
      connId,
      callId,
    });
    expect(barrier.active).toBe(true);

    enqueueRelayVoiceTranscript(relay, "user", "speech before close");

    // Close while barrier is active and speech is held
    const closePromise = closeRelaySession(relay, "completed");

    // Barrier must be released by close
    expect(barrier.active).toBe(false);

    // Must resolve promptly (not deadlock on flush)
    await expect(closePromise).resolves.toBeUndefined();
    ownedRelay = undefined;
  });

  it("edge 3: in-flight retries settle before acquireTalkRealtimeRelayVoiceBarrier returns", async () => {
    const { relay } = createRelayHarness();
    const scope = {
      agentId,
      sessionId: "main",
      sessionKey,
      storePath: relay.sessionTarget.storePath,
    };
    await upsertSessionEntryCore(scope, {
      sessionFile: formatSqliteSessionFileMarker(scope),
      sessionId: scope.sessionId,
      updatedAt: 1,
    });

    // Enqueue a transcript that will settle
    enqueueRelayVoiceTranscript(relay, "user", "earlier speech");

    // When barrier is acquired, it flushes pre-existing writes
    const barrier = await acquireTalkRealtimeRelayVoiceBarrier({
      relaySessionId: relay.id,
      connId,
      callId: "call-retry-1",
    });

    // Verify earlier speech has already settled in SQLite before barrier acquisition finished
    const events = (await loadTranscriptEvents(scope)) as Array<{
      type?: string;
      message?: { role?: string; content?: unknown };
    }>;
    const messages = events.filter((e) => e.type === "message" && e.message).map((e) => e.message!);
    expect(messages).toHaveLength(1);
    expect(extractMessageText(messages[0]?.content)).toBe("earlier speech");

    barrier.release();
    await relay.voiceTranscriptQueue.flush();
  });

  it("continuity reset releases barrier and drains held speech", async () => {
    const { relay } = createRelayHarness();
    const barrier = await acquireTalkRealtimeRelayVoiceBarrier({
      relaySessionId: relay.id,
      connId,
      callId: "call-continuity-1",
    });
    expect(barrier.active).toBe(true);

    enqueueRelayVoiceTranscript(relay, "user", "continuity speech");
    expect(barrier.heldCount).toBe(1);

    // Provider continuity reset releases barrier immediately
    resetTalkRealtimeRelayContinuity(relay);
    expect(barrier.active).toBe(false);

    // Queue drains
    await relay.voiceTranscriptQueue.flush();
  });

  it("behavior proof: talk.client.toolCall consult holds voice transcripts, allows clean adoption, and drains on settlement", async () => {
    const { relay } = createRelayHarness();
    const scope = {
      agentId,
      sessionId: "main",
      sessionKey,
      storePath: relay.sessionTarget.storePath,
    };

    await upsertSessionEntryCore(scope, {
      sessionFile: formatSqliteSessionFileMarker(scope),
      sessionId: scope.sessionId,
      updatedAt: 1,
    });

    const callId = "talk-call_proof_1";
    const idempotencyKey = `talk-${callId}-${Date.now()}`;
    const consultUserMessage = {
      role: "user" as const,
      content: "What is on the calendar tomorrow?",
      idempotencyKey,
      excludeFromContext: true,
      timestamp: Date.now(),
    };

    const spy = vi
      .spyOn(chatSendHandler, "handleTrustedInternalChatSend")
      .mockImplementationOnce(async (options) => {
        // Consult pre-persists keyed consult user turn
        await appendTranscriptMessage(scope, {
          eventId: "keyed-consult-turn",
          message: consultUserMessage,
          now: Date.now(),
        });
        options.respond(true, { runId: "run-proof-1" });
      });

    let toolCallAck: unknown;
    await talkClientHandlers["talk.client.toolCall"]?.({
      req: { id: "req-proof-1", type: "req", method: "talk.client.toolCall" },
      params: {
        sessionKey,
        callId,
        name: "openclaw_agent_consult",
        args: { question: "What is on the calendar tomorrow?" },
        relaySessionId: relay.id,
      },
      client: {
        connId,
        connect: {
          scopes: ["operator.admin"],
          caps: ["tool-events", "task-suggestions"],
        },
      },
      respond: (ok: boolean, result?: unknown, err?: unknown) => {
        toolCallAck = { ok, result, err };
      },
      context: {
        ...relay.context,
        getRuntimeConfig: () => ({ agents: { entries: { main: { default: true } } } }),
      },
      sessionMutationAuthorization: {
        talkSessionTarget: relay.sessionTarget,
        assertCurrent: () => {},
      },
    } as never);

    expect(toolCallAck).toEqual(expect.objectContaining({ ok: true }));

    // 1. Barrier was installed via talk.client.toolCall
    const barrier = relay.voiceTranscriptBarrier;
    expect(barrier).toBeDefined();
    expect(barrier?.active).toBe(true);
    expect(barrier?.callIds.has(callId)).toBe(true);

    // 2. Realtime voice transcripts arrive while consult is active
    expect(enqueueRelayVoiceTranscript(relay, "user", "Wait, check Thursday instead")).toBe(true);
    expect(enqueueRelayVoiceTranscript(relay, "assistant", "Checking Thursday")).toBe(true);
    expect(barrier?.heldCount).toBe(2);

    // 3. Embedded agent run adopts the keyed turn (does NOT throw!)
    const sessionManager = SessionManager.openBounded(scope, {
      maxBytes: 100_000,
      maxEvents: 100,
    });
    expect(() => sessionManager.appendMessage(consultUserMessage)).not.toThrow();

    sessionManager.appendMessage({
      role: "assistant",
      content: [{ type: "text", text: "You have 1 meeting on Thursday at 2 PM." }],
      api: "chat",
      provider: "test",
      model: "test-model",
      usage: {
        input: 0,
        output: 0,
        cacheRead: 0,
        cacheWrite: 0,
        totalTokens: 0,
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
      },
      stopReason: "stop",
      timestamp: Date.now(),
    });

    // 4. Settle the consult tool call
    clearRelayAgentToolCall(relay, callId);
    expect(barrier?.active).toBe(false);

    // 5. Held speech drains into SQLite in FIFO order
    await relay.voiceTranscriptQueue.flush();

    const events = (await loadTranscriptEvents(scope)) as Array<{
      type?: string;
      message?: { role?: string; content?: unknown };
    }>;
    const messages = events.filter((e) => e.type === "message" && e.message).map((e) => e.message!);

    expect(messages).toHaveLength(4);
    expect(messages[0]?.role).toBe("user");
    expect(extractMessageText(messages[0]?.content)).toBe("What is on the calendar tomorrow?");
    expect(messages[1]?.role).toBe("assistant");
    expect(extractMessageText(messages[1]?.content)).toBe(
      "You have 1 meeting on Thursday at 2 PM.",
    );
    expect(messages[2]?.role).toBe("user");
    expect(extractMessageText(messages[2]?.content)).toBe("Wait, check Thursday instead");
    expect(messages[3]?.role).toBe("assistant");
    expect(extractMessageText(messages[3]?.content)).toBe("Checking Thursday");

    spy.mockRestore();
  });
});
