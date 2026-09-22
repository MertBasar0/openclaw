// Keeps the setup-inference probe's run-registry visibility scoped to its own lifetime.
import { clearAgentRunContext, registerAgentRunContext } from "../infra/agent-run-registry.js";

/**
 * The probe's transcript is throwaway and never durably persisted. Mark its run hidden
 * so its terminal event is not projected as an ordinary chat completion and does not
 * trigger an "agent finished" web-push notification that would open an empty chat.
 * Disposing the returned handle (typically via `using`) clears the registration again.
 */
export function markSetupInferenceProbeHidden(
  runId: string,
  agentId: string,
  sessionKey: string,
): Disposable {
  registerAgentRunContext(runId, {
    agentId,
    sessionKey,
    isControlUiVisible: false,
    projectSessionActive: false,
    projectSessionLifecycle: false,
    projectSessionMessages: false,
  });
  return { [Symbol.dispose]: () => clearAgentRunContext(runId) };
}
