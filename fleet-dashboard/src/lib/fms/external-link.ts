/**
 * Conversions between the Python marine_contracts envelope JSON and the
 * dashboard's TypeScript Envelope. The Python side adds `schema_version`
 * and uses ISO-8601 UTC timestamps; the TypeScript side uses epoch ms.
 */
import { MESSAGE_SPECS, type Envelope, type MessageType } from "./contracts";
import type { RawEnvelope } from "./relay";

export const SCHEMA_VERSION = "1.0.0";
const BOAT_ID_PATTERN = /^[a-z0-9][a-z0-9-]{1,62}$/;

/** Parse one raw JSON envelope from an AI box. Returns null when unusable. */
export function pythonToTsEnvelope(raw: RawEnvelope): Envelope | null {
  const messageType = raw["message_type"];
  const boatId = raw["boat_id"];
  const messageId = raw["message_id"];
  const sequence = raw["sequence_number"];
  if (typeof messageType !== "string" || !(messageType in MESSAGE_SPECS)) return null;
  if (typeof boatId !== "string" || !BOAT_ID_PATTERN.test(boatId)) return null;
  if (typeof messageId !== "string" || !messageId) return null;
  if (typeof sequence !== "number" || !Number.isInteger(sequence) || sequence < 0) return null;
  const rawTs = raw["timestamp"];
  const timestamp =
    typeof rawTs === "number" ? rawTs : typeof rawTs === "string" ? Date.parse(rawTs) : NaN;
  if (!Number.isFinite(timestamp)) return null;
  const missionId = raw["mission_id"];
  const payload = raw["payload"];
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) return null;
  return {
    message_id: messageId,
    boat_id: boatId,
    message_type: messageType as MessageType,
    mission_id: typeof missionId === "string" ? missionId : null,
    sequence_number: sequence,
    timestamp,
    payload,
  };
}

/** Serialise a dashboard envelope into the Python contract shape. */
export function tsToPythonEnvelope(e: Envelope): RawEnvelope {
  const payload: RawEnvelope = { ...(e.payload as RawEnvelope) };
  // The Python MissionAssignmentPayload forbids unknown fields; the dashboard's
  // simulated delivery extension is dropped before crossing the link.
  delete payload["delivery"];
  return {
    schema_version: SCHEMA_VERSION,
    message_id: e.message_id,
    boat_id: e.boat_id,
    mission_id: e.mission_id,
    message_type: e.message_type,
    timestamp: new Date(e.timestamp).toISOString(),
    sequence_number: e.sequence_number,
    payload,
  };
}
