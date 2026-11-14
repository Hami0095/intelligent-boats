import { Download, Thermometer } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { FleetController } from "@/lib/fms/fleet";

export function TemperatureLog({ fleet }: { fleet: FleetController }) {
  const readings = fleet.temperatures.records;
  const exportCsv = () => {
    const url = URL.createObjectURL(new Blob([fleet.temperatures.csv()], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "water-temperature.csv"; link.click(); URL.revokeObjectURL(url);
  };
  return <section className="min-w-0 border-y border-border py-3" aria-label="Water temperature log">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="panel-title flex items-center gap-2"><Thermometer size={16} />Water temperature · simulation</h2>
      <Button size="sm" variant="outline" onClick={exportCsv} disabled={!readings.length}><Download size={14} />Export CSV</Button>
    </div>
    <div className="my-2 font-mono text-xs text-muted-foreground">{readings.length} readings · 10s sampling · session only</div>
    <div className="max-h-60 overflow-auto">
      <table className="w-full whitespace-nowrap text-left font-mono text-xs">
        <thead className="text-muted-foreground"><tr>{["Boat", "°C", "Time (UTC)", "GPS", "Source"].map((label) => <th key={label} className="px-2 py-2 font-normal">{label}</th>)}</tr></thead>
        <tbody>{readings.slice(0, 100).map((r, i) => <tr key={`${r.boatId}-${r.at}-${i}`} className="border-t border-border">
          <td className="px-2 py-2">{fleet.registry.require(r.boatId).display_name}</td>
          <td className="px-2 py-2 text-accent">{r.celsius.toFixed(1)}</td>
          <td className="px-2 py-2">{new Date(r.at).toISOString().slice(11, 19)}</td>
          <td className="px-2 py-2">{r.position.latitude_deg.toFixed(5)}, {r.position.longitude_deg.toFixed(5)}</td>
          <td className="px-2 py-2">{r.source === "simulation" ? "Simulation" : "AI box"}</td>
        </tr>)}</tbody>
      </table>
      {!readings.length && <p className="py-3 text-sm text-muted-foreground">No temperature readings</p>}
    </div>
  </section>;
}