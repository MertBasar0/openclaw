import { createHash } from "node:crypto";
import fs from "node:fs";
import { openRootFileSync, readFileWindowFullySync } from "../infra/boundary-file-read.js";

// Bounded chunk size for streaming large plugin source files during capture/verification;
// keeps peak buffer use fixed instead of proportional to file size (see issue #155728).
const PLUGIN_SOURCE_STREAM_CHUNK_BYTES = 1024 * 1024; // 1 MiB

/**
 * Reads `fd` in fixed-size chunks (reusing one scratch buffer) instead of buffering it whole.
 * With `limit`, stops after that many bytes even if more remain; without it, reads to EOF.
 */
function drainFileInChunks(fd: number, onChunk: (chunk: Buffer) => void, limit = Infinity): void {
  const buffer = Buffer.allocUnsafe(PLUGIN_SOURCE_STREAM_CHUNK_BYTES);
  let position = 0;
  while (position < limit) {
    const window = Math.min(buffer.length, limit - position);
    const target = window === buffer.length ? buffer : buffer.subarray(0, window);
    const bytesRead = readFileWindowFullySync(fd, target, position);
    if (bytesRead > 0) {
      onChunk(target.subarray(0, bytesRead));
      position += bytesRead;
    }
    if (bytesRead < window) {
      break;
    }
  }
}

function openPluginSourceFile(source: string, boundary: string) {
  const opened = openRootFileSync({
    absolutePath: source,
    rootPath: boundary,
    boundaryLabel: "plugin build source",
    rejectHardlinks: false,
  });
  if (!opened.ok) {
    throw new Error(`Cannot capture plugin source ${source}`, { cause: opened.error });
  }
  return opened;
}

/**
 * Streams a boundary-checked source file to `target` in bounded chunks, computing its SHA-256
 * content hash incrementally — without ever holding the whole file in memory. Callers that also
 * maintain a cross-file artifact digest feed it separately via {@link capturePluginSourceDigest}
 * against the written `target` (identical bytes, one shared code path for every copied entry).
 */
export function capturePluginSourceFile(params: {
  source: string;
  boundary: string;
  target: { path: string; mode: number };
}): { length: number; contentHash: string } {
  const opened = openPluginSourceFile(params.source, params.boundary);
  try {
    const length = opened.stat.size;
    const contentHash = createHash("sha256");
    const targetFd = fs.openSync(params.target.path, "w", params.target.mode);
    try {
      drainFileInChunks(
        opened.fd,
        (chunk) => {
          contentHash.update(chunk);
          fs.writeSync(targetFd, chunk);
        },
        length,
      );
    } finally {
      fs.closeSync(targetFd);
    }
    return { length, contentHash: contentHash.digest("hex") };
  } finally {
    fs.closeSync(opened.fd);
  }
}

/**
 * Feeds `digest` the exact `String(length)` + NUL + byte sequence a single whole-buffer read of
 * the already-local `filePath` would have produced, in bounded chunks. Used for every copied
 * entry (freshly captured or re-aliased from an earlier capture) so the cross-file artifact
 * digest never requires a second full-buffer read of the original source.
 */
export function capturePluginSourceDigest(
  filePath: string,
  digest: ReturnType<typeof createHash>,
  length: number,
): void {
  digest.update(String(length)).update("\0");
  const fd = fs.openSync(filePath, "r");
  try {
    drainFileInChunks(fd, (chunk) => digest.update(chunk), length);
  } finally {
    fs.closeSync(fd);
  }
}

/** Boundary-checked, bounded-memory equivalent of hashing a whole-buffer read of `source`. */
export function pluginSourceFileContentHash(source: string, boundary: string): string {
  const opened = openPluginSourceFile(source, boundary);
  try {
    const hash = createHash("sha256");
    drainFileInChunks(opened.fd, (chunk) => hash.update(chunk));
    return hash.digest("hex");
  } finally {
    fs.closeSync(opened.fd);
  }
}
