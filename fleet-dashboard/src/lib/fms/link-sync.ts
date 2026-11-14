/**
 * Browser side of the AI-box link. The dashboard posts FMS commands and
 * acknowledgements for real boats here, and collects the boat-originated
 * messages waiting in the relay. Shares the relay singleton with the public
 * /api/public/fms-link route.
 */
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { getFmsLinkRelay, type RawEnvelope } from "./relay";

const rawEnvelope = z.record(z.string(), z.any());
const input = z.object({
  commands: z.array(rawEnvelope).max(100),
  replies: z.array(rawEnvelope).max(100),
});

export const syncFmsLink = createServerFn({ method: "POST" })
  .inputValidator((data) => input.parse(data))
  .handler(async ({ data }) => {
    const relay = getFmsLinkRelay();
    for (const e of [...data.commands, ...data.replies]) {
      const boatId = (e as RawEnvelope)["boat_id"];
      if (typeof boatId === "string") relay.queueForBoat(boatId, [e as RawEnvelope]);
    }
    return { messages: relay.drainFromBoat() };
  });
