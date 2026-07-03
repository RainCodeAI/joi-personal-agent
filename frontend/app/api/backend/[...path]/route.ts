import { NextRequest } from "next/server";

// Same-origin proxy to the Joi backend. The browser talks to this route with no
// credentials; the API token is injected here, server-side, so it never ships
// in the client bundle. Active only in proxy mode (NEXT_PUBLIC_API_BASE_URL
// unset); when an absolute base URL is configured the client calls the backend
// directly instead and this route is unused.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_BASE_URL =
  process.env.API_BASE_URL ||
  process.env.BACKEND_API_BASE_URL ||
  "http://127.0.0.1:8000";

const API_TOKEN = process.env.JOI_API_TOKEN || "";

type RouteContext = { params: Promise<{ path?: string[] }> };

async function proxy(req: NextRequest, ctx: RouteContext): Promise<Response> {
  const { path = [] } = await ctx.params;
  const target = `${BACKEND_BASE_URL}/${path.join("/")}${req.nextUrl.search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const accept = req.headers.get("accept");
  if (accept) headers.set("accept", accept);
  if (API_TOKEN) headers.set("x-joi-api-token", API_TOKEN);

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const body = hasBody ? await req.text() : undefined;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ detail: `Backend unreachable: ${(err as Error).message}` }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }

  // Stream the upstream body through unchanged (works for SSE too). Only copy
  // headers that are safe to forward; content-length/encoding are recomputed.
  const responseHeaders = new Headers();
  const upstreamType = upstream.headers.get("content-type");
  if (upstreamType) responseHeaders.set("content-type", upstreamType);
  const cacheControl = upstream.headers.get("cache-control");
  if (cacheControl) responseHeaders.set("cache-control", cacheControl);
  responseHeaders.set("x-accel-buffering", "no");

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
