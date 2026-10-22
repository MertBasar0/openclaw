import {
  NODE_SERVICE_KIND,
  resolveGatewayProfileSuffix,
  resolveNodeServiceIdentityEnvironment,
} from "./constants.js";
import type { GatewayServiceEnv } from "./service-types.js";
import type { GatewayService, GatewayServiceInstallArgs } from "./service.js";
import { resolveGatewayService } from "./service.js";

function withNodeServiceEnv(
  env: Record<string, string | undefined>,
): Record<string, string | undefined> {
  // Node services reuse gateway platform installers; env overrides select the
  // node-specific labels, logs, task script, and service marker.
  return {
    ...env,
    ...resolveNodeServiceIdentityEnvironment(env),
  };
}

function withNodeInstallEnv(args: GatewayServiceInstallArgs): GatewayServiceInstallArgs {
  const identity = resolveNodeServiceIdentityEnvironment(args.env);
  return {
    ...args,
    env: { ...args.env, ...identity },
    environment: { ...args.environment, ...identity },
  };
}

export function resolveNodeService(): GatewayService {
  const base = resolveGatewayService("node");
  const { hasInstalledDefinition, isAbsent, readDefinitionMutationCapability } = base;
  // A profile node name can equal another profile's legacy Gateway name (profile
  // work's openclaw-node-work.service is profile node-work's legacy unit). Under
  // the mutation lock and before native effects, refuse a readable definition
  // that is not marked as a node. Unmarked default-profile definitions and
  // unreadable ones keep their existing behavior and native inspection.
  const owned = <TArgs extends { env: GatewayServiceEnv; beforeMutation?: () => Promise<void> }>(
    args: TArgs,
  ): TArgs => ({
    ...args,
    beforeMutation: async () => {
      await args.beforeMutation?.();
      const command = await base.readCommand(args.env).catch(() => null);
      const kind = command?.environment?.OPENCLAW_SERVICE_KIND?.trim();
      const profiled = Boolean(resolveGatewayProfileSuffix(args.env.OPENCLAW_PROFILE));
      if (command && kind !== NODE_SERVICE_KIND && (kind || profiled)) {
        throw new Error(
          `${command.sourcePath ?? "The selected service"} is not an OpenClaw node service, so node commands left it unchanged. It may be another profile's legacy Gateway; move or remove it before managing this profile's node.`,
        );
      }
    },
  });
  return {
    ...base,
    stage: (args) => base.stage(owned(withNodeInstallEnv(args))),
    install: (args) => base.install(owned(withNodeInstallEnv(args))),
    uninstall: (args) => base.uninstall(owned({ ...args, env: withNodeServiceEnv(args.env) })),
    start: (args) => base.start(owned({ ...args, env: withNodeServiceEnv(args.env ?? {}) })),
    stop: (args) => base.stop(owned({ ...args, env: withNodeServiceEnv(args.env ?? {}) })),
    restart: (args) => base.restart(owned({ ...args, env: withNodeServiceEnv(args.env ?? {}) })),
    isLoaded: (args) => {
      // Preserve the status read deadline so node probes fail soft under a
      // wedged service manager instead of hanging the whole status command.
      return base.isLoaded({ env: withNodeServiceEnv(args.env ?? {}), timeoutMs: args.timeoutMs });
    },
    hasInstalledDefinition: hasInstalledDefinition
      ? (args) => hasInstalledDefinition({ ...args, env: withNodeServiceEnv(args.env ?? {}) })
      : undefined,
    isAbsent: isAbsent
      ? (args) => isAbsent({ ...args, env: withNodeServiceEnv(args.env ?? {}) })
      : undefined,
    readDefinitionMutationCapability: readDefinitionMutationCapability
      ? (args) =>
          readDefinitionMutationCapability({
            ...args,
            env: withNodeServiceEnv(args.env ?? {}),
            environment: args.environment ? withNodeServiceEnv(args.environment) : undefined,
          })
      : undefined,
    readCommand: (env, opts) => base.readCommand(withNodeServiceEnv(env), opts),
    readRuntime: (env, opts) => base.readRuntime(withNodeServiceEnv(env), opts),
  };
}
