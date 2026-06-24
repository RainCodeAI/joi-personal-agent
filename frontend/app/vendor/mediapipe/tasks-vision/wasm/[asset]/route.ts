import { readFile } from "node:fs/promises";
import { join } from "node:path";

const ALLOWED_ASSETS = new Set([
  "vision_wasm_internal.js",
  "vision_wasm_internal.wasm",
  "vision_wasm_module_internal.js",
  "vision_wasm_module_internal.wasm",
  "vision_wasm_nosimd_internal.js",
  "vision_wasm_nosimd_internal.wasm",
]);

function contentTypeFor(asset: string): string {
  if (asset.endsWith(".wasm")) {
    return "application/wasm";
  }
  if (asset.endsWith(".js")) {
    return "application/javascript; charset=utf-8";
  }
  return "application/octet-stream";
}

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ asset: string }> },
) {
  const { asset } = await params;
  if (!ALLOWED_ASSETS.has(asset)) {
    return new Response("Not found", { status: 404 });
  }

  const assetPath = join(
    process.cwd(),
    "node_modules",
    "@mediapipe",
    "tasks-vision",
    "wasm",
    asset,
  );
  const body = await readFile(assetPath);
  return new Response(body, {
    headers: {
      "Cache-Control": "public, max-age=31536000, immutable",
      "Content-Type": contentTypeFor(asset),
    },
  });
}
