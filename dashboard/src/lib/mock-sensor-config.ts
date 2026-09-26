// Shared by the mock config GET and ingest acknowledgements.
export const MOCK_CONFIG = {
  config_version: "mock-v1",
  publish_interval_minutes: 15,
  heartbeat_interval_minutes: 5,
  daily_publish_time_utc: "00:00",
  detection_zone: null,
  frame_skip: 1,
  min_track_hits: 3,
} as const;
