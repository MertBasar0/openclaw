// The forwarding suppression decision belongs to the channel, but the host owns
// the native-route runtime state it needs. This covers the host half: the hint
// must actually reach the adapter, mirroring the local prompt path.
import { describe, expect, it, vi } from "vitest";
import type { ChannelPlugin } from "../channels/plugins/types.public.js";
import type { OpenClawConfig } from "../config/config.js";
import { setActivePluginRegistry } from "../plugins/runtime.js";
import { createChannelTestPluginBase, createTestRegistry } from "../test-utils/channel-plugins.js";
import { createExecApprovalForwarder } from "./exec-approval-forwarder.js";

const CHANNEL = "discord";
const ACCOUNT_ID = "acct-1";

const baseRequest = {
  id: "req-1",
  request: {
    command: "echo hello",
    agentId: "main",
    sessionKey: "agent:main:main",
  },
  createdAtMs: 1_000,
  expiresAtMs: 6_000,
};

describe("exec approval forwarding native-route hint", () => {
  it("passes the resolved native-route state to the channel's suppression hook", async () => {
    const received: Array<{ nativeRouteActive?: boolean }> = [];
    const plugin = {
      ...createChannelTestPluginBase({ id: CHANNEL }),
      approvalCapability: {
        delivery: {
          shouldSuppressForwardingFallback: (params: { nativeRouteActive?: boolean }) => {
            received.push({ nativeRouteActive: params.nativeRouteActive });
            return false;
          },
        },
      },
    } as unknown as ChannelPlugin;
    setActivePluginRegistry(
      createTestRegistry([{ pluginId: CHANNEL, plugin, source: "test" }]) as never,
    );

    const deliver = vi.fn(async () => ({ ok: true }) as never);
    const forwarder = createExecApprovalForwarder({
      getConfig: () =>
        ({ approvals: { exec: { enabled: true, mode: "session" } } }) as OpenClawConfig,
      deliver,
      nowMs: () => 1_000,
      resolveSessionTarget: () => ({ channel: CHANNEL, to: "channel:123", accountId: ACCOUNT_ID }),
    } as never);

    try {
      await forwarder.handleRequested(baseRequest as never);
    } finally {
      await forwarder.stop();
    }

    // No native approval runtime is registered in this process, so the adapter
    // must be told so rather than left to guess from configuration alone.
    expect(received.length).toBeGreaterThan(0);
    expect(received.every((entry) => entry.nativeRouteActive === false)).toBe(true);
  });
});
