import { truncateUtf16Safe } from "@openclaw/normalization-core/utf16-slice";
import { redactSensitiveText } from "../logging/redact.js";

type AgentRunTerminalModelRef = { provider: string; model: string };

export type AgentRunTerminalReceipt = {
  runId: string;
  sessionId: string;
  turnId: string;
  requested: AgentRunTerminalModelRef;
  effective: AgentRunTerminalModelRef & { responseModel: string };
  successfulToolNames: string[];
  rerouted: boolean;
  terminalDisposition: "visible" | "not-visible";
};

export function normalizeAgentRunTerminalReceipt(
  value: unknown,
): AgentRunTerminalReceipt | undefined {
  const receipt = value as AgentRunTerminalReceipt | undefined;
  return receipt &&
    typeof receipt.runId === "string" &&
    typeof receipt.sessionId === "string" &&
    typeof receipt.turnId === "string" &&
    receipt.requested &&
    receipt.effective &&
    Array.isArray(receipt.successfulToolNames)
    ? receipt
    : undefined;
}

function formatAgentRunModelRef(value: unknown): string | undefined {
  if (
    typeof value !== "object" ||
    value === null ||
    !("provider" in value) ||
    typeof value.provider !== "string" ||
    !("model" in value) ||
    typeof value.model !== "string"
  ) {
    return undefined;
  }
  const route = redactSensitiveText(`${value.provider}/${value.model}`, { mode: "tools" })
    .replace(/\s+/gu, " ")
    .trim();
  return route ? truncateUtf16Safe(route, 128) : undefined;
}

/** Formats the bounded, secret-free route fact owned by a terminal receipt. */
export function formatAgentRunRouteChange(
  receipt: AgentRunTerminalReceipt | undefined,
  expectedRunId: string,
): string | undefined {
  if (
    receipt?.runId !== expectedRunId ||
    !receipt.rerouted ||
    receipt.terminalDisposition !== "visible"
  ) {
    return undefined;
  }
  const requested = formatAgentRunModelRef(receipt.requested);
  const effective = formatAgentRunModelRef({
    ...receipt.effective,
    model: receipt.effective.responseModel || receipt.effective.model,
  });
  return requested && effective ? `Model route changed: ${requested} → ${effective}.` : undefined;
}
