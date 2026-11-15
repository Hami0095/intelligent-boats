import { describe, expect, it } from "vitest";
import { FmsLinkRelay } from "./relay";

describe("FmsLinkRelay", () => {
  it("queues boat messages and drains them all for the dashboard", () => {
    const r = new FmsLinkRelay();
    r.postFromBoat("usv-05", [{ message_id: "a", boat_id: "usv-05" }]);
    r.postFromBoat("usv-06", [{ message_id: "b", boat_id: "usv-06" }]);
    expect(r.drainFromBoat().map((e) => e["message_id"])).toEqual(["a", "b"]);
    expect(r.drainFromBoat()).toEqual([]);
  });

  it("queues FMS commands per boat and drains only that boat's queue", () => {
    const r = new FmsLinkRelay();
    r.queueForBoat("usv-05", [{ message_id: "cmd-1" }]);
    r.queueForBoat("usv-06", [{ message_id: "cmd-2" }]);
    expect(r.drainForBoat("usv-05").map((e) => e["message_id"])).toEqual(["cmd-1"]);
    expect(r.drainForBoat("usv-05")).toEqual([]);
    expect(r.drainForBoat("usv-06").map((e) => e["message_id"])).toEqual(["cmd-2"]);
  });

  it("drops the oldest messages when a boat's queue exceeds 200", () => {
    const r = new FmsLinkRelay();
    r.postFromBoat("usv-05", Array.from({ length: 210 }, (_, i) => ({ n: i })));
    const drained = r.drainFromBoat();
    expect(drained).toHaveLength(200);
    expect(drained[0]?.["n"]).toBe(10);
  });
});
