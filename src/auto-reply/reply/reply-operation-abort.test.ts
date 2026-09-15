import { describe, expect, it } from "vitest";
import {
  createSessionPlacementSettlementClosedAbortError,
  FailoverError,
} from "../../agents/failover-error.js";
import {
  createAgentRunDirectAbortError,
  createAgentRunRestartAbortError,
  createAgentRunSupersededAbortError,
} from "../../agents/run-termination.js";
import {
  isReplyOperationSuperseded,
  resolveReplyOperationAbortReason,
  resolveReplyOperationTerminationFields,
} from "./reply-operation-abort.js";
import type { ReplyOperation } from "./reply-run-registry.js";

describe("reply-operation-abort", () => {
  it("resolves superseded for session placement settlement closed abort error", () => {
    const error = createSessionPlacementSettlementClosedAbortError();
    expect(resolveReplyOperationAbortReason(undefined, error)).toBe("superseded");
  });

  it("resolves superseded for session placement settlement closed wrapped in cause", () => {
    const error = new Error("wrapper", {
      cause: createSessionPlacementSettlementClosedAbortError(),
    });
    expect(resolveReplyOperationAbortReason(undefined, error)).toBe("superseded");
  });

  it("resolves superseded for session placement settlement closed in fallback summary error", () => {
    const closedError = createSessionPlacementSettlementClosedAbortError();
    const summaryError = new FailoverError("All models failed", {
      reason: "unknown",
      attempts: [
        {
          provider: "p1",
          model: "m1",
          error: closedError,
        },
      ],
      soonestCooldownExpiry: null,
    });
    expect(resolveReplyOperationAbortReason(undefined, summaryError)).toBe("superseded");
  });

  it("resolves superseded for agent run superseded abort error", () => {
    const error = createAgentRunSupersededAbortError();
    expect(resolveReplyOperationAbortReason(undefined, error)).toBe("superseded");
  });

  it("resolves superseded when replyOperation abort signal holds session placement settlement closed", () => {
    const controller = new AbortController();
    controller.abort(createSessionPlacementSettlementClosedAbortError());
    const replyOp = { abortSignal: controller.signal } as unknown as ReplyOperation;
    expect(isReplyOperationSuperseded(replyOp)).toBe(true);
    expect(resolveReplyOperationAbortReason(replyOp)).toBe("superseded");
  });

  it("resolves superseded when replyOperation is marked aborted_for_supersession", () => {
    const replyOp = {
      result: { kind: "aborted", code: "aborted_for_supersession" },
    } as unknown as ReplyOperation;
    expect(isReplyOperationSuperseded(replyOp)).toBe(true);
    expect(resolveReplyOperationAbortReason(replyOp)).toBe("superseded");
  });

  it("resolves restart for restart abort error", () => {
    const error = createAgentRunRestartAbortError();
    expect(resolveReplyOperationAbortReason(undefined, error)).toBe("restart");
  });

  it("resolves user for direct agent abort error", () => {
    const error = createAgentRunDirectAbortError();
    expect(resolveReplyOperationAbortReason(undefined, error)).toBe("user");
  });

  it("returns undefined for genuine provider errors", () => {
    const providerError = new FailoverError("Rate limit exceeded", {
      reason: "rate_limit",
      status: 429,
    });
    expect(resolveReplyOperationAbortReason(undefined, providerError)).toBeUndefined();
  });

  it("resolves termination fields with superseded stopReason on closed settlement error", () => {
    const error = createSessionPlacementSettlementClosedAbortError();
    const fields = resolveReplyOperationTerminationFields(error, undefined, undefined);
    expect(fields).toEqual({
      aborted: true,
      stopReason: "superseded",
    });
  });
});
