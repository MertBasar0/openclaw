import { randomUUID } from "node:crypto";
import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { isRecord } from "@openclaw/normalization-core/record-coerce";
import { assert, expect, it, onTestFinished, vi } from "vitest";
import { writeOpenAiResponsesText } from "../../test/helpers/openai-responses-sse.js";
import { createDeferred, withTestTimeout } from "../../test/helpers/promise.js";
import { useAutoCleanupTempDirTracker } from "../../test/helpers/temp-dir.js";
import { captureEnv } from "../test-utils/env.js";
import { disconnectGatewayClient, startGatewayWithClient } from "./test-helpers.e2e.js";

type ProviderRequest = {
  body: string;
  threadId: string | string[] | undefined;
};

type ReadyThread = {
  threadId: string;
  clientId: string;
  action: string;
};

it.each([
  {
    name: "recovers a settled failure",
    failFirst: true,
    activeSibling: false,
  },
  {
    name: "leaves active siblings alone",
    failFirst: true,
    activeSibling: true,
  },
  {
    name: "reloads a healthy thread",
    failFirst: false,
    activeSibling: false,
  },
])("chat.send $name", { timeout: 180_000 }, async ({ failFirst, activeSibling }) => {
  const dirs = useAutoCleanupTempDirTracker(onTestFinished);
  const root = await fs.realpath(dirs.make("gateway-native-recovery-"));
  const workspace = path.join(root, "workspace");
  const state = path.join(root, "state");
  const plugin = path.join(root, "instruction-plugin");
  await Promise.all([workspace, state, plugin].map((dir) => fs.mkdir(dir, { recursive: true })));
  const instruction = path.join(root, "instructions.txt");
  await fs.writeFile(instruction, "INITIAL_POLICY");
  await fs.writeFile(
    path.join(plugin, "openclaw.plugin.json"),
    JSON.stringify({
      id: "recovery-instructions",
      activation: { onStartup: true },
      configSchema: { type: "object", properties: {}, additionalProperties: false },
    }),
  );
  await fs.writeFile(
    path.join(plugin, "index.js"),
    [
      'const fs = require("node:fs");',
      "module.exports = {",
      '  id: "recovery-instructions",',
      "  register(api) {",
      '    api.on("before_prompt_build", () => ({',
      `      systemPrompt: fs.readFileSync(${JSON.stringify(instruction)}, "utf8"),`,
      "    }));",
      "  },",
      "};",
    ].join("\n"),
  );

  const requests: ProviderRequest[] = [];
  const primaryRequests: ProviderRequest[] = [];
  const siblingReceived = createDeferred<ProviderRequest>();
  const releaseSibling = createDeferred();
  const server = http.createServer((req, res) => {
    if (req.method !== "POST" || req.url !== "/v1/responses") {
      res.writeHead(404).end();
      return;
    }
    let body = "";
    req.setEncoding("utf8");
    req.on("data", (chunk: string) => {
      body += chunk;
    });
    req.on("end", () => {
      const request = { body, threadId: req.headers["thread-id"] };
      requests.push(request);
      if (body.includes("SIBLING_HELD")) {
        siblingReceived.resolve(request);
        void releaseSibling.promise.then(() => {
          writeOpenAiResponsesText(res, {
            text: "SIBLING_COMPLETE",
            messageId: "sibling-message",
            responseId: "sibling-response",
          });
        });
        return;
      }
      primaryRequests.push(request);
      if (failFirst && primaryRequests.length === 1) {
        res.writeHead(400, { "content-type": "application/json" }).end(
          JSON.stringify({
            error: {
              message: "controlled settled failure",
              type: "invalid_request_error",
              code: "invalid_request",
            },
          }),
        );
        return;
      }
      writeOpenAiResponsesText(res, {
        text: primaryRequests.length === 1 ? "INITIAL_REPLY" : "HISTORY_ALPHA NEW_POLICY_BETA",
        messageId: `primary-message-${primaryRequests.length}`,
        responseId: `primary-response-${primaryRequests.length}`,
      });
    });
  });
  onTestFinished(async () => {
    releaseSibling.resolve();
    server.closeAllConnections();
    await new Promise<void>((resolve) => {
      server.close(() => resolve());
    });
  });
  await new Promise<void>((resolve) => {
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  assert(address && typeof address !== "string", "controlled provider must bind a local port");
  const baseUrl = `http://127.0.0.1:${address.port}/v1`;
  const values = {
    HOME: root,
    USERPROFILE: root,
    CODEX_HOME: path.join(root, ".codex"),
    OPENCLAW_STATE_DIR: state,
    OPENCLAW_CONFIG_PATH: path.join(state, "openclaw.json"),
    OPENCLAW_GATEWAY_TOKEN: "synthetic-recovery-token",
    OPENCLAW_TEST_MINIMAL_GATEWAY: "0",
    OPENCLAW_AGENT_RUNTIME: "codex",
    OPENCLAW_SKIP_CHANNELS: "1",
    OPENCLAW_SKIP_GMAIL_WATCHER: "1",
    OPENCLAW_SKIP_CRON: "1",
    OPENCLAW_SKIP_CANVAS_HOST: "1",
    OPENCLAW_SKIP_BROWSER_CONTROL_SERVER: "1",
    OPENCLAW_SKIP_PROVIDERS: "0",
    OPENCLAW_DISABLE_BUNDLED_PLUGINS: "0",
    OPENCLAW_BUNDLED_PLUGINS_DIR: path.join(process.cwd(), "extensions"),
    OPENCLAW_TEST_TRUST_BUNDLED_PLUGINS_DIR: "1",
    HTTP_PROXY: "http://127.0.0.1:9",
    HTTPS_PROXY: "http://127.0.0.1:9",
    ALL_PROXY: "http://127.0.0.1:9",
    NO_PROXY: "127.0.0.1,localhost,::1",
  };
  const env = captureEnv(Object.keys(values));
  Object.assign(process.env, values);
  onTestFinished(() => env.restore());
  const model = "gpt-5.5";
  const cfg = {
    gateway: {
      mode: "local",
      auth: { mode: "token", token: values.OPENCLAW_GATEWAY_TOKEN },
      controlUi: { enabled: false },
    },
    agents: {
      defaults: {
        workspace,
        skipBootstrap: true,
        utilityModel: "",
        heartbeat: { every: "0m" },
        model: { primary: `openai/${model}` },
        models: { [`openai/${model}`]: { agentRuntime: { id: "codex" } } },
        maxConcurrent: 2,
        timeoutSeconds: 60,
      },
    },
    models: {
      mode: "replace",
      providers: {
        openai: {
          baseUrl: "https://api.openai.com/v1",
          apiKey: "synthetic-local-only",
          api: "openai-responses",
          models: [
            {
              id: model,
              name: "Synthetic model",
              reasoning: false,
              input: ["text"],
              cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
              contextWindow: 128000,
              maxTokens: 1024,
            },
          ],
        },
      },
    },
    plugins: {
      allow: ["codex", "openai", "recovery-instructions"],
      load: { paths: [plugin] },
      entries: {
        codex: {
          enabled: true,
          config: {
            appServer: {
              args: [
                "app-server",
                "--listen",
                "stdio://",
                "-c",
                `openai_base_url="${baseUrl}"`,
                "-c",
                "analytics.enabled=false",
                "-c",
                "feedback.enabled=false",
                "-c",
                "features.shell_snapshot=false",
              ],
            },
          },
        },
        openai: { enabled: true },
        "recovery-instructions": {
          enabled: true,
          hooks: { allowPromptInjection: true, allowConversationAccess: true },
        },
      },
    },
  };
  const readyThreads = new Map<string, ReadyThread>();
  const gateway = await startGatewayWithClient({
    cfg,
    configPath: values.OPENCLAW_CONFIG_PATH,
    token: values.OPENCLAW_GATEWAY_TOKEN,
    onEvent: ({ event, payload }) => {
      if (
        event !== "agent" ||
        !isRecord(payload) ||
        payload.stream !== "codex_app_server.lifecycle" ||
        typeof payload.runId !== "string" ||
        !isRecord(payload.data) ||
        payload.data.phase !== "thread_ready"
      ) {
        return;
      }
      const { threadId, clientId, action } = payload.data;
      if (
        typeof threadId === "string" &&
        typeof clientId === "string" &&
        typeof action === "string"
      ) {
        readyThreads.set(payload.runId, { threadId, clientId, action });
      }
    },
  });
  onTestFinished(async () => {
    releaseSibling.resolve();
    await disconnectGatewayClient(gateway.client);
    await gateway.server.close();
  });
  const runPrefix = randomUUID();
  const sessionKey = `agent:main:recovery-proof-${runPrefix}`;
  const siblingSessionKey = `agent:main:recovery-sibling-${runPrefix}`;
  const start = (message: string, idempotencyKey: string, targetSession = sessionKey) =>
    gateway.client.request<{ runId: string }>("chat.send", {
      sessionKey: targetSession,
      message,
      idempotencyKey: `${runPrefix}-${idempotencyKey}`,
      deliver: false,
    });
  const wait = (runId: string) =>
    gateway.client.request<{ status: string; error?: string }>(
      "agent.wait",
      { runId, timeoutMs: 65_000 },
      { timeoutMs: 70_000 },
    );
  const ready = (runId: string) =>
    vi.waitFor(() => {
      const thread = readyThreads.get(runId);
      assert(thread, "chat.send must publish its ready native thread and client");
      return thread;
    });

  const first = await start("Remember HISTORY_ALPHA.", "first");
  const settled = await wait(first.runId);
  expect(settled).toMatchObject({ status: failFirst ? "error" : "ok" });
  if (failFirst) {
    expect(settled.error).toContain("controlled settled failure");
  }
  const previous = await ready(first.runId);
  expect(previous.action).toBe("started");
  expect(primaryRequests).toHaveLength(1);
  expect(primaryRequests[0]).toMatchObject({
    body: expect.stringContaining("INITIAL_POLICY"),
    threadId: previous.threadId,
  });

  let siblingRunId: string | undefined;
  if (activeSibling) {
    const sibling = await start("SIBLING_HELD", "sibling", siblingSessionKey);
    siblingRunId = sibling.runId;
    const received = await withTestTimeout(
      siblingReceived.promise,
      30_000,
      "active sibling did not reach the controlled provider",
    );
    const siblingThread = await ready(sibling.runId);
    expect(siblingThread.clientId).toBe(previous.clientId);
    expect(siblingThread.threadId).not.toBe(previous.threadId);
    expect(received.threadId).toBe(siblingThread.threadId);
  }

  await fs.writeFile(instruction, "NEW_POLICY_BETA");
  if (siblingRunId) {
    for (const key of ["second", "retry"]) {
      const refused = await start("Continue with changed instructions.", key);
      const result = await wait(refused.runId);
      expect(result.status).toBe("error");
      expect(result.error).toContain("did not confirm unloading");
      expect(readyThreads.has(refused.runId)).toBe(false);
    }
    expect(primaryRequests).toHaveLength(1);
    await start("/codex binding", "binding");
    await vi.waitFor(
      async () => {
        const history = await gateway.client.request("chat.history", { sessionKey, limit: 20 });
        expect(JSON.stringify(history)).toContain(`Thread: ${previous.threadId}`);
      },
      { timeout: 10_000 },
    );

    releaseSibling.resolve();
    expect(await wait(siblingRunId)).toMatchObject({ status: "ok" });
    const siblingThread = await ready(siblingRunId);
    await fs.writeFile(instruction, "INITIAL_POLICY");
    const continuedSibling = await start(
      "Continue the sibling.",
      "sibling-next",
      siblingSessionKey,
    );
    expect(await wait(continuedSibling.runId)).toMatchObject({ status: "ok" });
    expect(await ready(continuedSibling.runId)).toMatchObject({
      threadId: siblingThread.threadId,
      clientId: previous.clientId,
    });
    expect(primaryRequests).toHaveLength(1);
    expect(requests).toHaveLength(3);
    return;
  }
  const continued = await start("Continue with changed instructions.", "second");
  expect(await wait(continued.runId)).toMatchObject({ status: "ok" });
  const recovered = await ready(continued.runId);
  expect(recovered.threadId).toBe(previous.threadId);
  expect(recovered.action).toBe("resumed");
  if (failFirst) {
    expect(recovered.clientId).not.toBe(previous.clientId);
  } else {
    expect(recovered.clientId).toBe(previous.clientId);
  }
  expect(primaryRequests).toHaveLength(2);
  expect(primaryRequests[1]).toMatchObject({
    threadId: previous.threadId,
    body: expect.stringContaining("HISTORY_ALPHA"),
  });
  expect(primaryRequests[1]).toMatchObject({ body: expect.stringContaining("NEW_POLICY_BETA") });
  const history = await gateway.client.request("chat.history", { sessionKey, limit: 20 });
  expect(JSON.stringify(history)).toContain("HISTORY_ALPHA NEW_POLICY_BETA");

  expect(requests).toHaveLength(2);
});
