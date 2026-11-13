"""FMS data: what the FMS stores about boats, and about the fleet.

Ownership: data ORIGINATES on the boat (telemetry, progress, observations, events)
and the FMS stores it as received, stamped with `received_at`. Fleet-level data
(identities, assignments, the fleet picture) originates in the FMS.
The database technology and retention policy are OPEN decisions.
"""
