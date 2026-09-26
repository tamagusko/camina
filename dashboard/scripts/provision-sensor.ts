import { createHash, randomBytes } from "node:crypto";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import postgres from "postgres";
import { sensorConfigResponseSchema } from "../src/lib/schemas";

type Client = ReturnType<typeof postgres>;

type CreateOptions = {
  id: string;
  displayName: string;
  streetId: string;
  latitude: number;
  longitude: number;
  installDate: string;
  configVersion: string;
  config: Record<string, unknown>;
  rotate?: false;
};
type RotateOptions = { id: string; rotate: true };

/** A new token is returned only after the database has stored its hash. */
export async function provisionSensor(
  client: Client,
  options: CreateOptions | RotateOptions
): Promise<string> {
  if (!options.id.trim()) throw new Error("sensor id is required");
  const token = randomBytes(32).toString("base64url");
  const hash = createHash("sha256").update(token).digest("hex");

  if (options.rotate) {
    const updated = await client`
      UPDATE sensors SET api_token_hash = ${hash}, updated_at = now()
      WHERE id = ${options.id} RETURNING id
    `;
    if (updated.length === 0) throw new Error(`sensor ${options.id} does not exist`);
    return token;
  }

  if (!Number.isFinite(options.latitude) || Math.abs(options.latitude) > 90 ||
      !Number.isFinite(options.longitude) || Math.abs(options.longitude) > 180) {
    throw new Error("invalid latitude or longitude");
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(options.installDate)) {
    throw new Error("install date must be YYYY-MM-DD");
  }
  const parsed = sensorConfigResponseSchema.parse({
    ...options.config,
    config_version: options.configVersion,
  });
  const { config_version: _version, ...config } = parsed;
  await client.begin(async (tx) => {
    const inserted = await tx`
      INSERT INTO sensors (id, display_name, latitude, longitude, install_date,
                           config_json, config_version, api_token_hash)
      VALUES (${options.id}, ${options.displayName}, ${options.latitude},
              ${options.longitude}, ${options.installDate}, ${JSON.stringify(config)}::jsonb,
              ${options.configVersion}, ${hash})
      ON CONFLICT (id) DO NOTHING RETURNING id
    `;
    if (inserted.length === 0) throw new Error(`sensor ${options.id} already exists; use --rotate to replace its token`);
    await tx`
      INSERT INTO sensor_street_coverage (sensor_id, street_id)
      VALUES (${options.id}, ${options.streetId})
    `;
  });
  return token;
}

const DEFAULT_CONFIG = {
  publish_interval_minutes: 15,
  heartbeat_interval_minutes: 5,
  daily_publish_time_utc: "00:00",
  detection_zone: null,
  frame_skip: 5,
  min_track_hits: 3,
};

async function main(): Promise<void> {
  const args = new Map<string, string>();
  let rotate = false;
  for (let i = 2; i < process.argv.length; i++) {
    const flag = process.argv[i];
    if (flag === "--rotate") {
      rotate = true;
      continue;
    }
    if (!flag?.startsWith("--") || !process.argv[i + 1]?.length ||
        process.argv[i + 1]?.startsWith("--")) {
      throw new Error(`expected --flag value, got ${flag ?? "end of arguments"}`);
    }
    args.set(flag, process.argv[++i]!);
  }
  const allowed = new Set([
    "--id", "--display-name", "--street-id", "--latitude", "--longitude",
    "--install-date", "--config-version", "--config",
  ]);
  for (const flag of args.keys()) if (!allowed.has(flag)) throw new Error(`unknown option ${flag}`);
  const id = args.get("--id");
  if (!id) throw new Error("--id is required");
  const url = process.env.DATABASE_URL_UNPOOLED ?? process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL_UNPOOLED or DATABASE_URL is required");
  const client = postgres(url, { max: 1, prepare: false });
  try {
    let options: CreateOptions | RotateOptions;
    if (rotate) {
      options = { id, rotate: true };
    } else {
      const displayName = args.get("--display-name");
      const streetId = args.get("--street-id");
      const latitude = args.get("--latitude");
      const longitude = args.get("--longitude");
      if (!displayName || !streetId || !latitude || !longitude) {
        throw new Error("creation requires --display-name, --street-id, --latitude, and --longitude");
      }
      const config = args.has("--config")
        ? JSON.parse(await readFile(args.get("--config")!, "utf8")) as Record<string, unknown>
        : DEFAULT_CONFIG;
      options = {
        id, displayName, streetId,
        latitude: Number(latitude), longitude: Number(longitude),
        installDate: args.get("--install-date") ?? new Date().toISOString().slice(0, 10),
        configVersion: args.get("--config-version") ?? "1",
        config,
      };
    }
    const token = await provisionSensor(client, options);
    process.stdout.write(`${token}\n`);
  } finally {
    await client.end();
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
