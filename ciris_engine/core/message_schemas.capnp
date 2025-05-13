# Example Cap'n Proto conceptual structure (syntax illustrative)
# @0x... identifiers would be assigned automatically

# --- Common Message Envelope ---
struct CirisMessage {
  # Header
  messageId @0 :Text;
  schemaVersion @1 :Text; # e.g., "1.0-beta"
  senderDid @2 :Text; # Veilid DID
  recipientDid @3 :Text; # Veilid DID or broadcast address
  timestamp @4 :Int64; # Unix timestamp (nanoseconds)
  correlationId @5 :Text; # Optional, for request-response matching

  # Discriminated Union for Payload
  union {
    assignTask @6 :TaskAssignmentPayload;
    updateTaskStatus @7 :TaskStatusUpdatePayload;
    shareObservation @8 :ObservationPayload;
    speak @9 :SpeakPayload;
    toolInvocation @10 :ToolInvocationPayload;
    toolResult @11 :ToolResultPayload;
    deferralNotification @12 :DeferralNotificationPayload;
    #... other message types
    registerAgent @13 :AgentRegistrationPayload;
    heartbeat @14 :HeartbeatPayload;
    #... etc.
  }
}

# --- Example Payload Structures ---

struct TaskAssignmentPayload {
  taskUal @0 :Text; # UAL of the Task KA
  parameters @1 :Data; # Serialized parameters (e.g., JSON blob, or another Capnp struct)
  priority @2 :Int32;
  deadline @3 :Int64; # Optional Unix timestamp
}

struct TaskStatusUpdatePayload {
  taskUal @0 :Text;
  newStatus @1 :TaskStatusEnum; # Enum defined elsewhere (corresponds to TaskStatus in foundational_schemas.py)
  progressPercentage @2 :Float32;
  updateMessage @3 :Text; # Optional message
}

struct ObservationPayload {
  observationId @0 :Text;
  sourceType @1 :ObservationSourceTypeEnum; # Corresponds to ObservationSourceType in foundational_schemas.py
  sourceIdentifier @2 :Text;
  dataSchemaUal @3 :Text; # Optional UAL to schema KA
  dataPayload @4 :Data; # Serialized observation data
  confidence @5 :Float32;
  metadata @6 :Data; # Optional serialized metadata
}

struct SpeakPayload {
  content @0 :Text;
  targetChannel @1 :Text; # Optional
  modality @2 :Text;
}

struct ToolInvocationPayload {
  toolName @0 :Text;
  arguments @1 :Data; # Serialized arguments
  invocationId @2 :Text; # Unique ID for this invocation
}

struct ToolResultPayload {
  invocationId @0 :Text; # Correlates with ToolInvocationPayload
  resultData @1 :Data; # Serialized result
  isError @2 :Bool;
  errorMessage @3 :Text; # Optional
}

struct DeferralNotificationPayload {
  deferredTaskUal @0 :Text; # Optional, if deferral relates to a task
  deferredThoughtId @1 :Text; # Optional, if deferral relates to a thought
  reason @2 :Text;
  targetWaUal @3 :Text;
  deferralPackageUal @4 :Text; # UAL of the KA containing the full deferral package
}

# TODO: Define other payload structs like AgentRegistrationPayload, HeartbeatPayload etc.

# Note: Enums like TaskStatusEnum and ObservationSourceTypeEnum would typically be defined
# in a separate .capnp file and imported, or defined within this file if preferred.
# For example:
# enum TaskStatusEnum {
#   pending @0;
#   active @1;
#   completed @2;
#   failed @3;
#   deferred @4;
#   rejected @5;
# }
#
# enum ObservationSourceTypeEnum {
#   discordMessage @0;
#   wbdPackage @1;
#   # ... and so on for all values in Python's ObservationSourceType
# }
