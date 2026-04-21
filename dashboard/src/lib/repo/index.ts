import "server-only";
import { isMock } from "@/lib/data-source";
import { mockStreetsRepo } from "./streets-mock";
import { liveStreetsRepo } from "./streets-live";
import type { StreetsRepo } from "./types";

export const streetsRepo: StreetsRepo = isMock ? mockStreetsRepo : liveStreetsRepo;

export type { StreetsRepo } from "./types";
