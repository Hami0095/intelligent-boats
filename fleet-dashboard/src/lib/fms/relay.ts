/**
 * In-memory mailbox between real AI boxes and the browser-hosted FMS.
 *
 * The Python `HttpFmsLink` adapter POSTs boat-originated envelopes here and
 * GETs FMS commands; the dashboard drains/posts the other side through the
 * `syncFmsLink` server function. Envelopes are passed through as raw JSON —
 * validation happens at both ends (pydantic on the boat, contracts here).
 *
 * State is per server process and resets on restart; that is acceptable for
 * the hackathon demo link, not for production durability.
 */

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type RawEnvelope = { [key: string]: JsonValue };

const LIMIT_PER_BOAT = 200;

export class FmsLinkRelay {
  private fromBoat = new Map<string, RawEnvelope[]>();
  private fromFms = new Map<string, RawEnvelope[]>();

  private push(map: Map<string, RawEnvelope[]>, boatId: string, envelopes: RawEnvelope[]) {
    const q = map.get(boatId) ?? [];
    q.push(...envelopes);
    while (q.length > LIMIT_PER_BOAT) q.shift();
    map.set(boatId, q);
  }

  /** Boat -> FMS: called by the public HTTP route when an AI box sends messages. */
  postFromBoat(boatId: string, envelopes: RawEnvelope[]) {
    this.push(this.fromBoat, boatId, envelopes);
  }

  /** Boat -> FMS: called by the dashboard sync to collect everything waiting. */
  drainFromBoat(): RawEnvelope[] {
    const out: RawEnvelope[] = [];
    for (const [boatId, q] of this.fromBoat) {
      out.push(...q.map((e) => ({ ...e, boat_id: e["boat_id"] ?? boatId })));
      q.length = 0;
    }
    return out;
  }

  /** FMS -> Boat: commands and acknowledgements waiting for a specific boat. */
  queueForBoat(boatId: string, envelopes: RawEnvelope[]) {
    this.push(this.fromFms, boatId, envelopes);
  }

  /** FMS -> Boat: called by the public HTTP route when an AI box polls. */
  drainForBoat(boatId: string): RawEnvelope[] {
    const q = this.fromFms.get(boatId) ?? [];
    this.fromFms.set(boatId, []);
    return q;
  }
}

const relay = new FmsLinkRelay();

export function getFmsLinkRelay() {
  return relay;
}
