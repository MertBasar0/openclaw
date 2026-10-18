import { once } from "node:events";
import http, { createServer, type ClientRequest, type RequestOptions } from "node:http";
import https from "node:https";
import { connect, type AddressInfo, type Socket } from "node:net";
import { createNodeProxyAgent } from "openclaw/plugin-sdk/fetch-runtime";
import { rawDataToString } from "openclaw/plugin-sdk/realtime-voice-provider";
import { WebSocketServer } from "openclaw/plugin-sdk/websocket-runtime";
import { afterEach, describe, expect, it, vi } from "vitest";
import { openAIRealtimeHost } from "./realtime-host.js";
import { OpenAIQuicksilverGatewayBridge } from "./realtime-quicksilver-gateway-bridge.js";
import { createOpenAIQuicksilverBrowserSessionBroker } from "./realtime-quicksilver-session.js";
import {
  createCallResponse,
  createRequest,
  createResponseHarness,
} from "./realtime-quicksilver.test-helpers.js";
import { buildOpenAIRealtimeVoiceProvider } from "./realtime-voice-provider.js";

const closers: Array<() => Promise<void> | void> = [];

afterEach(async () => {
  try {
    for (const close of closers.splice(0).toReversed()) {
      await close();
    }
  } finally {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  }
});

// Gateway-isolate sockets get no agent of their own: they rely on the managed
// proxy hooks below, which Bun's built-in adapter for a bare `ws` import skips.
describe("OpenAI realtime sockets under the managed proxy", () => {
  it("tunnels the realtime voice bridge through the managed proxy", async () => {
    const target = await startRealtimeTarget();
    const proxy = await startForwardProxy(true);
    routeNodeHttpThroughProxy(proxy.url);
    // Only the proxy reaches this host, like api.openai.com behind egress restrictions.
    const authority = `realtime.openai.test:${target.port}`;
    const bridge = buildOpenAIRealtimeVoiceProvider().createBridge({
      providerConfig: {
        apiKey: "test-realtime-key",
        baseUrl: `ws://${authority}/v1/realtime`,
      },
      onAudio: vi.fn(),
      onClearAudio: vi.fn(),
    });
    closers.push(() => bridge.close());

    await bridge.connect();

    expect(bridge.isConnected()).toBe(true);
    expect(proxy.connects).toEqual([authority]);
    expect(target.authorizations).toEqual(["Bearer test-realtime-key"]);
  }, 10_000);

  it("offers the browser session sideband only to the managed proxy", async () => {
    const proxy = await startForwardProxy(false);
    routeNodeHttpThroughProxy(proxy.url);
    const realtime = createOpenAIQuicksilverBrowserSessionBroker(
      {
        getConfig: () => ({}),
        logger: { debug: vi.fn(), warn: vi.fn() },
        fetchImpl: vi.fn(async () => createCallResponse()),
      },
      openAIRealtimeHost,
    );
    closers.push(() => realtime.cleanup());
    const reservation = await realtime.broker.createBrowserSession(
      {
        providerConfig: {},
        model: "gpt-live-test-canary",
        runAgentConsult: vi.fn(async () => ({ text: "Done" })),
      },
      { type: "api-key", token: "platform-key" },
    );
    if (reservation.transport !== "webrtc") {
      throw new Error("Expected WebRTC reservation");
    }
    const response = createResponseHarness();

    await realtime.handler(createRequest({ token: reservation.clientSecret }), response.res);

    // A refused tunnel fails the offer; there is no direct sideband retry.
    expect(response.res.statusCode).toBe(502);
    expect(proxy.connects.length).toBeGreaterThan(0);
    expect(new Set(proxy.connects)).toEqual(new Set(["api.openai.com:443"]));
  }, 15_000);

  it("offers the gateway relay sideband only to the managed proxy", async () => {
    const proxy = await startForwardProxy(false);
    routeNodeHttpThroughProxy(proxy.url);
    const bridge = new OpenAIQuicksilverGatewayBridge(
      {
        providerConfig: {},
        model: "gpt-live-test-canary",
        audioFormat: { encoding: "pcm16", sampleRateHz: 24_000, channels: 1 },
        onAudio: vi.fn(),
        onClearAudio: vi.fn(),
        logger: { debug: vi.fn(), warn: vi.fn() },
        runAgentConsult: vi.fn(async () => ({ text: "done" })),
        resolveAuth: async () => ({ type: "oauth", token: "oauth-token", accountId: "account-1" }),
        createPeer: vi.fn(async () => ({
          createOffer: vi.fn(async () => "v=offer\r\n"),
          applyAnswer: vi.fn(async () => undefined),
          adoptPendingAudio: vi.fn(),
          sendAudio: vi.fn(),
          close: vi.fn(),
        })),
        fetchImpl: vi.fn<typeof fetch>(async () =>
          createCallResponse("v=answer\r\n", "rtc_bridge"),
        ),
      },
      openAIRealtimeHost,
    );
    closers.push(() => bridge.close());

    await expect(bridge.connect()).rejects.toThrow();

    expect(proxy.connects.length).toBeGreaterThan(0);
    expect(new Set(proxy.connects)).toEqual(new Set(["api.openai.com:443"]));
  }, 15_000);
});

// Mirrors the managed proxy's Gateway-isolate hooks: every node:http(s) request
// gets a proxy agent, and the caller's direct createConnection is dropped.
function routeNodeHttpThroughProxy(proxyUrl: string): void {
  for (const key of ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]) {
    vi.stubEnv(key, undefined);
  }
  vi.stubEnv("OPENCLAW_DEBUG_PROXY_ENABLED", undefined);
  for (const [module, protocol] of [
    [http, "http"],
    [https, "https"],
  ] as const) {
    const request = module.request;
    vi.spyOn(module, "request").mockImplementation(((
      options: RequestOptions,
      callback?: (response: http.IncomingMessage) => void,
    ): ClientRequest => {
      const agent = createNodeProxyAgent({ mode: "explicit", proxyUrl, protocol });
      const { createConnection: _direct, ...routed } = options;
      const routedRequest = request({ ...routed, agent }, callback);
      routedRequest.once("close", () => agent.destroy());
      return routedRequest;
    }) as typeof module.request);
  }
}

async function startRealtimeTarget() {
  const server = new WebSocketServer({ host: "127.0.0.1", port: 0 });
  const authorizations: string[] = [];
  server.on("connection", (socket, request) => {
    authorizations.push(request.headers.authorization ?? "");
    socket.on("message", (data) => {
      const event = JSON.parse(rawDataToString(data)) as { type?: string };
      if (event.type === "session.update") {
        socket.send(JSON.stringify({ type: "session.updated" }));
      }
    });
  });
  await once(server, "listening");
  closers.push(
    () =>
      new Promise<void>((resolve) => {
        for (const client of server.clients) {
          client.terminate();
        }
        server.close(() => resolve());
      }),
  );
  return { port: (server.address() as AddressInfo).port, authorizations };
}

async function startForwardProxy(admit: boolean) {
  const connects: string[] = [];
  const sockets = new Set<Socket>();
  const server = createServer((_request, response) => response.writeHead(405).end());
  server.on("connection", (socket) => sockets.add(socket));
  server.on("connect", (request, client: Socket, head: Buffer) => {
    const authority = request.url ?? "";
    connects.push(authority);
    if (!admit) {
      client.end("HTTP/1.1 403 Forbidden\r\n\r\n");
      return;
    }
    const upstream = connect(Number(authority.split(":").at(-1)), "127.0.0.1", () => {
      client.write("HTTP/1.1 200 Connection Established\r\n\r\n");
      upstream.write(head);
      upstream.pipe(client);
      client.pipe(upstream);
    });
    sockets.add(upstream);
    upstream.on("error", () => client.destroy());
    client.on("error", () => upstream.destroy());
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  closers.push(
    () =>
      new Promise<void>((resolve) => {
        for (const socket of sockets) {
          socket.destroy();
        }
        server.close(() => resolve());
      }),
  );
  return { connects, url: `http://127.0.0.1:${(server.address() as AddressInfo).port}` };
}
