// Gateway Talk realtime relay.
// Bridges browser Talk audio sessions with realtime voice provider plugins.
export { createTalkRealtimeRelaySession } from "./session-create.js";
export {
  acknowledgeTalkRealtimeRelayMark,
  cancelTalkRealtimeRelayTurn,
  ensureTalkRealtimeRelayVoiceSession,
  registerTalkRealtimeRelayAgentRun,
  sendTalkRealtimeRelayAudio,
  steerTalkRealtimeRelayAgentRun,
  stopTalkRealtimeRelaySession,
  submitTalkRealtimeRelayToolResult,
} from "./operations.js";
export {
  acquireTalkRealtimeRelayVoiceBarrier,
  releaseTalkRealtimeRelayVoiceBarrier,
} from "./voice.js";
