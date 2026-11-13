"""Single source of truth mapping each message type to its payload model.

Adding a message type means: add an enum member, add a payload model, add a
row to MESSAGE_SPECS, add a contract test. Nothing else should need to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel

from marine_contracts import payloads as p


class MessageType(str, Enum):
    # Boat -> FMS
    BOAT_STATE = "boat.state"
    MISSION_PROGRESS = "boat.mission_progress"
    OBSTACLE_SUMMARY = "boat.obstacle_summary"
    ENVIRONMENT_PROGRESS = "boat.environment_progress"
    OPERATIONAL_EVENT = "boat.operational_event"
    SERVICE_HEALTH = "boat.service_health"
    # FMS -> Boat
    MISSION_ASSIGNMENT = "fms.mission_assignment"
    NAVIGATION_GOAL = "fms.navigation_goal"
    MISSION_CANCELLATION = "fms.mission_cancellation"
    CONFIGURATION_UPDATE = "fms.configuration_update"
    SAFE_STATE_COMMAND = "fms.safe_state_command"
    # Both directions
    ACKNOWLEDGEMENT = "ack"


class Direction(str, Enum):
    BOAT_TO_FMS = "boat_to_fms"
    FMS_TO_BOAT = "fms_to_boat"
    EITHER = "either"


@dataclass(frozen=True)
class MessageSpec:
    model: type[BaseModel]
    direction: Direction
    requires_mission_id: bool
    critical: bool  # critical messages must be acknowledged (PROPOSED, see protocols/)


MESSAGE_SPECS: dict[MessageType, MessageSpec] = {
    MessageType.BOAT_STATE: MessageSpec(p.BoatStatePayload, Direction.BOAT_TO_FMS, False, False),
    MessageType.MISSION_PROGRESS: MessageSpec(p.MissionProgressPayload, Direction.BOAT_TO_FMS, True, True),
    MessageType.OBSTACLE_SUMMARY: MessageSpec(p.ObstacleSummaryPayload, Direction.BOAT_TO_FMS, False, False),
    MessageType.ENVIRONMENT_PROGRESS: MessageSpec(p.EnvironmentProgressPayload, Direction.BOAT_TO_FMS, False, False),
    MessageType.OPERATIONAL_EVENT: MessageSpec(p.OperationalEventPayload, Direction.BOAT_TO_FMS, False, True),
    MessageType.SERVICE_HEALTH: MessageSpec(p.ServiceHealthPayload, Direction.BOAT_TO_FMS, False, False),
    MessageType.MISSION_ASSIGNMENT: MessageSpec(p.MissionAssignmentPayload, Direction.FMS_TO_BOAT, True, True),
    MessageType.NAVIGATION_GOAL: MessageSpec(p.NavigationGoalPayload, Direction.FMS_TO_BOAT, True, True),
    MessageType.MISSION_CANCELLATION: MessageSpec(p.MissionCancellationPayload, Direction.FMS_TO_BOAT, True, True),
    MessageType.CONFIGURATION_UPDATE: MessageSpec(p.ConfigurationUpdatePayload, Direction.FMS_TO_BOAT, False, True),
    MessageType.SAFE_STATE_COMMAND: MessageSpec(p.SafeStateCommandPayload, Direction.FMS_TO_BOAT, False, True),
    MessageType.ACKNOWLEDGEMENT: MessageSpec(p.AcknowledgementPayload, Direction.EITHER, False, False),
}
