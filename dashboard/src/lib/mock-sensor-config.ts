import { withHeartbeat } from "@/lib/heartbeat";

// Shared by the mock config GET and ingest acknowledgements. The heartbeat
// interval comes from CAMINA_HEARTBEAT_MINUTES (src/lib/heartbeat.ts).
const { config, config_version } = withHeartbeat(
  {
    publish_interval_minutes: 15,
    daily_publish_time_utc: "00:00",
    detection_zone: null,
    frame_skip: 1,
    min_track_hits: 3,
  },
  "mock-v1"
);

export const MOCK_CONFIG = { ...config, config_version } as {
  config_version: string;
  publish_interval_minutes: number;
  heartbeat_interval_minutes: number;
  daily_publish_time_utc: string;
  detection_zone: null;
  frame_skip: number;
  min_track_hits: number;
};
