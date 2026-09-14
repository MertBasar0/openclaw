// Recovery cleanup is addressed by session key *and* session id, and neither is
// exclusive over time. These cover the two ways ownership can move between the
// moment a cleanup is scheduled and the moment it acts.
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  abortAndDrainEmbeddedAgentRun,
  isEmbeddedAgentRunHandleActive,
  setActiveEmbeddedRun,
} from "../agents/embedded-agent-runner/runs.js";
import { testing as embeddedRunTesting } from "../agents/embedded-agent-runner/runs.test-support.js";
import {
  createReplyOperation,
  resolveActiveReplyRunSessionId,
} from "../auto-reply/reply/reply-run-registry.js";
import { testing as replyRunTesting } from "../auto-reply/reply/reply-run-registry.test-support.js";
import { resetCommandQueueStateForTest } from "../process/command-queue.test-support.js";
import { resetDiagnosticStateForTest } from "./diagnostic.test-support.js";

describe("stuck session recovery owner lineage", () => {
  afterEach(() => {
    embeddedRunTesting.resetActiveEmbeddedRuns();
    replyRunTesting.resetReplyRunRegistry();
    resetCommandQueueStateForTest();
    resetDiagnosticStateForTest();
  });

  it("leaves a successor admitted under the same key with a new session id running", async () => {
    // Resolving the owner by key alone reaches whoever holds the key *now*. Once an
    // execution ends, the same conversation can admit a new one under a different
    // session id, and a late sweep still carrying the old id would expire it.
    const endedSessionId = "cron-sweep-ended-session";
    const successorSessionId = "cron-sweep-successor-session";
    const sharedKey = "agent:main:dm-successor";

    const successor = createReplyOperation({
      sessionKey: sharedKey,
      sessionId: successorSessionId,
      resetTriggered: false,
    });
    const successorCancel = vi.fn<(reason?: string) => void>(() => successor.complete());
    successor.attachBackend({
      kind: "embedded",
      cancel: successorCancel,
      isStreaming: () => true,
    });
    successor.setPhase("running");

    // The delayed cleanup still names the execution that already ended.
    const result = await abortAndDrainEmbeddedAgentRun({
      sessionId: endedSessionId,
      sessionKey: sharedKey,
      settleMs: 50,
      forceClear: true,
      reason: "cron_timeout",
    });

    expect(successorCancel).not.toHaveBeenCalled();
    expect(successor.phase).toBe("running");
    expect(successor.staleExpiryReason).toBeUndefined();
    // The successor keeps the slot it was legitimately admitted into.
    expect(resolveActiveReplyRunSessionId(sharedKey)).toBe(successorSessionId);
    expect(result.aborted).toBe(false);
  });

  it("does not abort a replacement that claims the session id while the owner is expiring", async () => {
    // Expiry can complete the owner synchronously, and the helper then yields at
    // setImmediate before the id-addressed abort. A replacement registered during
    // that window must not inherit cancellation aimed at the owner it replaced.
    const sessionId = "replacement-during-expiry-session";
    const ownerKey = "agent:main:dm-expiring-owner";

    const replacementAbort = vi.fn<() => void>();
    const replacementHandle = {
      queueMessage: async () => {},
      isStreaming: () => true,
      isCompacting: () => false,
      abort: replacementAbort,
    };

    const owner = createReplyOperation({
      sessionKey: ownerKey,
      sessionId,
      resetTriggered: false,
    });
    const ownerCancel = vi.fn<(reason?: string) => void>(() => {
      owner.complete();
      // Successor work takes the freed session id before the abort below runs.
      setActiveEmbeddedRun(sessionId, replacementHandle, "agent:main:dm-replacement");
    });
    owner.attachBackend({ kind: "embedded", cancel: ownerCancel, isStreaming: () => true });
    owner.setPhase("running");

    await abortAndDrainEmbeddedAgentRun({
      sessionId,
      sessionKey: ownerKey,
      settleMs: 50,
      forceClear: true,
      reason: "cron_timeout",
    });

    // The owner we named is still cancelled; only the replacement is spared.
    expect(ownerCancel).toHaveBeenCalled();
    expect(replacementAbort).not.toHaveBeenCalled();
    expect(isEmbeddedAgentRunHandleActive(sessionId)).toBe(true);
  });
});
