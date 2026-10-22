import fs from "node:fs/promises";
import path from "node:path";
import { PassThrough } from "node:stream";
import { afterEach, expect, it, vi } from "vitest";
import { useAutoCleanupTempDirTracker } from "../../test/helpers/temp-dir.js";
import * as exec from "../process/exec.js";
import { closeOpenClawStateDatabaseForTest } from "../state/openclaw-state-db.js";
import { createPathResolutionEnv, withEnvAsync } from "../test-utils/env.js";
import { withMockedPlatform } from "../test-utils/vitest-spies.js";
import { decodeLaunchAgentPlistFixture } from "./launchd-plist.test-support.js";
import { resolveNodeService } from "./node-service.js";
import { withDaemonRuntimePinMigration } from "./runtime-pin-state.js";
import * as systemd from "./systemd.js";

vi.mock("./launchd-system.js", async (original) => ({
  ...(await original<typeof import("./launchd-system.js")>()),
  assertNoSystemLaunchDaemonOwnership: async () => {},
}));
vi.mock("./systemd.js", async (original) => {
  const actual = await original<typeof import("./systemd.js")>();
  const native = ["stage", "install", "uninstall", "start", "stop", "restart"] as const;
  return {
    ...actual,
    readSystemdServiceExecStart: vi.fn(async () => null),
    ...Object.fromEntries(
      native.map((action) => [`${action}SystemdService`, vi.fn(async () => undefined)]),
    ),
  };
});
vi.mock("./launchd-exec.js", async (original) => ({
  ...(await original<typeof import("./launchd-exec.js")>()),
  execLaunchctl: async () => ({
    code: 113,
    stdout: "",
    stderr: "Could not find service",
    termination: "exit" as const,
  }),
}));

const dirs = useAutoCleanupTempDirTracker(afterEach);
afterEach(() => {
  closeOpenClawStateDatabaseForTest();
  vi.restoreAllMocks();
});

it("stages and reads separate node definitions for two profiles beside the default", async () => {
  // Keep real plist/env-file reads; Linux hosts do not provide native plutil.
  vi.spyOn(exec, "runExec").mockImplementation(async (file, args, options) => {
    if (file !== "/usr/bin/plutil" || typeof options !== "object" || !options.input) {
      throw new Error(`Unexpected native command: ${file}`);
    }
    return decodeLaunchAgentPlistFixture(options.input, args[1]);
  });
  const home = dirs.make("openclaw-node-profiles-");
  const isolatedEnv = createPathResolutionEnv(home, {
    OPENCLAW_STATE_DIR: path.join(home, "state"),
    OPENCLAW_PROFILE: undefined,
  });
  await withEnvAsync(isolatedEnv, async () => {
    // Create private stores on the real host before selecting the launchd adapter.
    await withDaemonRuntimePinMigration(process.env, () => undefined);
    await withMockedPlatform("darwin", async () => {
      const service = resolveNodeService();
      for (const profile of [undefined, "work", "other"]) {
        const env = { ...process.env, OPENCLAW_PROFILE: profile };
        await service.stage({
          env,
          environment: { HOME: home },
          stdout: new PassThrough(),
          programArguments: ["/usr/bin/node", "/opt/openclaw/openclaw.mjs", "node", "run"],
        });
      }
      for (const profile of [undefined, "work", "other"]) {
        const label = profile ? `ai.openclaw.node.${profile}` : "ai.openclaw.node";
        const file = path.join(home, "Library", "LaunchAgents", `${label}.plist`);
        await expect(fs.readFile(file, "utf8")).resolves.toContain(`<string>${label}</string>`);
        const command = await service.readCommand({ ...process.env, OPENCLAW_PROFILE: profile });
        expect(command).toMatchObject({
          sourcePath: file,
          environment: { OPENCLAW_LAUNCHD_LABEL: label },
        });
        expect(command?.environment?.OPENCLAW_PROFILE).toBe(profile);
      }
    });
  });
});

it("leaves another profile's legacy Gateway unit untouched by node mutations", async () => {
  const home = dirs.make("openclaw-node-legacy-gateway-");
  const isolatedEnv = createPathResolutionEnv(home, {
    OPENCLAW_STATE_DIR: path.join(home, "state"),
    OPENCLAW_PROFILE: undefined,
  });
  await withEnvAsync(isolatedEnv, async () => {
    await withDaemonRuntimePinMigration(process.env, () => undefined);
    await withMockedPlatform("linux", async () => {
      const unitPath = path.join(home, ".config/systemd/user/openclaw-node-work.service");
      const read = vi.mocked(systemd.readSystemdServiceExecStart);
      // Profile node-work's legacy Gateway owns the name profile work's node derives.
      read.mockResolvedValue({
        programArguments: ["/usr/bin/node", "/opt/openclaw/openclaw.mjs", "gateway"],
        sourcePath: unitPath,
        environment: {
          OPENCLAW_PROFILE: "node-work",
          OPENCLAW_SERVICE_MARKER: "openclaw",
          OPENCLAW_SERVICE_KIND: "gateway",
        },
      });
      const service = resolveNodeService();
      const args = {
        env: { ...process.env, OPENCLAW_PROFILE: "work" },
        stdout: new PassThrough(),
        programArguments: ["/usr/bin/node", "/opt/openclaw/openclaw.mjs", "node", "run"],
      };
      const native = {
        stage: systemd.stageSystemdService,
        install: systemd.installSystemdService,
        uninstall: systemd.uninstallSystemdService,
        start: systemd.startSystemdService,
        stop: systemd.stopSystemdService,
        restart: systemd.restartSystemdService,
      };
      for (const action of Object.keys(native) as (keyof typeof native)[]) {
        await expect(service[action](args)).rejects.toThrow(
          `${unitPath} is not an OpenClaw node service`,
        );
      }
      expect(read).toHaveBeenCalledWith(
        expect.objectContaining({ OPENCLAW_SYSTEMD_UNIT: "openclaw-node-work" }),
      );
      for (const effect of Object.values(native)) {
        expect(effect).not.toHaveBeenCalled();
      }

      read.mockResolvedValue({
        programArguments: args.programArguments,
        sourcePath: unitPath,
        environment: { OPENCLAW_PROFILE: "work", OPENCLAW_SERVICE_KIND: "node" },
      });
      await service.stop(args);
      expect(native.stop).toHaveBeenCalledTimes(1);
    });
  });
});
