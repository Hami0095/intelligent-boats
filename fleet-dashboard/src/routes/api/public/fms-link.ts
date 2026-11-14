/**
 * HTTP endpoint used by real AI boxes (Python `HttpFmsLink` adapter).
 *
 * POST { envelopes: [...] }  — boat-originated messages, queued for the FMS.
 * GET  ?boat_id=<id>         — drains FMS commands waiting for that boat.
 *
 * This route is public by prefix, so every call must carry
 * `Authorization: Bearer <FMS_LINK_TOKEN>`.
 */
import { createFileRoute } from "@tanstack/react-router";
import { getFmsLinkRelay, type RawEnvelope } from "@/lib/fms/relay";

const BOAT_ID_PATTERN = /^[a-z0-9][a-z0-9-]{1,62}$/;
const MAX_ENVELOPES_PER_CALL = 50;

function authorized(request: Request): Response | null {
  const token = process.env["FMS_LINK_TOKEN"];
  if (!token) return Response.json({ error: "FMS link is not configured" }, { status: 503 });
  const header = request.headers.get("authorization");
  if (header !== `Bearer ${token}`) return Response.json({ error: "unauthorized" }, { status: 401 });
  return null;
}

function isRawEnvelope(v: unknown): v is RawEnvelope {
  if (typeof v !== "object" || v === null || Array.isArray(v)) return false;
  const e = v as RawEnvelope;
  return typeof e["boat_id"] === "string" && BOAT_ID_PATTERN.test(e["boat_id"] as string);
}

export const Route = createFileRoute("/api/public/fms-link")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const denied = authorized(request);
        if (denied) return denied;
        let body: unknown;
        try {
          body = await request.json();
        } catch {
          return Response.json({ error: "invalid JSON body" }, { status: 400 });
        }
        const envelopes = (body as { envelopes?: unknown })?.envelopes;
        if (!Array.isArray(envelopes) || envelopes.length > MAX_ENVELOPES_PER_CALL)
          return Response.json({ error: "envelopes must be an array of at most 50" }, { status: 400 });
        const valid = envelopes.filter(isRawEnvelope);
        const byBoat = new Map<string, RawEnvelope[]>();
        for (const e of valid) {
          const boatId = e["boat_id"] as string;
          const q = byBoat.get(boatId) ?? [];
          q.push(e);
          byBoat.set(boatId, q);
        }
        const relay = getFmsLinkRelay();
        for (const [boatId, q] of byBoat) relay.postFromBoat(boatId, q);
        return Response.json({ accepted: valid.length, rejected: envelopes.length - valid.length });
      },
      GET: async ({ request }) => {
        const denied = authorized(request);
        if (denied) return denied;
        const boatId = new URL(request.url).searchParams.get("boat_id") ?? "";
        if (!BOAT_ID_PATTERN.test(boatId))
          return Response.json({ error: "boat_id query parameter is required" }, { status: 400 });
        return Response.json({ envelopes: getFmsLinkRelay().drainForBoat(boatId) });
      },
    },
  },
});
