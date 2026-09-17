import { beforeEach, describe, expect, it, vi } from "vitest";
import { createClientVoiceConfirmationReadiness } from "../../../talk/client-voice-confirmation-readiness.js";
import { VOICE_TRANSCRIPT_QUEUE_POLICY } from "../../../talk/voice-transcript.js";
import type { RelaySession } from "./state.js";
import {
  acquireTalkRealtimeRelayVoiceBarrier,
  closeRelayVoiceSession,
  enqueueRelayVoiceTranscript,
  releaseTalkRealtimeRelayVoiceBarrier,
} from "./voice.js";

const voiceSessionMocks = vi.hoisted(() => ({
  appendRelayVoiceTranscript: vi.fn(),
  closeRelayVoiceSessionRecord: vi.fn(),
  createOrResumeClientVoiceSession: vi.fn(),
}));

vi.mock("../../../talk/client-voice-session.js", () => voiceSessionMocks);

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve!: () => void;
  const promise = new Promise<void>((accept) => {
    resolve = accept;
  });
  return { promise, resolve };
}

function createRelaySession(): {
  session: RelaySession;
  failSession: ReturnType<typeof vi.fn>;
} {
  const failSession = vi.fn(() => {
    void closeRelayVoiceSession(session);
  });
  const session = {
    id: "relay-voice-bounded",
    sessionTarget: {
      agentId: "main",
      sessionKey: "main",
      canonicalKey: "agent:main:work",
      storePath: "/tmp/relay-voice-sessions.sqlite",
    },
    provider: "openai",
    context: {
      getRuntimeConfig: () => ({}),
      logGateway: { warn: vi.fn() },
    },
    confirmationReadiness: createClientVoiceConfirmationReadiness({
      agentId: "main",
      voiceSessionId: "relay-voice-bounded",
      flushTranscript: async () => await session.voiceTranscriptQueue.flush(),
    }),
    voiceSessionCreated: false,
    voiceTranscriptSeq: 0,
    voiceTranscriptQueue: VOICE_TRANSCRIPT_QUEUE_POLICY.createQueue(),
    failSession,
  } as unknown as RelaySession;
  return { session, failSession };
}

describe("realtime relay voice transcript persistence", () => {
  beforeEach(() => {
    voiceSessionMocks.appendRelayVoiceTranscript.mockReset();
    voiceSessionMocks.closeRelayVoiceSessionRecord.mockReset().mockResolvedValue(undefined);
    voiceSessionMocks.createOrResumeClientVoiceSession.mockReset();
  });

  it("bounds stalled finals, drains the accepted prefix, and closes once", async () => {
    const firstAppend = deferred();
    voiceSessionMocks.appendRelayVoiceTranscript.mockImplementation(
      async ({ entryId }: { entryId: string }) => {
        if (entryId === "1") {
          await firstAppend.promise;
        }
      },
    );
    const { session, failSession } = createRelaySession();
    let accepted = enqueueRelayVoiceTranscript(session, "user", `  ${"x".repeat(9_000)}  `) ? 1 : 0;

    for (let index = 0; index < 10_000; index += 1) {
      expect(enqueueRelayVoiceTranscript(session, "user", " \t\n ")).toBe(true);
    }

    for (let index = 1; index < 10_000; index += 1) {
      if (
        enqueueRelayVoiceTranscript(
          session,
          index % 2 === 0 ? "user" : "assistant",
          `  ${"x".repeat(9_000)}  `,
        )
      ) {
        accepted += 1;
      }
    }

    expect(accepted).toBe(41);
    expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        agentId: "main",
        sessionKey: "main",
        sessionTarget: {
          sessionKey: "agent:main:work",
          storePath: "/tmp/relay-voice-sessions.sqlite",
        },
      }),
    );
    expect(failSession).toHaveBeenCalledOnce();
    const close = session.voiceSessionClose;
    expect(close).toBeDefined();
    expect(closeRelayVoiceSession(session)).toBe(close);
    expect(voiceSessionMocks.closeRelayVoiceSessionRecord).not.toHaveBeenCalled();

    firstAppend.resolve();
    await close;

    expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenCalledTimes(41);
    expect(
      voiceSessionMocks.appendRelayVoiceTranscript.mock.calls.map(
        ([params]) => (params as { entryId: string }).entryId,
      ),
    ).toEqual(Array.from({ length: 41 }, (_, index) => String(index + 1)));
    expect(
      voiceSessionMocks.appendRelayVoiceTranscript.mock.calls.every(
        ([params]) => (params as { text: string }).text.length === 8_000,
      ),
    ).toBe(true);
    expect(voiceSessionMocks.closeRelayVoiceSessionRecord).toHaveBeenCalledOnce();
    expect(enqueueRelayVoiceTranscript(session, "user", "too late")).toBe(false);
  });

  it("terminally closes the durable record after bounded transcript retries fail", async () => {
    vi.useFakeTimers();
    try {
      voiceSessionMocks.appendRelayVoiceTranscript.mockRejectedValue(
        new Error("transcript write failed"),
      );
      const { session } = createRelaySession();

      expect(enqueueRelayVoiceTranscript(session, "user", "persist me")).toBe(true);
      const close = closeRelayVoiceSession(session);
      await vi.runAllTimersAsync();
      await close;

      expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenCalledTimes(3);
      expect(voiceSessionMocks.closeRelayVoiceSessionRecord).toHaveBeenCalledOnce();
      expect(session.context.logGateway?.warn).toHaveBeenCalledExactlyOnceWith(
        expect.stringContaining("realtime relay transcript append failed"),
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it("holds transcripts during active barrier and drains in FIFO sequence on release", async () => {
    const { session } = createRelaySession();
    const barrier = await acquireTalkRealtimeRelayVoiceBarrier(session, "call-1");
    expect(barrier.active).toBe(true);
    expect(barrier.heldCount).toBe(0);

    expect(enqueueRelayVoiceTranscript(session, "user", "one")).toBe(true);
    expect(enqueueRelayVoiceTranscript(session, "assistant", "two")).toBe(true);
    expect(barrier.heldCount).toBe(2);

    // Writes are held; appendRelayVoiceTranscript has not been called
    expect(voiceSessionMocks.appendRelayVoiceTranscript).not.toHaveBeenCalled();

    // Release barrier
    releaseTalkRealtimeRelayVoiceBarrier(session, "call-1");
    expect(barrier.active).toBe(false);

    await session.voiceTranscriptQueue.flush();
    expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenCalledTimes(2);
    expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ role: "user", text: "one" }),
    );
    expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ role: "assistant", text: "two" }),
    );
  });

  it("coordinates multiple concurrent tool calls under the same barrier", async () => {
    const { session } = createRelaySession();
    const barrier1 = await acquireTalkRealtimeRelayVoiceBarrier(session, "call-a");
    const barrier2 = await acquireTalkRealtimeRelayVoiceBarrier(session, "call-b");
    expect(barrier1).toBe(barrier2);
    expect(barrier1.callIds).toEqual(new Set(["call-a", "call-b"]));

    enqueueRelayVoiceTranscript(session, "user", "during-calls");
    expect(voiceSessionMocks.appendRelayVoiceTranscript).not.toHaveBeenCalled();

    // Releasing call-a leaves barrier active for call-b
    releaseTalkRealtimeRelayVoiceBarrier(session, "call-a");
    expect(barrier1.active).toBe(true);
    expect(voiceSessionMocks.appendRelayVoiceTranscript).not.toHaveBeenCalled();

    // Releasing call-b releases gate
    releaseTalkRealtimeRelayVoiceBarrier(session, "call-b");
    expect(barrier1.active).toBe(false);

    await session.voiceTranscriptQueue.flush();
    expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenCalledOnce();
  });

  it("synchronously reserves ownership on concurrent overlapping acquisitions", async () => {
    const { session } = createRelaySession();
    const [barrier1, barrier2] = await Promise.all([
      acquireTalkRealtimeRelayVoiceBarrier(session, "call-overlap-1"),
      acquireTalkRealtimeRelayVoiceBarrier(session, "call-overlap-2"),
    ]);
    expect(barrier1).toBe(barrier2);
    expect(barrier1.callIds).toEqual(new Set(["call-overlap-1", "call-overlap-2"]));
    expect(barrier1.active).toBe(true);

    enqueueRelayVoiceTranscript(session, "user", "during-overlap");
    expect(voiceSessionMocks.appendRelayVoiceTranscript).not.toHaveBeenCalled();

    releaseTalkRealtimeRelayVoiceBarrier(session, "call-overlap-1");
    expect(barrier1.active).toBe(true);

    releaseTalkRealtimeRelayVoiceBarrier(session, "call-overlap-2");
    expect(barrier1.active).toBe(false);

    await session.voiceTranscriptQueue.flush();
    expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenCalledOnce();
  });

  it("safety timeout releases barrier after 60s", async () => {
    vi.useFakeTimers();
    try {
      const { session } = createRelaySession();
      const barrier = await acquireTalkRealtimeRelayVoiceBarrier(session, "call-timeout");
      expect(barrier.active).toBe(true);

      enqueueRelayVoiceTranscript(session, "user", "will timeout");
      expect(voiceSessionMocks.appendRelayVoiceTranscript).not.toHaveBeenCalled();

      await vi.advanceTimersByTimeAsync(60_000);
      expect(barrier.active).toBe(false);
      expect(session.context.logGateway?.warn).toHaveBeenCalledWith(
        expect.stringContaining("barrier timed out"),
      );

      await session.voiceTranscriptQueue.flush();
      expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
    }
  });

  it("force-releases barrier when heldCount approaches queue capacity", async () => {
    const { session, failSession } = createRelaySession();
    const barrier = await acquireTalkRealtimeRelayVoiceBarrier(session, "call-overflow");
    expect(barrier.active).toBe(true);

    // Enqueue 38 items (maxPendingCount 40 - 2)
    for (let i = 0; i < 38; i++) {
      expect(enqueueRelayVoiceTranscript(session, "user", `msg ${i}`)).toBe(true);
    }

    // Barrier was force-released at threshold
    expect(barrier.active).toBe(false);
    expect(failSession).not.toHaveBeenCalled();
    expect(session.context.logGateway?.warn).toHaveBeenCalledWith(
      expect.stringContaining("barrier reached capacity threshold"),
    );

    // Subsequent enqueue still succeeds
    expect(enqueueRelayVoiceTranscript(session, "assistant", "msg 39")).toBe(true);
    expect(failSession).not.toHaveBeenCalled();

    await session.voiceTranscriptQueue.flush();
    expect(voiceSessionMocks.appendRelayVoiceTranscript).toHaveBeenCalledTimes(39);
  });
});
