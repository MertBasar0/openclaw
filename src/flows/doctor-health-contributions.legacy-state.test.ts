import { beforeEach, expect, it, vi } from "vitest";
import { createDoctorConfigSnapshot } from "../commands/doctor-config-snapshot.test-helpers.js";
import { prepareDoctorConfigMigrationResult } from "../commands/doctor/shared/config-migration-result.js";
import type { LegacyStateMigrationStepReceipt } from "../infra/state-migrations.types.js";
import {
  createDoctorHealthFlowContext,
  createDoctorPrompterFixture,
  resolveDoctorHealthContributions,
} from "./doctor-health-contributions.test-support.js";

const mocks = vi.hoisted(() => ({
  detectLegacyStateMigrations: vi.fn(),
  runLegacyStateMigrations: vi.fn(),
  repairObsoleteGeneratedExecApprovals: vi.fn(() => 0),
  runCoreContributionHealth: vi.fn(async () => undefined),
  note: vi.fn(),
}));

vi.mock("../infra/state-migrations.doctor.js", () => ({
  detectLegacyStateMigrations: mocks.detectLegacyStateMigrations,
  runLegacyStateMigrations: mocks.runLegacyStateMigrations,
}));

vi.mock("../infra/exec-approvals-generated-migration.js", () => ({
  repairObsoleteGeneratedExecApprovals: mocks.repairObsoleteGeneratedExecApprovals,
}));

vi.mock("./doctor-health-contribution-core.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./doctor-health-contribution-core.js")>()),
  runCoreContributionHealth: mocks.runCoreContributionHealth,
}));

vi.mock("../../packages/terminal-core/src/note.js", () => ({
  note: mocks.note,
}));

beforeEach(() => {
  vi.clearAllMocks();
});

it("skips duplicate legacy state detection when preflight settled unchanged config and deduplicates prior notes when rerun", async () => {
  const cfg = { session: { store: "/tmp/shared-sessions.json" } };
  const snapshot = createDoctorConfigSnapshot({ config: cfg });
  const receipts: LegacyStateMigrationStepReceipt[] = [
    {
      id: "migration-detection",
      phase: "preflight",
      source: [],
      target: [],
      requiredness: "required",
      reversibility: "idempotent",
      outcome: "skipped",
      changes: [],
      notices: ["already-noted"],
      warnings: [],
    },
  ];
  const finalize = prepareDoctorConfigMigrationResult(
    {
      snapshot,
      baseConfig: cfg,
      postSessionPluginMigrationPlanBound: true,
      stateMigrationStepReceipts: receipts,
    },
    snapshot,
  );
  const settled = await finalize({
    cfg,
    shouldWriteConfig: false,
    runWithCurrentPluginMetadata: (_c, run) => run(),
  });
  expect(settled.preflightLegacyStateSettled).toBe(true);
  expect(
    (
      await finalize({
        cfg,
        shouldWriteConfig: true,
        runWithCurrentPluginMetadata: (_c, run) => run(),
      })
    ).preflightLegacyStateSettled,
  ).toBeUndefined();

  const contribution = resolveDoctorHealthContributions().find(
    (entry) => entry.id === "doctor:legacy-state",
  )!;
  mocks.repairObsoleteGeneratedExecApprovals.mockReturnValue(1);
  await contribution.run(
    createDoctorHealthFlowContext({
      cfg,
      configResult: { cfg, ...settled },
      prompter: createDoctorPrompterFixture(true),
      options: { nonInteractive: true, repair: true },
    }),
  );
  expect(mocks.runCoreContributionHealth).toHaveBeenCalledWith(expect.anything(), [
    "core/doctor/removed-workspaces-state",
  ]);
  expect(mocks.detectLegacyStateMigrations).not.toHaveBeenCalled();
  expect(mocks.repairObsoleteGeneratedExecApprovals).toHaveBeenCalledOnce();

  mocks.note.mockClear();
  mocks.detectLegacyStateMigrations.mockResolvedValue({
    preview: [],
    warnings: ["already-warned", "new-warning"],
    notices: ["already-noted", "new-notice"],
  });
  await contribution.run(
    createDoctorHealthFlowContext({
      cfg: { ...cfg, gateway: { mode: "local" } },
      configResult: {
        cfg,
        ...settled,
        stateMigrationStepReceipts: [{ ...receipts[0]!, warnings: ["already-warned"] }],
      },
      prompter: createDoctorPrompterFixture(true),
      options: { nonInteractive: true, repair: true },
    }),
  );
  expect(mocks.detectLegacyStateMigrations).toHaveBeenCalledOnce();
  expect(mocks.note).toHaveBeenCalledWith("new-notice", "Doctor notices");
  expect(mocks.note).toHaveBeenCalledWith("new-warning", "Doctor warnings");
  expect(mocks.note).not.toHaveBeenCalledWith(
    expect.stringContaining("already-"),
    expect.anything(),
  );
});
