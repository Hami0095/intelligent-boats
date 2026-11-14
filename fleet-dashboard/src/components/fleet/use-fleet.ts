import { useEffect, useState, useSyncExternalStore } from "react";
import { FleetController } from "@/lib/fms/fleet";
import { DELIVERY_HISTORY_KEY, DeliveryHistory } from "@/lib/fms/delivery-history";

export function useFleet() {
  const [fleet, setFleet] = useState<FleetController | null>(null);
  useEffect(() => {
    const f = new FleetController(DeliveryHistory.parse(localStorage.getItem(DELIVERY_HISTORY_KEY))); setFleet(f);
    let saved = "";
    const save = () => { const v = f.deliveries.serialize(); if (v !== saved) { saved = v; localStorage.setItem(DELIVERY_HISTORY_KEY, v); } };
    const unsub = f.subscribe(save); f.tick();
    const t = setInterval(() => f.tick(), 1500);
    return () => { clearInterval(t); unsub(); };
  }, []);
  useSyncExternalStore(fleet?.subscribe ?? (() => () => {}), fleet?.getVersion ?? (() => 0), () => 0);
  return fleet;
}
