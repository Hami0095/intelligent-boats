import { useEffect, useState, useSyncExternalStore } from "react";
import { FleetController } from "@/lib/fms/fleet";
import { DELIVERY_HISTORY_KEY, DeliveryHistory } from "@/lib/fms/delivery-history";
import { syncFmsLink } from "@/lib/fms/link-sync";
import { tsToPythonEnvelope } from "@/lib/fms/external-link";
import type { RawEnvelope } from "@/lib/fms/relay";

export function useFleet() {
  const [fleet, setFleet] = useState<FleetController | null>(null);
  useEffect(() => {
    const f = new FleetController(DeliveryHistory.parse(localStorage.getItem(DELIVERY_HISTORY_KEY))); setFleet(f);
    let saved = "";
    const save = () => { const v = f.deliveries.serialize(); if (v !== saved) { saved = v; localStorage.setItem(DELIVERY_HISTORY_KEY, v); } };
    const unsub = f.subscribe(save); f.tick();
    const t = setInterval(() => f.tick(), 1500);
    // Exchange messages with real AI boxes through the server-side relay.
    // Pending FMS replies (acknowledgements) ride along on the next sync.
    let pendingReplies: RawEnvelope[] = [];
    let syncing = false;
    const link = setInterval(() => {
      if (syncing) return;
      syncing = true;
      const commands = f.externalCommands().map(tsToPythonEnvelope);
      syncFmsLink({ data: { commands, replies: pendingReplies } })
        .then((res) => {
          pendingReplies = f.ingestExternal(res.messages).map(tsToPythonEnvelope);
        })
        .catch(() => { /* link unavailable; retry next interval */ })
        .finally(() => { syncing = false; });
    }, 2000);
    return () => { clearInterval(t); clearInterval(link); unsub(); };
  }, []);
  useSyncExternalStore(fleet?.subscribe ?? (() => () => {}), fleet?.getVersion ?? (() => 0), () => 0);
  return fleet;
}
