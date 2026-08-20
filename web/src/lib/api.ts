import "server-only";

// 스텁 API 호출은 전부 서버에서만 일어난다. X-Internal-Key는 브라우저로 나가지 않는다.

export class ConsoleApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ConsoleApiError";
  }
}

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `환경변수 ${name}가 설정되지 않았습니다. web/.env.local.example을 web/.env.local로 복사해 주세요.`,
    );
  }
  return value;
}

function baseUrl(): string {
  return process.env.CONSOLE_API_BASE ?? "http://127.0.0.1:8100";
}

interface ErrorBody {
  detail?: { code?: string; message?: string } | string;
}

async function toError(response: Response): Promise<ConsoleApiError> {
  let code = "UNKNOWN";
  let message = "요청을 처리하지 못했습니다.";
  try {
    const body = (await response.json()) as ErrorBody;
    if (typeof body.detail === "string") {
      message = body.detail;
    } else if (body.detail) {
      code = body.detail.code ?? code;
      message = body.detail.message ?? message;
    }
  } catch {
    // 본문이 JSON이 아니면 기본 메시지를 쓴다.
  }
  return new ConsoleApiError(response.status, code, message);
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl()}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "X-Internal-Key": requiredEnv("INTERNAL_API_KEY"),
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
      },
    });
  } catch (cause) {
    throw new ConsoleApiError(
      0,
      "API_UNREACHABLE",
      `스텁 API(${baseUrl()})에 연결하지 못했습니다. uvicorn이 실행 중인지 확인해 주세요. (${String(cause)})`,
    );
  }
  if (!response.ok) throw await toError(response);
  return (await response.json()) as T;
}

export async function consoleGet<T>(
  path: string,
  params: Record<string, string | undefined> = {},
): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value && value !== "normal") query.set(key, value);
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<T>(`${path}${suffix}`, { method: "GET" });
}

export async function consolePost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function consolePatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

/** 페이지에서 오류 상태를 그리기 위해 예외 대신 결과를 돌려주는 래퍼. */
export async function tryGet<T>(
  path: string,
  params: Record<string, string | undefined> = {},
): Promise<{ ok: true; data: T } | { ok: false; error: ConsoleApiError }> {
  try {
    return { ok: true, data: await consoleGet<T>(path, params) };
  } catch (error) {
    if (error instanceof ConsoleApiError) return { ok: false, error };
    throw error;
  }
}
