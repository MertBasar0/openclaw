import fs from "node:fs/promises";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAutoCleanupTempDirTracker } from "../../test/helpers/temp-dir.js";
import type { RuntimeEnv } from "../runtime.js";
import {
  closeOpenClawAgentDatabasesUnderStateDir,
  openOpenClawAgentDatabase,
} from "../state/openclaw-agent-db.js";
import {
  closeOpenClawStateDatabaseByPath,
  openOpenClawStateDatabase,
} from "../state/openclaw-state-db.js";
import { resolveOpenClawStateSqlitePath } from "../state/openclaw-state-db.paths.js";
import { agentExecCommand } from "./agent-exec.js";

const tempDirs = useAutoCleanupTempDirTracker(afterEach);

function createRuntime(): RuntimeEnv {
  return {
    log: vi.fn(),
    error: vi.fn(),
    exit: vi.fn(),
  };
}

function successResult(text = "ok") {
  return {
    payloads: [{ text }],
    meta: {
      durationMs: 1,
      finalAssistantVisibleText: text,
      agentMeta: {
        sessionId: "cleanup-test-session",
        provider: "proof",
        model: "proof",
      },
    },
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("agent exec temporary SQLite cleanup", () => {
  it("closes temporary agent and shared-state databases before removing their directory", async () => {
    const runtime = createRuntime();
    let observedStateDir = "";
    let stateDatabasePath = "";
    let agentDatabase: ReturnType<typeof openOpenClawAgentDatabase> | undefined;
    let stateDatabase: ReturnType<typeof openOpenClawStateDatabase> | undefined;

    try {
      const result = await agentExecCommand("inspect", {}, runtime, {
        runAgent: vi.fn(async () => {
          observedStateDir = process.env.OPENCLAW_STATE_DIR ?? "";
          stateDatabasePath = resolveOpenClawStateSqlitePath();
          stateDatabase = openOpenClawStateDatabase();
          agentDatabase = openOpenClawAgentDatabase({ agentId: "main" });
          return successResult();
        }),
      });

      expect(result).toMatchObject({ exitCode: 0, envelope: { status: "ok", final: "ok" } });
      expect(agentDatabase?.db.isOpen).toBe(false);
      expect(stateDatabase?.db.isOpen).toBe(false);
      await expect(fs.stat(observedStateDir)).rejects.toMatchObject({ code: "ENOENT" });
    } finally {
      if (observedStateDir) {
        closeOpenClawAgentDatabasesUnderStateDir(observedStateDir);
      }
      if (stateDatabasePath) {
        closeOpenClawStateDatabaseByPath(stateDatabasePath);
      }
      if (observedStateDir) {
        await fs.rm(observedStateDir, { recursive: true, force: true });
      }
    }
  });

  it("leaves process-held databases outside the temporary state directory open", async () => {
    const externalStateDir = tempDirs.make("openclaw-agent-exec-external-state-");
    const externalEnv = { ...process.env, OPENCLAW_STATE_DIR: externalStateDir };
    const externalStateDatabasePath = resolveOpenClawStateSqlitePath(externalEnv);
    const externalStateDatabase = openOpenClawStateDatabase({ env: externalEnv });
    const externalAgentDatabase = openOpenClawAgentDatabase({
      agentId: "external-owner",
      env: externalEnv,
    });
    const runtime = createRuntime();

    try {
      const result = await agentExecCommand("inspect", {}, runtime, {
        runAgent: vi.fn(async () => {
          openOpenClawStateDatabase();
          openOpenClawAgentDatabase({ agentId: "main" });
          return successResult();
        }),
      });

      expect(result.exitCode).toBe(0);
      expect(externalAgentDatabase.db.isOpen).toBe(true);
      expect(externalStateDatabase.db.isOpen).toBe(true);
    } finally {
      closeOpenClawAgentDatabasesUnderStateDir(externalStateDir);
      closeOpenClawStateDatabaseByPath(externalStateDatabasePath);
    }
  });
});
