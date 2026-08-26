// Restart delivery persistence tests prove that required completion obligations
// survive without a child session and replay only from their frozen payload.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAutoCleanupTempDirTracker } from "../../../../test/helpers/temp-dir.js";
import "./subagent-registry.mocks.shared.js";
import { callGateway } from "../../../gateway/call.js";
import { closeOpenClawStateDatabaseForTest } from "../../../state/openclaw-state-db.js";
import { captureEnv, setTestEnvValue } from "../../../test-utils/env.js";
import { cleanupSessionStateForTest } from "../../../test-utils/session-state-cleanup.js";
import {
  canonicalSubagentRunFixtures,
  createSubagentRegistryTestDeps,
} from "./subagent-registry.persistence.test-support.js";
import {
  loadSubagentRegistryFromSqlite,
  saveSubagentRegistryToSqlite,
} from "./subagent-registry.store.sqlite.js";
import {
  testing,
  activateSubagentRegistry,
  initSubagentRegistry,
  resetSubagentRegistryForTests,
} from "./subagent-registry.test-helpers.js";
import type { SubagentRunRecord } from "./subagent-registry.types.js";

const { announceSpy } = vi.hoisted(() => ({
  announceSpy: vi.fn(async (): Promise<"delivered" | "retryable"> => "delivered"),
}));

vi.mock("../announce/subagent-announce.js", () => ({
  runSubagentAnnounceFlow: announceSpy,
}));

describe("subagent registry restart delivery persistence", () => {
  const envSnapshot = captureEnv(["OPENCLAW_STATE_DIR"]);
  const tempDirTracker = useAutoCleanupTempDirTracker(afterEach);
  let tempStateDir: string | null = null;

  const writePersistedRun = (entry: SubagentRunRecord) => {
    tempStateDir = tempDirTracker.make("openclaw-subagent-delivery-");
    setTestEnvValue("OPENCLAW_STATE_DIR", tempStateDir);
    saveSubagentRegistryToSqlite(canonicalSubagentRunFixtures(new Map([[entry.runId, entry]])));
  };

  const readPersistedRun = (runId: string) => loadSubagentRegistryFromSqlite().get(runId);

  const restartRegistry = () => {
    resetSubagentRegistryForTests({ persist: false });
    initSubagentRegistry();
    const recoveryRuntime = {
      dispatchAgent: (params: Record<string, unknown>, timeoutMs?: number) =>
        callGateway({ method: "agent", params, timeoutMs }),
      waitForAgent: (params: Record<string, unknown>, timeoutMs?: number) =>
        callGateway({ method: "agent.wait", params, timeoutMs }),
      sendRecoveryNotice: vi.fn(),
    };
    activateSubagentRegistry(() => ({ recoveryRuntime }) as never);
  };

  const flushQueuedRegistryWork = async () => {
    await Promise.resolve();
    await Promise.resolve();
  };

  const waitForRegistryWork = async (predicate: () => boolean) => {
    await vi.waitFor(() => expect(predicate()).toBe(true), {
      interval: 1,
      timeout: 5_000,
    });
  };

  const createRequiredDeliveryRun = (status: "pending" | "suspended"): SubagentRunRecord => {
    const now = Date.now();
    const runId = "run-orphan-" + status + "-delivery";
    const childSessionKey = "agent:main:subagent:orphan-" + status + "-delivery";
    const terminalReply = { disposition: "visible" as const, text: "durable final reply" };
    return {
      runId,
      childSessionKey,
      requesterSessionKey: "agent:main:main",
      requesterDisplayKey: "main",
      task: "deliver after restart",
      cleanup: "delete",
      createdAt: now - 100,
      expectsCompletionMessage: true,
      cleanupHandled: false,
      execution: {
        status: "terminal",
        startedAt: now - 50,
        endedAt: now,
        outcome: { status: "ok" },
      },
      completion: {
        required: true,
        resultText: "canonical final reply",
        capturedAt: now,
        terminalReply,
      },
      delivery: {
        status,
        ...(status === "suspended" ? { suspendedAt: now, suspendedReason: "expiry" as const } : {}),
        payload: {
          requesterSessionKey: "agent:main:main",
          requesterDisplayKey: "main",
          childSessionKey,
          childRunId: runId,
          task: "deliver after restart",
          startedAt: now - 50,
          endedAt: now,
          outcome: { status: "ok" },
          expectsCompletionMessage: true,
          terminalReply,
        },
      },
    };
  };

  beforeEach(() => {
    announceSpy.mockReset();
    announceSpy.mockResolvedValue("delivered");
    vi.mocked(callGateway).mockReset();
    vi.mocked(callGateway).mockResolvedValue({
      status: "ok",
      startedAt: 111,
      endedAt: 222,
    });
    testing.setDepsForTest({
      ...createSubagentRegistryTestDeps(),
      persistSubagentRunsToDisk: (runs: Map<string, SubagentRunRecord>) =>
        saveSubagentRegistryToSqlite(runs),
      runSubagentAnnounceFlow: announceSpy,
    });
  });

  afterEach(async () => {
    closeOpenClawStateDatabaseForTest();
    testing.setDepsForTest();
    resetSubagentRegistryForTests({ persist: false });
    await cleanupSessionStateForTest();
    tempStateDir = null;
    envSnapshot.restore();
  });

  it("replays one persisted completion after restart without the child session", async () => {
    const entry = createRequiredDeliveryRun("pending");
    writePersistedRun(entry);

    restartRegistry();
    await waitForRegistryWork(
      () => announceSpy.mock.calls.length === 1 && readPersistedRun(entry.runId) === undefined,
    );

    expect(announceSpy).toHaveBeenCalledOnce();
    expect(announceSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        childSessionKey: entry.childSessionKey,
        childRunId: entry.runId,
        requesterSessionKey: "agent:main:main",
        roundOneReply: "canonical final reply",
        terminalReply: entry.completion?.terminalReply,
        outcome: { status: "ok" },
      }),
    );

    restartRegistry();
    await flushQueuedRegistryWork();
    expect(announceSpy).toHaveBeenCalledOnce();
  });

  it("retains suspended required completion after restart without the child session", async () => {
    const entry = createRequiredDeliveryRun("suspended");
    writePersistedRun(entry);

    restartRegistry();
    await flushQueuedRegistryWork();

    expect(announceSpy).not.toHaveBeenCalled();
    expect(readPersistedRun(entry.runId)).toMatchObject({
      delivery: {
        status: "suspended",
        suspendedAt: entry.delivery?.suspendedAt,
      },
    });
  });
});
