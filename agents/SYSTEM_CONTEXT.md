# System context for agents

## The machine

A small autonomous surface vessel. It has sensors (cameras and possibly range sensors, positioning hardware to be decided), a propulsion system (to be decided with the CAD team), and an onboard computer that runs the AI Box.

## The fleet

Several boats, each independent. A central Fleet Management System assigns missions and receives reports. Boats never talk to each other.

## The job

A mission gives a boat a search area and an objective. The boat explores the area, avoids obstacles, and reports progress. The reward or target definition is not yet known, and the boat does not know where it is.

## Two concerns that must not be merged

- **Collision avoidance** (perception): is there something in my path, and how risky is it?
- **Search progress** (environment, decision): where have I been, what is searched, where next?

## Where we are

Foundation stage. Contracts, module boundaries, mock integration and tests exist. Perception, navigation, risk estimation, search coverage, transport, storage and hardware are not implemented. See `docs/OPEN_DECISIONS.md`.

## Things that look like facts but are not

- A camera gives a distance. (It does not reliably, without calibration and fusion.)
- The boat knows its coordinates. (Only if a position source provides them.)
- Isaac Sim is the runtime. (It is the final demo environment only.)
- A visit to a region means it has been searched. (It does not; searching needs a coverage model.)
- Zero reward is the same as no reward information. (It is not.)
