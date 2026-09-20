// Vercel Ai Gateway plugin entrypoint registers its OpenClaw integration.
import { defineSingleProviderPluginEntry } from "openclaw/plugin-sdk/provider-entry";
import { createVercelAiGatewayDecisionProvider } from "./decisions.js";
import { applyVercelAiGatewayConfig, VERCEL_AI_GATEWAY_DEFAULT_MODEL_REF } from "./onboard.js";
import manifest from "./openclaw.plugin.json" with { type: "json" };
import {
  buildStaticVercelAiGatewayProvider,
  buildVercelAiGatewayProvider,
  resolveVercelAiGatewayModel,
} from "./provider-catalog.js";
import { resolveVercelAiGatewayThinkingProfile } from "./thinking.js";

const PROVIDER_ID = "vercel-ai-gateway";

export default defineSingleProviderPluginEntry({
  id: PROVIDER_ID,
  name: "Vercel AI Gateway Provider",
  description: "Bundled Vercel AI Gateway provider plugin",
  manifest,
  provider: {
    label: "Vercel AI Gateway",
    docsPath: "/providers/vercel-ai-gateway",
    manifestAuth: {
      defaultModel: VERCEL_AI_GATEWAY_DEFAULT_MODEL_REF,
      applyConfig: applyVercelAiGatewayConfig,
    },
    catalog: {
      discoveryMode: "strict",
      buildProvider: () => buildVercelAiGatewayProvider({ discoveryMode: "strict" }),
      buildStaticProvider: buildStaticVercelAiGatewayProvider,
    },
    resolveDynamicModel: ({ modelId }) => resolveVercelAiGatewayModel(modelId),
    resolveThinkingProfile: ({ modelId }) => resolveVercelAiGatewayThinkingProfile(modelId),
  },
  register(api) {
    api.registerDecisionProvider(
      createVercelAiGatewayDecisionProvider(() => {
        // SAFETY: pluginConfig is user-supplied configuration object mapped as a record
        const pluginConfig = (api.pluginConfig ?? {}) as Record<string, unknown>;
        const providerConfig = api.config?.models?.providers?.[PROVIDER_ID];
        const apiKey =
          (typeof pluginConfig.apiKey === "string" && pluginConfig.apiKey.trim()
            ? pluginConfig.apiKey.trim()
            : undefined) ||
          (typeof providerConfig?.apiKey === "string" && providerConfig.apiKey.trim()
            ? providerConfig.apiKey.trim()
            : undefined) ||
          process.env.AI_GATEWAY_API_KEY;
        const baseUrl =
          (typeof pluginConfig.baseUrl === "string" && pluginConfig.baseUrl.trim()
            ? pluginConfig.baseUrl.trim()
            : undefined) ||
          (typeof providerConfig?.baseUrl === "string" && providerConfig.baseUrl.trim()
            ? providerConfig.baseUrl.trim()
            : undefined);
        return {
          apiKey,
          baseUrl,
        };
      }),
    );
  },
});
