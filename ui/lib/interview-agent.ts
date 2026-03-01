const DEFAULT_TIMEOUT_MS = 90_000;
const DEFAULT_RETRY_ATTEMPTS = 4;
const RETRYABLE_STATUS = new Set([429, 502, 503, 504]);
const MAX_RETRY_DELAY_MS = 3000;

export class InterviewAgentApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export function getInterviewAgentBaseUrl(): string {
  const raw =
    process.env.INTERVIEW_AGENT_API_URL ??
    process.env.NEXT_PUBLIC_INTERVIEW_AGENT_API_URL ??
    "http://127.0.0.1:8081";
  return raw.trim().replace(/\/+$/, "");
}

/** Returns the WebSocket base URL (ws:// or wss://) for the interview agent endpoint. */
export function getInterviewAgentWsBaseUrl(): string {
  const normalizeLocalhost = (value: string): string =>
    value.replace(/^ws(s)?:\/\/localhost(?=[:/]|$)/, "ws$1://127.0.0.1");

  const wsRaw = process.env.NEXT_PUBLIC_INTERVIEW_AGENT_WS_URL?.trim().replace(/\/+$/, "");
  if (wsRaw) {
    return normalizeLocalhost(wsRaw);
  }

  const publicRaw = process.env.NEXT_PUBLIC_INTERVIEW_AGENT_API_URL?.trim().replace(/\/+$/, "");
  if (publicRaw) {
    return normalizeLocalhost(publicRaw.replace(/^http/, "ws"));
  }

  if (typeof window !== "undefined") {
    const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
    const host = window.location.hostname === "localhost" ? "127.0.0.1" : window.location.hostname;
    return `${wsProtocol}://${host}:8081`;
  }

  return "ws://127.0.0.1:8081";
}

export async function fetchInterviewAgent(
  path: string,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<Response> {
  const baseUrl = getInterviewAgentBaseUrl();
  if (!baseUrl) {
    throw new Error("INTERVIEW_AGENT_API_URL is not configured");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeout);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function computeRetryDelayMs(attempt: number): number {
  const exp = Math.min(200 * 2 ** attempt, MAX_RETRY_DELAY_MS);
  const jitter = Math.floor(Math.random() * 120);
  return exp + jitter;
}

function isRetryableFetchError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const message = error.message.toLowerCase();
  if (error.name === "AbortError") return true;
  return (
    message.includes("fetch failed") ||
    message.includes("network") ||
    message.includes("econnrefused") ||
    message.includes("timed out")
  );
}

export async function fetchInterviewAgentWithRetry(
  path: string,
  init?: RequestInit,
  options?: {
    attempts?: number;
    timeoutMs?: number;
  }
): Promise<Response> {
  const attempts = Math.max(1, options?.attempts ?? DEFAULT_RETRY_ATTEMPTS);
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  let lastError: unknown = null;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetchInterviewAgent(path, init, timeoutMs);
      if (!RETRYABLE_STATUS.has(response.status) || attempt === attempts - 1) {
        return response;
      }
    } catch (error) {
      lastError = error;
      if (!isRetryableFetchError(error) || attempt === attempts - 1) {
        throw error;
      }
    }

    await sleep(computeRetryDelayMs(attempt));
  }

  if (lastError) {
    throw lastError;
  }
  throw new Error("Failed to call interview agent after retries.");
}

export async function parseJsonSafe(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
