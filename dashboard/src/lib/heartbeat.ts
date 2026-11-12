// How often sensors send a heartbeat — the ONE place to change it.
//
// Set CAMINA_HEARTBEAT_MINUTES in the Vercel project's environment variables
// and redeploy. Every sensor picks the new interval up on its next heartbeat:
// the value is folded into the config version the server acknowledges, so each
// sensor's config poller sees a new version and fetches the new config. No
// per-sensor edit, no SSH.
//
// Pilot: 15 min. Each heartbeat wakes the free Neon database, which then stays
// awake for 5 min; at 15 min, aligned with the 15-min count windows, it wakes
// once per quarter-hour and stays inside the free plan's compute hours.
// Goal: 5 min (fresher health and faster silent-sensor alerts) once there is a
// paid database plan. See README.md, "Heartbeat interval".

export const DEFAULT_HEARTBEAT_MINUTES = 15;

// Values that keep heartbeats on the same wall-clock boundaries as the 15-min
// count windows (so heartbeats and counts wake the database together).
const ALLOWED_MINUTES = [1, 3, 5, 15, 30, 60] as const;

export function heartbeatMinutes(
  env: Record<string, string | undefined> = process.env
): number {
  const raw = env.CAMINA_HEARTBEAT_MINUTES?.trim();
  if (!raw) return DEFAULT_HEARTBEAT_MINUTES;
  const minutes = Number(raw);
  if (!(ALLOWED_MINUTES as readonly number[]).includes(minutes)) {
    throw new Error(
      `CAMINA_HEARTBEAT_MINUTES must be one of ${ALLOWED_MINUTES.join(", ")} ` +
        `(minutes; 15 for the free pilot, 5 is the goal), got "${raw}"`
    );
  }
  return minutes;
}

/** A sensor's config with the deployment's heartbeat interval applied. */
export function withHeartbeat(
  config: Record<string, unknown>,
  configVersion: string,
  minutes: number = heartbeatMinutes()
): { config: Record<string, unknown>; config_version: string } {
  return {
    config: { ...config, heartbeat_interval_minutes: minutes },
    config_version: `${configVersion}+hb${minutes}`,
  };
}

/** A sensor is silent after three missed heartbeats. */
export function silentAfterMs(minutes: number = heartbeatMinutes()): number {
  return 3 * minutes * 60_000;
}
