<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.

## What Lovable manages

Rules outside this block are the project's own. Change the pieces below in
Lovable, not by hand. With the [Lovable MCP](https://mcp.lovable.dev)
connected, `send_message` asks Lovable to do it; otherwise ask the user to
use the editor.

- **Database.** Do not add or edit `supabase/migrations/` or `drizzle/`.
  Ask Lovable to change the schema.
- **Generated files.** Do not edit a file whose header says it is automatically
  generated.
- **AI gateway.** Keep model calls on Lovable's gateway, and keep
  `LOVABLE_API_KEY` out of browser code.
- **Connectors.** Lovable provides native connectors. `list_connectors` shows
  which are enabled; `add_connector` only returns the dashboard link. When a
  connector is enabled, calls go through the connector gateway and need
  `LOVABLE_API_KEY`. When Lovable does not provide one, users can bring their
  own key and store it in Secrets.
- **Secrets.** Lovable manages them. Do not put secret values in the repo.
<!-- LOVABLE:END -->

- Fleet logic (FMS endpoint, outbox, missions, mock boats) lives framework-free in src/lib/fms and stays in memory, ported from the original Python repo; UI subscribes via useFleet. Why: mirrors the source's transport-independent, in-memory design and keeps rules unit-testable.
- Simulated coverage saturation does not complete a mission; mission lifecycle remains separate from coverage counters so continuous search can retain operator stops and battery safeguards.
- Use shared geographic bounds, fleet-wide visited cells and disjoint row-band assignments for active recon boats; retain per-boat trails and coverage in memory and reallocate unsearched work after commands. Why: avoids duplicate search destinations without blocking necessary transit or completing missions at full coverage.
- Derive connection freshness from received boat-state timestamps with a 10-second stale threshold, and label only the configured transport source; current loopback boats are simulation only. Why: telemetry must never imply a real AI-box connection.
- Delivery payloads explicitly carry item and recipient ID; mock boats resolve live recipient positions and track outbound, handoff and home-return phases independently of search coverage. Why: delivery motion must not follow search lanes or imply real payload transfer.
- All simulated movement uses shared A* navigation with segment clearance against static hazards and live boat GPS positions; blocked travel stops safely. Why: search, delivery and safety returns must obey the same collision rules without claiming real onboard protection.
