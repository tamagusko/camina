import "server-only";

// Selects the data source at server-start time.
// Honoured by every API route and server-component data-access function.

export type DataSource = "mock" | "live";

const env = process.env.CAMINA_DATA_SOURCE?.toLowerCase();

export const dataSource: DataSource = env === "live" ? "live" : "mock";

export const isMock = dataSource === "mock";
export const isLive = dataSource === "live";

export const mockCity = process.env.CAMINA_MOCK_CITY ?? "dublin";
