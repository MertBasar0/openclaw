// Node service tests cover the node identity the shared platform installers receive.
import { afterEach, describe, expect, it, vi } from "vitest";
import type { GatewayServiceInstallArgs } from "./service.js";

const installed: GatewayServiceInstallArgs[] = [];

// mock-isolation: the real platform installer would register a native service; this one records its arguments.
vi.mock("./service.js", () => ({
  resolveGatewayService: () => ({
    install: async (args: GatewayServiceInstallArgs) => {
      installed.push(args);
    },
  }),
}));

const { resolveNodeService } = await import("./node-service.js");

describe("resolveNodeService", () => {
  afterEach(() => {
    installed.length = 0;
  });

  it("installs a named profile's node under that profile's service name", async () => {
    await resolveNodeService().install({
      env: { HOME: "/home/u", OPENCLAW_PROFILE: "work" },
      environment: { OPENCLAW_STATE_DIR: "/home/u/.openclaw-work" },
      stdout: process.stdout,
      programArguments: ["node", "openclaw.mjs", "node", "run"],
    });

    const [args] = installed;
    for (const env of [args?.env, args?.environment]) {
      expect(env).toMatchObject({
        OPENCLAW_LAUNCHD_LABEL: "ai.openclaw.node.work",
        OPENCLAW_SYSTEMD_UNIT: "openclaw-node-work",
        OPENCLAW_WINDOWS_TASK_NAME: "OpenClaw Node (work)",
        OPENCLAW_SERVICE_KIND: "node",
      });
    }
    expect(args?.environment?.OPENCLAW_STATE_DIR).toBe("/home/u/.openclaw-work");
  });
});
