import { formatErrorMessage } from "../../../infra/errors.js";
import {
  appendRelayVoiceTranscript,
  closeRelayVoiceSessionRecord,
  createOrResumeClientVoiceSession,
} from "../../../talk/client-voice-session.js";
import {
  normalizeVoiceTranscriptText,
  VOICE_TRANSCRIPT_QUEUE_POLICY,
} from "../../../talk/voice-transcript.js";
import { drainingRelaySessions, relaySessions, type RelaySession } from "./state.js";

const RELAY_TRANSCRIPT_RETRY_DELAYS_MS = [0, 500, 2_000] as const;
const RELAY_VOICE_BARRIER_TIMEOUT_MS = 60_000;

type TalkRealtimeRelayVoiceBarrier = NonNullable<RelaySession["voiceTranscriptBarrier"]>;

type TalkRealtimeRelayVoiceBarrierParams = {
  relaySessionId: string;
  connId: string;
  callId: string;
};

type TalkRealtimeRelayVoiceBarrierReleaseParams = {
  relaySessionId: string;
  connId: string;
  callId?: string;
};

export async function acquireTalkRealtimeRelayVoiceBarrier(
  sessionOrParams: RelaySession | TalkRealtimeRelayVoiceBarrierParams,
  callId?: string,
): Promise<TalkRealtimeRelayVoiceBarrier> {
  let session: RelaySession;
  let targetCallId: string;
  if ("relaySessionId" in sessionOrParams) {
    const found = relaySessions.get(sessionOrParams.relaySessionId);
    if (!found || found.connId !== sessionOrParams.connId) {
      return {
        active: false,
        callId: sessionOrParams.callId.trim(),
        callIds: new Set(sessionOrParams.callId.trim() ? [sessionOrParams.callId.trim()] : []),
        heldCount: 0,
        release: () => {},
      };
    }
    session = found;
    targetCallId = sessionOrParams.callId;
  } else {
    session = sessionOrParams;
    targetCallId = callId ?? "";
  }
  const normalizedCallId = targetCallId.trim();
  const currentBarrier = session.voiceTranscriptBarrier;
  if (currentBarrier?.active) {
    if (normalizedCallId) {
      currentBarrier.callIds.add(normalizedCallId);
    }
    if (currentBarrier.ready) {
      await currentBarrier.ready;
    }
    return currentBarrier;
  }

  if (session.closing || session.voiceTranscriptQueue.didOverflow) {
    return {
      active: false,
      callId: normalizedCallId,
      callIds: new Set(normalizedCallId ? [normalizedCallId] : []),
      heldCount: 0,
      release: () => {},
    };
  }

  let gateResolve!: () => void;
  const gatePromise = new Promise<void>((resolve) => {
    gateResolve = resolve;
  });

  const callIds = new Set<string>(normalizedCallId ? [normalizedCallId] : []);
  let active = true;
  let heldCount = 0;
  let timeoutTimer: NodeJS.Timeout | undefined;

  const release = (releaseCallId?: string) => {
    if (!active) {
      return;
    }
    if (releaseCallId) {
      callIds.delete(releaseCallId.trim());
      if (callIds.size > 0) {
        return;
      }
    }
    active = false;
    if (timeoutTimer) {
      clearTimeout(timeoutTimer);
      timeoutTimer = undefined;
    }
    if (session.voiceTranscriptBarrier === barrier) {
      session.voiceTranscriptBarrier = undefined;
    }
    gateResolve();
  };

  const barrier: TalkRealtimeRelayVoiceBarrier = {
    get active() {
      return active;
    },
    get callId() {
      return normalizedCallId || [...callIds][0] || "";
    },
    callIds,
    get heldCount() {
      return heldCount;
    },
    set heldCount(val: number) {
      heldCount = val;
    },
    release,
  };

  session.voiceTranscriptBarrier = barrier;

  const readyPromise = (async () => {
    try {
      await session.voiceTranscriptQueue.flush();
      if (session.closing || session.voiceTranscriptQueue.didOverflow || !active) {
        release();
        return;
      }
      const admission = session.voiceTranscriptQueue.enqueue(
        async () => {
          await gatePromise;
        },
        { weight: 0, sealOnOverflow: false },
      );
      if (!admission.accepted) {
        release();
      }
    } catch {
      release();
    }
  })();

  barrier.ready = readyPromise;
  await readyPromise;

  if (active) {
    timeoutTimer = setTimeout(() => {
      session.context.logGateway?.warn(
        `realtime voice transcript barrier timed out after ${RELAY_VOICE_BARRIER_TIMEOUT_MS}ms for callId=${normalizedCallId}`,
      );
      release();
    }, RELAY_VOICE_BARRIER_TIMEOUT_MS);
    timeoutTimer.unref?.();
  }

  return barrier;
}

export function releaseTalkRealtimeRelayVoiceBarrier(
  sessionOrParams: RelaySession | TalkRealtimeRelayVoiceBarrierReleaseParams,
  callId?: string,
): void {
  let session: RelaySession | undefined;
  let targetCallId: string | undefined;
  if ("relaySessionId" in sessionOrParams) {
    const found = relaySessions.get(sessionOrParams.relaySessionId);
    if (found && found.connId === sessionOrParams.connId) {
      session = found;
    }
    targetCallId = sessionOrParams.callId;
  } else {
    session = sessionOrParams;
    targetCallId = callId;
  }
  session?.voiceTranscriptBarrier?.release(targetCallId);
}

function logRelayVoiceFailure(session: RelaySession, message: string, error: unknown): void {
  session.context.logGateway?.warn(`${message}: ${formatErrorMessage(error)}`);
}

export function ensureRelayVoiceSession(session: RelaySession): boolean {
  if (session.voiceSessionCreated) {
    return true;
  }
  const { agentId, sessionKey } = session.sessionTarget;
  try {
    createOrResumeClientVoiceSession({
      agentId,
      sessionKey,
      provider: session.provider,
      origin: "relay",
      voiceSessionId: session.id,
    });
    session.voiceSessionCreated = true;
    return true;
  } catch (error) {
    logRelayVoiceFailure(session, "realtime relay voice session create failed", error);
    return false;
  }
}

export function enqueueRelayVoiceTranscript(
  session: RelaySession,
  role: "user" | "assistant",
  text: string,
): boolean {
  const observed =
    role === "user" && !session.closing
      ? session.confirmationReadiness.observeUserTranscript(text, true)
      : undefined;
  const normalizedText = normalizeVoiceTranscriptText(text);
  if (!normalizedText) {
    return true;
  }
  if (!ensureRelayVoiceSession(session)) {
    session.confirmationReadiness.fail(new Error("Realtime voice session could not be recorded"));
    return true;
  }
  const barrier = session.voiceTranscriptBarrier;
  if (barrier?.active) {
    barrier.heldCount += 1;
    if (barrier.heldCount >= VOICE_TRANSCRIPT_QUEUE_POLICY.maxPendingCount - 2) {
      logRelayVoiceFailure(
        session,
        `realtime voice transcript barrier reached capacity threshold (${barrier.heldCount}); force-releasing for callId=${barrier.callId}`,
        new Error("queue capacity threshold reached"),
      );
      barrier.release();
    }
  }
  const transcriptSeq = session.voiceTranscriptSeq + 1;
  const entryId = String(transcriptSeq);
  const { agentId, sessionKey, canonicalKey, storePath } = session.sessionTarget;
  const admission = session.voiceTranscriptQueue.enqueue(
    async () => {
      let lastError: unknown;
      for (const delayMs of RELAY_TRANSCRIPT_RETRY_DELAYS_MS) {
        if (delayMs > 0) {
          await new Promise<void>((resolve) => {
            setTimeout(resolve, delayMs);
          });
        }
        try {
          await appendRelayVoiceTranscript({
            agentId,
            sessionKey,
            sessionTarget: { sessionKey: canonicalKey, storePath },
            voiceSessionId: session.id,
            entryId,
            role,
            text: normalizedText,
            confirmation: observed?.confirmation ?? null,
            ...(session.voiceConfig ? { config: session.voiceConfig } : {}),
          });
          return;
        } catch (error) {
          lastError = error;
        }
      }
      throw lastError;
    },
    { weight: normalizedText.length },
  );
  if (!admission.accepted) {
    session.confirmationReadiness.fail(
      new Error("Realtime voice transcript queue is closed or full"),
    );
    if (admission.reason === "overflow") {
      session.failSession(VOICE_TRANSCRIPT_QUEUE_POLICY.overflowMessage);
    }
    return false;
  }
  session.voiceTranscriptSeq = transcriptSeq;
  void admission.completion.then(observed?.persisted, (error: unknown) => {
    session.confirmationReadiness.fail(error);
    logRelayVoiceFailure(session, "realtime relay transcript append failed", error);
  });
  return true;
}

export function closeRelayVoiceSession(session: RelaySession): Promise<void> {
  session.voiceTranscriptBarrier?.release();
  if (session.voiceSessionClose) {
    return session.voiceSessionClose;
  }
  session.voiceTranscriptQueue.seal();
  if (!ensureRelayVoiceSession(session)) {
    session.voiceSessionClose = Promise.resolve();
    return session.voiceSessionClose;
  }
  const { agentId, sessionKey } = session.sessionTarget;
  session.voiceSessionClose = session.voiceTranscriptQueue
    .flush()
    .then(async () => {
      const config = session.voiceConfig ?? session.context.getRuntimeConfig();
      await closeRelayVoiceSessionRecord({
        agentId,
        sessionKey,
        voiceSessionId: session.id,
        config,
      });
    })
    .catch((error: unknown) => {
      logRelayVoiceFailure(session, "realtime relay voice session close failed", error);
    });
  drainingRelaySessions.add(session);
  void session.voiceSessionClose.finally(() => {
    drainingRelaySessions.delete(session);
  });
  return session.voiceSessionClose;
}
