// Vercel AI Gateway typed decision provider implementation.
import type {
  DecisionBatch,
  DecisionBatchResult,
  DecisionProviderV1,
  ProviderDecisionOutcome,
} from "openclaw/plugin-sdk/decisions";
import { buildTimeoutAbortSignal } from "openclaw/plugin-sdk/extension-shared";
import { withTrustedEnvProxyGuardedFetchMode } from "openclaw/plugin-sdk/fetch-runtime";
import { parseRetryAfterHeaderSeconds } from "openclaw/plugin-sdk/retry-runtime";
import { fetchWithSsrFGuard } from "openclaw/plugin-sdk/ssrf-runtime";
import { VERCEL_AI_GATEWAY_BASE_URL } from "./models.js";

const DEFAULT_TIMEOUT_MS = 10_000;
const MAX_CHOICE_OPTIONS = 255;
const MAX_SCORE_LEVELS = 10;
const DEFAULT_DECISION_MODEL = "typesafe-ai/jev";

export type VercelAiGatewayDecisionConfig = {
  apiKey?: string;
  baseUrl?: string;
  timeoutMs?: number;
};

type VercelEvaluationRawAnswer =
  | {
      type: "boolean";
      probability: number;
    }
  | {
      type: "choice";
      choice: string;
      probabilities?: Record<string, number>;
    }
  | {
      type: "score";
      score: number;
      probabilities?: Record<string, number>;
    };

type VercelEvaluationResponseBody = {
  answers?: Record<string, VercelEvaluationRawAnswer>;
  usage?: {
    inputTokens?: number;
    outputTokens?: number;
  };
  providerMetadata?: {
    typesafe?: {
      confidence?: Record<string, number>;
    };
  };
};

export function createVercelAiGatewayDecisionProvider(
  getConfig: () => VercelAiGatewayDecisionConfig,
): DecisionProviderV1 {
  return {
    id: "vercel-ai-gateway",
    contractVersion: 1,
    isReady: () => Boolean(getConfig().apiKey || process.env.AI_GATEWAY_API_KEY),
    async evaluate(batch: DecisionBatch, context): Promise<ProviderDecisionOutcome> {
      context.signal.throwIfAborted();

      const config = getConfig();
      const apiKey = config.apiKey || process.env.AI_GATEWAY_API_KEY;
      if (!apiKey) {
        return { status: "unavailable", reason: "credentials-unavailable" };
      }

      const remainingMs = context.deadlineMonotonicMs - performance.now();
      if (remainingMs <= 0) {
        return { status: "unavailable", reason: "transport" };
      }

      // Validate choice / score bounds before sending
      for (const question of Object.values(batch.questions)) {
        if (question.type === "choice") {
          if (Object.keys(question.criteria).length > MAX_CHOICE_OPTIONS) {
            return { status: "unavailable", reason: "unsupported-input" };
          }
        } else if (question.type === "score") {
          if (question.criteria.length > MAX_SCORE_LEVELS) {
            return { status: "unavailable", reason: "unsupported-input" };
          }
        }
      }

      const timeoutMs = Math.min(config.timeoutMs ?? DEFAULT_TIMEOUT_MS, remainingMs);
      const { signal, cleanup } = buildTimeoutAbortSignal({
        signal: context.signal,
        timeoutMs,
        operation: "Vercel AI Gateway decision evaluation",
      });

      const baseUrl = config.baseUrl ?? VERCEL_AI_GATEWAY_BASE_URL;
      const endpoint = `${baseUrl}/v4/ai/evaluation-model`;
      const model = context.model || DEFAULT_DECISION_MODEL;

      const bodyPayload = JSON.stringify({
        state: batch.state,
        questions: batch.questions,
        providerOptions: {},
      });

      try {
        const guarded = await fetchWithSsrFGuard(
          withTrustedEnvProxyGuardedFetchMode({
            url: endpoint,
            fetchImpl: globalThis.fetch,
            init: {
              method: "POST",
              headers: {
                authorization: `Bearer ${apiKey}`,
                "content-type": "application/json",
                "ai-evaluation-model-specification-version": "4",
                "ai-gateway-auth-method": "api-key",
                "ai-gateway-protocol-version": "0.0.1",
                "ai-model-id": model,
              },
              body: bodyPayload,
              signal,
            },
          }),
        );

        let data: VercelEvaluationResponseBody | undefined;
        let responseStatus: number;
        let responseOk: boolean;
        let retryAfterHeader: string | null;

        try {
          const response = guarded.response;
          responseStatus = response.status;
          responseOk = response.ok;
          retryAfterHeader = response.headers.get("retry-after");

          if (responseOk) {
            // SAFETY: parsed JSON conforms to VercelEvaluationResponseBody and fields are validated at runtime before use.
            data = (await response.json()) as VercelEvaluationResponseBody;
          } else {
            await response.body?.cancel();
          }
        } finally {
          await guarded.release();
        }

        if (!responseOk) {
          if (responseStatus === 401 || responseStatus === 403) {
            return { status: "unavailable", reason: "authentication" };
          }
          if (responseStatus === 429) {
            const seconds = parseRetryAfterHeaderSeconds(retryAfterHeader);
            const retryAfterMs = seconds !== undefined ? seconds * 1000 : undefined;
            return {
              status: "unavailable",
              reason: "rate-limited",
              ...(retryAfterMs !== undefined ? { retryAfterMs } : {}),
            };
          }
          if (responseStatus === 400) {
            return { status: "unavailable", reason: "unsupported-input" };
          }
          return { status: "unavailable", reason: "transport" };
        }

        context.signal.throwIfAborted();

        if (!data || typeof data !== "object" || !data.answers) {
          return { status: "unavailable", reason: "invalid-response" };
        }

        const confidenceMap = data.providerMetadata?.typesafe?.confidence ?? {};
        const answers: Record<string, DecisionBatchResult["answers"][string]> = {};

        for (const [id, rawAnswer] of Object.entries(data.answers)) {
          const question = batch.questions[id];
          if (!question) {
            continue;
          }

          const confidence = typeof confidenceMap[id] === "number" ? confidenceMap[id] : undefined;

          if (rawAnswer.type === "boolean") {
            const prob = typeof rawAnswer.probability === "number" ? rawAnswer.probability : 0.5;
            answers[id] = {
              type: "boolean",
              probabilityTrue: prob,
            };
          } else if (rawAnswer.type === "choice") {
            answers[id] = {
              type: "choice",
              choice: rawAnswer.choice ?? "",
              probabilities: rawAnswer.probabilities ?? {},
              ...(confidence !== undefined ? { confidence } : {}),
            };
          } else if (rawAnswer.type === "score") {
            if (question.type !== "score") {
              return { status: "unavailable", reason: "invalid-response" };
            }
            const probsRecord = rawAnswer.probabilities ?? {};
            const probabilities = question.criteria.map((_level, i) => probsRecord[String(i)] ?? 0);
            answers[id] = {
              type: "score",
              score: rawAnswer.score ?? 0,
              probabilities,
              ...(confidence !== undefined ? { confidence } : {}),
            };
          }
        }

        return {
          status: "ok",
          result: {
            model,
            answers,
            usage: {
              inputTokens: data.usage?.inputTokens,
              outputTokens: data.usage?.outputTokens,
            },
          },
        };
      } catch {
        context.signal.throwIfAborted();
        return { status: "unavailable", reason: "transport" };
      } finally {
        cleanup();
      }
    },
  };
}
