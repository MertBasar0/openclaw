// Vercel AI Gateway decision provider tests.
import type { DecisionBatch } from "openclaw/plugin-sdk/decisions";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createVercelAiGatewayDecisionProvider } from "./decisions.js";

const batch: DecisionBatch = {
  state: { userMessage: "Test state" },
  questions: {
    bool_q: { type: "boolean", instructions: "Is this valid?" },
    choice_q: {
      type: "choice",
      instructions: "Pick one",
      criteria: { opt_a: "Option A", opt_b: "Option B" },
    },
    score_q: {
      type: "score",
      instructions: "Rate quality",
      criteria: ["poor", "fair", "good"],
    },
  },
};

const createContext = (
  overrides?: Partial<
    Parameters<ReturnType<typeof createVercelAiGatewayDecisionProvider>["evaluate"]>[1]
  >,
) => ({
  model: "typesafe-ai/jev",
  agentId: "test-agent",
  signal: new AbortController().signal,
  deadlineMonotonicMs: performance.now() + 5000,
  ...overrides,
});

describe("vercel ai gateway decision provider", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    delete process.env.AI_GATEWAY_API_KEY;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("reports ready state based on credentials", () => {
    const unconfigured = createVercelAiGatewayDecisionProvider(() => ({}));
    expect(unconfigured.isReady?.()).toBe(false);

    const configured = createVercelAiGatewayDecisionProvider(() => ({ apiKey: "test-key" }));
    expect(configured.isReady?.()).toBe(true);

    process.env.AI_GATEWAY_API_KEY = "env-key";
    expect(unconfigured.isReady?.()).toBe(true);
  });

  it("returns credentials-unavailable when no API key is set", async () => {
    const provider = createVercelAiGatewayDecisionProvider(() => ({}));
    const outcome = await provider.evaluate(batch, createContext());
    expect(outcome).toEqual({
      status: "unavailable",
      reason: "credentials-unavailable",
    });
  });

  it("returns transport when deadline has already expired", async () => {
    const provider = createVercelAiGatewayDecisionProvider(() => ({ apiKey: "test-key" }));
    const outcome = await provider.evaluate(
      batch,
      createContext({ deadlineMonotonicMs: performance.now() - 100 }),
    );
    expect(outcome).toEqual({
      status: "unavailable",
      reason: "transport",
    });
  });

  it("successfully evaluates boolean, choice, and score questions with confidence and usage", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          answers: {
            bool_q: { type: "boolean", probability: 0.12 },
            choice_q: {
              type: "choice",
              choice: "opt_a",
              probabilities: { opt_a: 0.85, opt_b: 0.15 },
            },
            score_q: {
              type: "score",
              score: 2.3,
              probabilities: { "0": 0.05, "1": 0.25, "2": 0.7 },
            },
          },
          usage: { inputTokens: 150, outputTokens: 30 },
          providerMetadata: {
            typesafe: {
              confidence: {
                choice_q: 0.85,
                score_q: 0.7,
              },
            },
          },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );

    const provider = createVercelAiGatewayDecisionProvider(() => ({ apiKey: "test-key" }));
    const outcome = await provider.evaluate(batch, createContext());

    expect(outcome).toEqual({
      status: "ok",
      result: {
        model: "typesafe-ai/jev",
        answers: {
          bool_q: { type: "boolean", probabilityTrue: 0.12 },
          choice_q: {
            type: "choice",
            choice: "opt_a",
            probabilities: { opt_a: 0.85, opt_b: 0.15 },
            confidence: 0.85,
          },
          score_q: {
            type: "score",
            score: 2.3,
            probabilities: [0.05, 0.25, 0.7],
            confidence: 0.7,
          },
        },
        usage: { inputTokens: 150, outputTokens: 30 },
      },
    });

    // Verify request headers
    const fetchMock = vi.mocked(globalThis.fetch);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("https://ai-gateway.vercel.sh/v4/ai/evaluation-model");
    const headers = init?.headers as Record<string, string>;
    expect(headers.authorization).toBe("Bearer test-key");
    expect(headers["ai-evaluation-model-specification-version"]).toBe("4");
    expect(headers["ai-gateway-auth-method"]).toBe("api-key");
    expect(headers["ai-gateway-protocol-version"]).toBe("0.0.1");
    expect(headers["ai-model-id"]).toBe("typesafe-ai/jev");
  });

  it("handles 401 and 403 as authentication failure", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response("Unauthorized", { status: 401 }));

    const provider = createVercelAiGatewayDecisionProvider(() => ({ apiKey: "invalid-key" }));
    const outcome = await provider.evaluate(batch, createContext());

    expect(outcome).toEqual({
      status: "unavailable",
      reason: "authentication",
    });
  });

  it("handles 429 rate limit with retry-after header", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("Rate limited", {
        status: 429,
        headers: { "retry-after": "5" },
      }),
    );

    const provider = createVercelAiGatewayDecisionProvider(() => ({ apiKey: "test-key" }));
    const outcome = await provider.evaluate(batch, createContext());

    expect(outcome).toEqual({
      status: "unavailable",
      reason: "rate-limited",
      retryAfterMs: 5000,
    });
  });

  it("handles 400 as unsupported-input", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response("Bad Request", { status: 400 }));

    const provider = createVercelAiGatewayDecisionProvider(() => ({ apiKey: "test-key" }));
    const outcome = await provider.evaluate(batch, createContext());

    expect(outcome).toEqual({
      status: "unavailable",
      reason: "unsupported-input",
    });
  });

  it("rejects immediately when input exceeds choice bounds without network call", async () => {
    globalThis.fetch = vi.fn();
    const excessiveCriteria: Record<string, string> = {};
    for (let i = 0; i < 256; i++) {
      excessiveCriteria[`opt_${i}`] = `Option ${i}`;
    }

    const provider = createVercelAiGatewayDecisionProvider(() => ({ apiKey: "test-key" }));
    const outcome = await provider.evaluate(
      {
        state: "test",
        questions: {
          huge_choice: { type: "choice", criteria: excessiveCriteria },
        },
      },
      createContext(),
    );

    expect(outcome).toEqual({
      status: "unavailable",
      reason: "unsupported-input",
    });
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("rethrows when signal is aborted", async () => {
    const controller = new AbortController();
    controller.abort();

    const provider = createVercelAiGatewayDecisionProvider(() => ({ apiKey: "test-key" }));
    await expect(
      provider.evaluate(batch, createContext({ signal: controller.signal })),
    ).rejects.toThrow();
  });
});
