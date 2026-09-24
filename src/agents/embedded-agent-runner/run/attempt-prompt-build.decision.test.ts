import { Type } from "typebox";
import { afterEach, describe, expect, it, onTestFinished, vi } from "vitest";
import {
  clearRuntimeConfigSnapshot,
  setRuntimeConfigSnapshot,
} from "../../../config/runtime-snapshot.js";
import type { OpenClawConfig } from "../../../config/types.openclaw.js";
import { AgentDefaultsBaseSchema } from "../../../config/zod-schema.agent-defaults-base.js";
import type { DecisionProviderV1, ProviderDecisionOutcome } from "../../../decisions/types.js";
import type { Context, Model } from "../../../llm/types.js";
import { runPluginRegisterSyncInRegistry } from "../../../plugins/loader-module-runtime.js";
import { createPluginRecord } from "../../../plugins/loader-records.js";
import { getPluginInstance } from "../../../plugins/plugin-instance-scope.js";
import { createTestPluginRegistry } from "../../../plugins/registry-runtime.test-helpers.js";
import {
  resetPluginRuntimeStateForTest,
  setActivePluginRegistry,
} from "../../../plugins/runtime.js";
import { prepareSystemAgentRunAdmission } from "../../admitted-run-context.js";
import {
  createAssistant,
  createAssistantResultStream,
  streamMocks,
  createTestSession,
  registerAgentSessionLoopTestLifecycle,
  testModel,
} from "../../sessions/agent-session-loop-correctness.test-support.js";
import { leasePendingAgentSteeringItems } from "../../subagents/registry/subagent-registry.js";
import type { ToolSearchCatalogRef } from "../../tool-search.js";
import { prepareEmbeddedAttemptPromptAssembly } from "./attempt-prompt-build.js";
import { forgetPromptBuildDrainCacheForRun } from "./attempt-prompt-helpers.js";
import { createPromptBuildToolPolicy } from "./attempt-prompt-support.js";
import type { EmbeddedRunAttemptParams } from "./types.js";

vi.mock("../../../plugins/host-hook-state.js", () => ({
  drainPluginNextTurnInjectionContext: vi.fn(async () => ({ queuedInjections: [] })),
}));
vi.mock("../../subagents/registry/subagent-registry.js", () => ({
  leasePendingAgentSteeringItems: vi.fn(async () => undefined),
  prependAgentSteeringPrompt: ({ prompt }: { prompt: string }) => prompt,
}));
registerAgentSessionLoopTestLifecycle();
afterEach(() => {
  resetPluginRuntimeStateForTest();
  clearRuntimeConfigSnapshot();
});
const result = (probabilityTrue = 0.1): ProviderDecisionOutcome => ({
  status: "ok",
  result: {
    model: "model",
    answers: {
      missing_request_context: { type: "boolean", probabilityTrue: 0.1 },
      next_response_needs_tools: { type: "boolean", probabilityTrue },
    },
  },
});
function config(enabled = true, selected = true): OpenClawConfig {
  return {
    agents: {
      defaults: AgentDefaultsBaseSchema.parse({
        experimental: { decisionAssistance: enabled },
        ...(selected ? { decisionModel: "fixture/model" } : {}),
      }),
      entries: { main: {}, quiet: { decisionModel: "" } },
    },
  };
}
function register(evaluate: DecisionProviderV1["evaluate"] = async () => result()) {
  const call = vi.fn(evaluate);
  const builder = createTestPluginRegistry();
  const record = createPluginRecord({
    id: "fixture",
    source: "/synthetic/prefilter.ts",
    origin: "global",
    enabled: true,
    configSchema: false,
    contracts: { decisionProviders: ["fixture"] },
  });
  const api = builder.createApi(record, { config: config() });
  runPluginRegisterSyncInRegistry(
    (registration) =>
      registration.registerDecisionProvider({ id: "fixture", contractVersion: 1, evaluate: call }),
    api,
    builder.registry,
    record.id,
  );
  builder.registry.plugins.push(record);
  setActivePluginRegistry(builder.registry);
  onTestFinished(async () => {
    await getPluginInstance(record)?.dispose();
  });
  return call;
}
let sequence = 0;
async function fixture(
  cfg = config(),
  mode: "structured" | "search" | "code" = "structured",
  agentId = "main",
) {
  const runId = "prefilter-" + ++sequence;
  const tools = ["inspect_file", "message", "decision_evaluate"].map((name) => ({
    name,
    label: name,
    description: name,
    parameters: Type.Object({}),
    execute: async () => ({ content: [{ type: "text" as const, text: "ok" }], details: {} }),
  }));
  const controls = mode === "search" ? ["tool_search"] : mode === "code" ? ["exec"] : [];
  const controlTools = controls.map((name) => ({ ...tools[0]!, name }));
  const { session, sessionManager, modelRegistry } = await createTestSession({
    customTools: [...tools, ...controlTools],
  });
  session.setActiveToolsByName(
    mode === "structured" ? tools.map((t) => t.name) : [...controls, "message"],
  );
  const catalogRef: ToolSearchCatalogRef | undefined =
    mode === "structured"
      ? undefined
      : {
          current: {
            entries: tools
              .filter((t) => t.name !== "message")
              .map((tool) => ({
                id: tool.name,
                name: tool.name,
                source: "openclaw" as const,
                description: tool.description,
                tool,
              })),
            counterScope: runId,
            searchCount: 0,
            describeCount: 0,
            callCount: 0,
          },
        };
  const policy = createPromptBuildToolPolicy({
    session,
    readModelTools: () => session.agent.state.tools,
    effectiveTools: mode === "structured" ? tools : [...controlTools, tools[1]!],
    uncompactedEffectiveTools: tools,
    tools,
    catalogRef,
    codeModeControlsEnabled: mode === "code",
    forceToolNames: ["message", "denied"],
  });
  const admission = prepareSystemAgentRunAdmission(cfg, runId, agentId, "prefilter-test");
  onTestFinished(() => {
    admission.close();
    forgetPromptBuildDrainCacheForRun(runId);
  });
  const controller = new AbortController();
  const attempt: EmbeddedRunAttemptParams = {
    admittedRunContext: await admission.admit("embedded"),
    authStorage: modelRegistry.authStorage,
    authProfileStore: { version: 1, profiles: {} },
    modelRegistry,
    config: cfg,
    model: testModel,
    modelId: testModel.id,
    provider: testModel.provider,
    thinkLevel: "off",
    prompt: "Hello",
    runId,
    sessionId: runId,
    sessionFile: "",
    sessionPersistence: "detached",
    trigger: "user",
    timeoutMs: 10_000,
    workspaceDir: "/synthetic",
    abortSignal: controller.signal,
    supportsTurnScopedToolRestrictions: true,
  };
  const assemble = (overrides: Partial<EmbeddedRunAttemptParams> = {}) =>
    prepareEmbeddedAttemptPromptAssembly({
      attempt: { ...attempt, ...overrides },
      activeSession: session,
      sessionManager,
      hookRunner: null,
      hookAgentId: agentId,
      diagnosticTrace: { traceId: "11111111111111111111111111111111" },
      isRawModelRun: false,
      sessionAgentId: agentId,
      runtimeModel: testModel.id,
      systemPromptText: "System",
      applyPromptBuildToolsAllow: (allow) => policy.apply(allow).callableToolNames,
      setActiveSessionSystemPrompt: () => {},
      setLeasedSteering: () => {},
    });
  return { assemble, session, policy, catalogRef, controller, admission, attempt };
}

describe("prompt assembly with registered Decision runtime", () => {
  it.each([
    [false, false],
    [false, true],
    [true, false],
    [true, true],
  ] as const)("opt-in %s, model %s", async (enabled, selected) => {
    const call = register();
    const f = await fixture(config(enabled, selected));
    await f.assemble();
    expect(call).toHaveBeenCalledTimes(enabled && selected ? 1 : 0);
    expect(f.policy.current.tools.map((t) => t.name)).toEqual(
      enabled && selected ? ["message"] : ["inspect_file", "message", "decision_evaluate"],
    );
    if (enabled && selected) {
      expect(call.mock.calls[0]).toEqual([
        expect.objectContaining({
          state: {
            recentConversation: [],
            latestRequest: "Hello",
            omittedContext: { olderConversation: false, toolPayloads: false },
          },
          questions: {
            missing_request_context: expect.objectContaining({
              type: "boolean",
              instructions: expect.stringContaining("`latestRequest`"),
            }),
            next_response_needs_tools: expect.objectContaining({
              criteria: { true: expect.any(String), false: expect.any(String) },
            }),
          },
        }),
        expect.objectContaining({
          agentId: "main",
          model: "model",
          signal: expect.any(AbortSignal),
          deadlineMonotonicMs: expect.any(Number),
        }),
      ]);
    }
  });
  it.each([undefined, false])(
    "unknown/unsupported harness %s dispatches nothing",
    async (support) => {
      const call = register();
      const f = await fixture();
      await f.assemble({ supportsTurnScopedToolRestrictions: support });
      expect(call).not.toHaveBeenCalled();
      expect(f.policy.current.tools).toHaveLength(3);
    },
  );
  it.each(["structured", "search", "code"] as const)(
    "narrows %s schema/catalog/callability and restores next turn",
    async (mode) => {
      const call = register();
      const f = await fixture(config(), mode);
      await f.assemble();
      expect(f.policy.current.tools.map((t) => t.name)).toEqual(["message"]);
      expect(f.session.getActiveToolNames()).toEqual(["message"]);
      expect(f.catalogRef?.current?.entries ?? []).toEqual([]);
      expect(f.policy.current.callableToolNames).not.toContain("denied");
      call.mockResolvedValue(result(0.9));
      await f.assemble({ prompt: "Read package.json" });
      expect(f.policy.current.tools.map((t) => t.name)).toEqual([
        "inspect_file",
        "message",
        "decision_evaluate",
      ]);
      expect(f.policy.current.callableToolNames).toContain("inspect_file");
    },
  );
  it("keeps another agent's empty override independent", async () => {
    const call = register();
    const quiet = await fixture(config(), "structured", "quiet");
    await quiet.assemble();
    expect(call).not.toHaveBeenCalled();
    expect(quiet.policy.current.tools).toHaveLength(3);
  });
  it.each(["opt-out", "owner-close", "abort"])(
    "fences a pending result after %s",
    async (change) => {
      let release!: () => void;
      let started!: () => void;
      const entered = new Promise<void>((resolve) => {
        started = resolve;
      });
      register(async () => {
        started();
        await new Promise<void>((resolve) => {
          release = resolve;
        });
        return result();
      });
      const cfg = config();
      setRuntimeConfigSnapshot(cfg);
      const f = await fixture(cfg);
      const pending = f.assemble();
      await entered;
      if (change === "opt-out") {
        setRuntimeConfigSnapshot(config(false));
      } else if (change === "owner-close") {
        f.admission.close();
      } else {
        f.controller.abort(new Error("cancelled"));
      }
      release();
      if (change === "opt-out") {
        await pending;
      } else {
        await expect(pending).rejects.toThrow();
      }
      expect(f.policy.current.tools).toHaveLength(3);
    },
  );
  it("retains baseline on provider unavailability and skips continuations", async () => {
    const call = register(async () => ({ status: "unavailable", reason: "transport" }));
    const f = await fixture();
    await f.assemble();
    expect(f.policy.current.tools).toHaveLength(3);
    await f.assemble({ skipPreparedUserTurnMessage: true });
    expect(call).toHaveBeenCalledTimes(1);
  });
  it("observes opt-out published while prompt preparation awaits steering", async () => {
    const call = register();
    const cfg = config();
    setRuntimeConfigSnapshot(cfg);
    const f = await fixture(cfg);
    vi.mocked(leasePendingAgentSteeringItems).mockImplementationOnce(async () => {
      setRuntimeConfigSnapshot(config(false));
      return undefined;
    });
    await f.assemble({ sessionKey: "agent:main:consent-transition" });
    expect(call).not.toHaveBeenCalled();
    expect(f.policy.current.tools).toHaveLength(3);
  });

  it("joins the real runtime deadline and preserves the normal tool surface", async () => {
    let started!: () => void;
    const entered = new Promise<void>((resolve) => {
      started = resolve;
    });
    const call = register(async (_batch, { signal }) => {
      started();
      await new Promise<void>((resolve) => {
        signal.addEventListener("abort", () => resolve(), { once: true });
      });
      return result();
    });
    const f = await fixture();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "performance"] });
    try {
      const pending = f.assemble();
      await entered;
      await vi.advanceTimersByTimeAsync(500);
      await pending;
      expect(call).toHaveBeenCalledOnce();
      expect(f.policy.current.tools).toHaveLength(3);
    } finally {
      vi.useRealTimers();
    }
  });
  it("preserves tools for approvals that depend on earlier assistant work", async () => {
    const call = register();
    const f = await fixture();
    f.session.agent.state.messages = [
      createAssistant(testModel, [{ type: "text", text: "Should I edit the file?" }]),
    ];
    await f.assemble({ prompt: "Go ahead." });
    expect(call).not.toHaveBeenCalled();
    expect(f.policy.current.tools).toHaveLength(3);
  });
  it.each(["structured", "search", "code"] as const)(
    "submits the second-turn restriction and next-action restoration in %s mode",
    async (mode) => {
      const call = register(async () => result(0.9));
      const f = await fixture(config(), mode);
      f.session.agent.state.messages = [];
      const captures: Array<{ names: string[]; definitions: unknown[] }> = [];
      let reply = "Would you like an explanation?";
      streamMocks.streamSimple.mockImplementation((model: Model, context: Context) => {
        captures.push({
          names: (context.tools ?? []).map((tool) => tool.name),
          definitions: (context.tools ?? []).map(({ name, description, parameters }) => ({
            name,
            description,
            parameters,
          })),
        });
        return createAssistantResultStream(createAssistant(model, [{ type: "text", text: reply }]));
      });
      const submit = async (prompt: string) => {
        await f.assemble({ prompt });
        await f.session.prompt(prompt);
      };
      await submit("Help me understand this example.");
      call.mockResolvedValue(result(0.1));
      reply = "Here is the explanation.";
      await submit("Yes");
      expect(call).toHaveBeenCalledTimes(2);
      expect(call.mock.calls[1]?.[0].state).toMatchObject({
        latestRequest: "Yes",
        recentConversation: [
          { user: "Help me understand this example.", assistant: "Would you like an explanation?" },
        ],
      });
      expect(captures[1]?.names).toEqual(["message"]);
      expect(captures[1]?.names).not.toContain("denied");
      expect(JSON.stringify(captures[1]?.definitions).length).toBeLessThan(
        JSON.stringify(captures[0]?.definitions).length,
      );
      call.mockResolvedValue(result(0.9));
      await submit("Read package.json now.");
      expect(call).toHaveBeenCalledTimes(3);
      expect(captures[2]?.names).toEqual(captures[0]?.names);
      expect(f.policy.current.callableToolNames).toContain("inspect_file");
      expect(f.policy.current.callableToolNames).not.toContain("denied");
    },
  );
  it.each([
    ["Help me fix this", "Should I apply the patch?", "Yes", 0.9, false],
    ["Help me understand this", "Would you like an explanation?", "Yes", 0.1, true],
    ["Apply the patch", "The action failed; no changes were made.", "Try again", 0.9, false],
    ["Apply the patch", "The action finished successfully.", "Thanks", 0.1, true],
    [
      "Tell me something interesting",
      "Here is an interesting fact.",
      "Now read package.json",
      0.9,
      false,
    ],
  ] as const)(
    "carries context for %s / %s / %s through the real prompt boundary",
    async (priorUser, priorAssistant, latest, probability, prune) => {
      const call = register(async () => result(0.9));
      const f = await fixture();
      f.session.agent.state.messages = [];
      streamMocks.streamSimple.mockImplementation((model: Model) =>
        createAssistantResultStream(
          createAssistant(model, [{ type: "text", text: priorAssistant }]),
        ),
      );
      await f.assemble({ prompt: priorUser });
      await f.session.prompt(priorUser);
      call.mockResolvedValue(result(probability));
      const submitted: string[][] = [];
      streamMocks.streamSimple.mockImplementation((model: Model, context: Context) => {
        submitted.push((context.tools ?? []).map((tool) => tool.name));
        return createAssistantResultStream(
          createAssistant(model, [{ type: "text", text: "Final response" }]),
        );
      });
      await f.assemble({ prompt: latest });
      await f.session.prompt(latest);
      expect(call).toHaveBeenCalledTimes(2);
      expect(call.mock.calls[1]?.[0].state).toMatchObject({
        latestRequest: latest,
        recentConversation: [{ user: priorUser, assistant: priorAssistant }],
      });
      expect(submitted).toEqual([
        prune ? ["message"] : ["inspect_file", "message", "decision_evaluate"],
      ]);
    },
  );
  it("does not re-evaluate on primary-model fallback", async () => {
    const call = register();
    const f = await fixture();
    await f.assemble();
    await f.assemble({ fallbackActive: true });
    expect(call).toHaveBeenCalledOnce();
    expect(f.policy.current.tools.map((tool) => tool.name)).toEqual([
      "inspect_file",
      "message",
      "decision_evaluate",
    ]);
  });
});
