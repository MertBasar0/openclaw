import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAutoCleanupTempDirTracker } from "../../test/helpers/temp-dir.js";
import {
  findPluginCapturedPackage,
  pluginSourceStatIdentity,
  verifyPluginSourceInputs,
  type PluginPackageCapture,
  type PluginSourceInput,
} from "./plugin-package-metadata-capture.js";
import {
  capturePluginSourceDigest,
  capturePluginSourceFile,
  pluginSourceFileContentHash,
} from "./plugin-source-stream-capture.js";

// Larger than the implementation's fixed streaming chunk size (1 MiB) with a partial
// final chunk, so every assertion below genuinely exercises multi-chunk iteration.
const MULTI_CHUNK_BYTES = 3 * 1024 * 1024 + 777;

function multiChunkFixture(): Buffer {
  // A fixed, non-repeating pattern (not zero-filled) so a truncated or reordered
  // stream would change the hash instead of accidentally matching.
  const content = Buffer.allocUnsafe(MULTI_CHUNK_BYTES);
  for (let index = 0; index < content.length; index++) {
    content[index] = (index * 2654435761) & 0xff;
  }
  return content;
}

function expectedWholeBufferDigestHex(content: Buffer): string {
  return createHash("sha256")
    .update(String(content.length))
    .update("\0")
    .update(content)
    .digest("hex");
}

function capturedPackage(root: string, links: string[] = []): PluginPackageCapture {
  return {
    destination: path.resolve(root),
    capturedRoot: path.resolve(root),
    sourceRoot: path.resolve(root),
    links: new Set(links.map((link) => path.resolve(link))),
    state: "body",
    materialize() {},
    captureTarget() {},
  };
}

describe("captured package lookup", () => {
  const directory = path.resolve("fixture");
  it.each([
    { suffix: "", matches: true },
    { suffix: "/lib/module.js", matches: true },
    { suffix: "/./lib/../module.js", matches: true },
    { suffix: "//lib///module.js", matches: true },
    { suffix: "/../outside/module.js", matches: false },
    { suffix: "-other/module.js", matches: false },
    { suffix: "/node_modules", matches: false },
    { suffix: "/lib/node_modules/dependency/module.js", matches: false },
    { suffix: "/node_modules-other/module.js", matches: true },
    { suffix: "/lib/node_modules.js", matches: true },
    { suffix: "/ümlaut/module.js", matches: true },
  ])("preserves package containment for '$suffix'", ({ suffix, matches }) => {
    const owner = capturedPackage("fixture/owner");
    const packages = new Map([[owner.capturedRoot, owner]]);
    const filename = owner.capturedRoot + suffix.replaceAll("/", path.sep);
    expect(findPluginCapturedPackage(packages, filename, directory)).toEqual(
      matches ? { owner, root: owner.capturedRoot } : undefined,
    );
  });

  it("keeps package order and resolves dependency links instead of the enclosing package", () => {
    const parent = capturedPackage("fixture/owner");
    const nested = capturedPackage(path.join(parent.capturedRoot, "lib"));
    const link = path.join(parent.capturedRoot, "node_modules", "@scope", "dependency");
    const dependency = capturedPackage("fixture/dependency", [link]);
    const packages = new Map([
      [parent.capturedRoot, parent],
      [nested.capturedRoot, nested],
      [dependency.capturedRoot, dependency],
    ]);

    expect(
      findPluginCapturedPackage(packages, path.join(nested.capturedRoot, "module.js"), directory),
    ).toEqual({
      owner: parent,
      root: parent.capturedRoot,
    });
    expect(findPluginCapturedPackage(packages, path.join(link, "module.js"), directory)).toEqual({
      owner: dependency,
      root: link,
    });
  });

  it("observes link additions, removals, and package removal on the next lookup", () => {
    const owner = capturedPackage("fixture/owner");
    const link = path.resolve("fixture/late-link");
    const filename = path.join(link, "module.js");
    const packages = new Map([[owner.capturedRoot, owner]]);
    expect(findPluginCapturedPackage(packages, filename, directory)).toBeUndefined();
    owner.links.add(link);
    expect(findPluginCapturedPackage(packages, filename, directory)).toEqual({ owner, root: link });
    owner.links.delete(link);
    expect(findPluginCapturedPackage(packages, filename, directory)).toBeUndefined();
    owner.links.add(link);
    packages.delete(owner.capturedRoot);
    expect(findPluginCapturedPackage(packages, filename, directory)).toBeUndefined();
  });
});

describe("streaming plugin source capture (issue #155728)", () => {
  const temp = useAutoCleanupTempDirTracker(afterEach);
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function readSyncLengths(spy: { mock: { calls: unknown[][] } }): number[] {
    return spy.mock.calls.map((call) => call[3] as number);
  }

  it("streams a multi-chunk source file to its target without a whole-buffer read", () => {
    const boundary = temp.make("plugin-stream-source-");
    const source = path.join(boundary, "asset.bin");
    const content = multiChunkFixture();
    fs.writeFileSync(source, content);
    const target = path.join(temp.make("plugin-stream-target-"), "asset.bin");

    const readFileSyncSpy = vi.spyOn(fs, "readFileSync");
    const readSyncSpy = vi.spyOn(fs, "readSync");
    const result = capturePluginSourceFile({
      source,
      boundary,
      target: { path: target, mode: 0o600 },
    });

    // The whole point of #155728: never buffer the entire file in a single read.
    expect(readFileSyncSpy).not.toHaveBeenCalled();
    expect(readSyncSpy.mock.calls.length).toBeGreaterThan(1);
    for (const length of readSyncLengths(readSyncSpy)) {
      expect(length).toBeLessThanOrEqual(2 * 1024 * 1024);
    }

    expect(result.length).toBe(content.length);
    expect(result.contentHash).toBe(createHash("sha256").update(content).digest("hex"));
    expect(fs.readFileSync(target)).toEqual(content);
  });

  it("feeds an artifact digest without a whole-buffer read, for a fresh or re-aliased entry", () => {
    const boundary = temp.make("plugin-stream-alias-source-");
    const source = path.join(boundary, "asset.bin");
    const content = multiChunkFixture();
    fs.writeFileSync(source, content);
    const firstTarget = path.join(temp.make("plugin-stream-alias-target-"), "first.bin");
    const { length } = capturePluginSourceFile({
      source,
      boundary,
      target: { path: firstTarget, mode: 0o600 },
    });

    const readFileSyncSpy = vi.spyOn(fs, "readFileSync");
    const readSyncSpy = vi.spyOn(fs, "readSync");
    // capturePluginSourceDigest is the one shared path production code uses to feed the
    // cross-file artifact digest for BOTH a freshly captured entry and a re-aliased one
    // (see plugin-generation-artifact.ts's copy() closure) — proving it here covers both.
    const digest = createHash("sha256");
    capturePluginSourceDigest(firstTarget, digest, length);

    expect(readFileSyncSpy).not.toHaveBeenCalled();
    expect(readSyncSpy.mock.calls.length).toBeGreaterThan(1);
    for (const readLength of readSyncLengths(readSyncSpy)) {
      expect(readLength).toBeLessThanOrEqual(2 * 1024 * 1024);
    }
    expect(digest.digest("hex")).toBe(expectedWholeBufferDigestHex(content));
  });

  it("computes a boundary-checked file's content hash without a whole-buffer read", () => {
    const boundary = temp.make("plugin-stream-hash-");
    const source = path.join(boundary, "asset.bin");
    const content = multiChunkFixture();
    fs.writeFileSync(source, content);

    const readFileSyncSpy = vi.spyOn(fs, "readFileSync");
    const readSyncSpy = vi.spyOn(fs, "readSync");
    const contentHash = pluginSourceFileContentHash(source, boundary);

    expect(readFileSyncSpy).not.toHaveBeenCalled();
    expect(readSyncSpy.mock.calls.length).toBeGreaterThan(1);
    expect(contentHash).toBe(createHash("sha256").update(content).digest("hex"));
  });

  describe("verifyPluginSourceInputs throw conditions on a multi-chunk fixture", () => {
    function captureInput(boundary: string, source: string, content: Buffer): PluginSourceInput {
      return {
        identity: pluginSourceStatIdentity(fs.statSync(source, { bigint: true })),
        contentHash: createHash("sha256").update(content).digest("hex"),
        directory: false,
        boundary,
      };
    }

    it("does not throw while the source is unchanged", () => {
      const boundary = temp.make("plugin-verify-stable-");
      const source = path.join(boundary, "asset.bin");
      const content = multiChunkFixture();
      fs.writeFileSync(source, content);
      const inputs = new Map([[source, captureInput(boundary, source, content)]]);
      expect(() => verifyPluginSourceInputs(inputs, [source])).not.toThrow();
    });

    it("throws when the source path's realpath drifts", () => {
      const boundary = temp.make("plugin-verify-realpath-");
      const source = path.join(boundary, "asset.bin");
      const content = multiChunkFixture();
      fs.writeFileSync(source, content);
      const inputs = new Map([[source, captureInput(boundary, source, content)]]);
      // Mocked rather than a real symlink: file-symlink creation needs elevated
      // privileges on Windows, and this exercises the exact comparison in isolation.
      vi.spyOn(fs, "realpathSync").mockReturnValue(path.join(boundary, "elsewhere.bin"));
      expect(() => verifyPluginSourceInputs(inputs, [source])).toThrow(
        "Plugin source changed while preparing its reload",
      );
    });

    it("throws when the stat identity drifts without a content change", () => {
      const boundary = temp.make("plugin-verify-identity-");
      const source = path.join(boundary, "asset.bin");
      const content = multiChunkFixture();
      fs.writeFileSync(source, content);
      const inputs = new Map([[source, captureInput(boundary, source, content)]]);
      // Touch mtime/ctime without altering a single byte of content.
      const future = new Date(Date.now() + 10_000);
      fs.utimesSync(source, future, future);
      expect(() => verifyPluginSourceInputs(inputs, [source])).toThrow(
        "Plugin source changed while preparing its reload",
      );
    });

    it("throws on content drift even when stat identity coincidentally matches", () => {
      const boundary = temp.make("plugin-verify-content-");
      const source = path.join(boundary, "asset.bin");
      const content = multiChunkFixture();
      fs.writeFileSync(source, content);
      const inputs = new Map([[source, captureInput(boundary, source, content)]]);
      const recordedStat = fs.statSync(source, { bigint: true });
      const realStatSync = fs.statSync;
      // Narrow, test-only double for a single overload of a highly overloaded Node API;
      // proves the content-hash comparison alone still catches a change identity misses.
      vi.spyOn(fs, "statSync").mockImplementation(((statPath: fs.PathLike, options?: object) => {
        if (statPath === source && options && "bigint" in options && options.bigint) {
          return recordedStat;
        }
        return realStatSync(statPath as fs.PathLike, options as never);
      }) as typeof fs.statSync);
      const changed = Buffer.from(content);
      changed[0] = (changed[0]! + 1) & 0xff;
      changed[changed.length - 1] = (changed[changed.length - 1]! + 1) & 0xff;
      fs.writeFileSync(source, changed);
      expect(() => verifyPluginSourceInputs(inputs, [source])).toThrow(
        "Plugin source changed while preparing its reload",
      );
    });
  });
});
