// The API client.
//
// One place that knows about the envelope, the session cookie and the CSRF
// token, so no screen has to remember any of it. Everything goes through the
// same origin (Next rewrites /api/v1 to the Go service in development, the
// reverse proxy does it in production), which is what keeps the session cookie
// first-party and SameSite=Lax effective.

export type ApiError = {
  status: number;
  code: string;
  message: string;
  fields?: Record<string, string>;
  requestId?: string;
};

export class ApiFailure extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string>;
  readonly requestId?: string;

  constructor(error: ApiError) {
    super(error.message);
    this.name = 'ApiFailure';
    this.status = error.status;
    this.code = error.code;
    this.fields = error.fields ?? {};
    this.requestId = error.requestId;
  }

  /** Whether the caller simply is not signed in, which is not an error worth showing. */
  get isUnauthenticated() {
    return this.status === 401;
  }
}

export type Envelope<T> = { data: T; meta?: Record<string, unknown> };

/** The CSRF token the API hands back on every authenticated response. */
let csrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

export function getCsrfToken() {
  return csrfToken;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  /** A multipart body, for uploads. Set instead of `body`. */
  form?: FormData;
  signal?: AbortSignal;
  /** Server components pass the incoming cookie header through. */
  headers?: Record<string, string>;
  cache?: RequestCache;
};

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? '/api/v1';

export async function api<T>(path: string, options: RequestOptions = {}): Promise<Envelope<T>> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json', ...options.headers };

  let body: BodyInit | undefined;
  if (options.form) {
    body = options.form;
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.body);
  }

  // The token rides on every mutation. The API rotates it on a role switch, so
  // it is read back from each response rather than cached at sign-in.
  if (method !== 'GET' && method !== 'HEAD' && csrfToken) {
    headers['X-CSRF-Token'] = csrfToken;
  }

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body,
    credentials: 'include',
    signal: options.signal,
    cache: options.cache ?? 'no-store',
  });

  const text = await response.text();
  const payload = text ? safeParse(text) : {};

  if (!response.ok) {
    const error = (payload as { error?: Record<string, unknown> }).error ?? {};
    throw new ApiFailure({
      status: response.status,
      code: String(error.code ?? 'unknown'),
      // A message from the API is written for a person; the fallback is too.
      message: String(error.message ?? "Something didn't work. Please try again."),
      fields: (error.fields as Record<string, string>) ?? undefined,
      requestId: error.request_id as string | undefined,
    });
  }

  const envelope = payload as Envelope<T>;
  const token = (envelope.data as { csrf_token?: string } | null)?.csrf_token;
  if (token) setCsrfToken(token);

  return envelope;
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

/** Shorthands, because most calls only want the data. */
export async function get<T>(path: string, options?: RequestOptions): Promise<T> {
  return (await api<T>(path, { ...options, method: 'GET' })).data;
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  return (await api<T>(path, { method: 'POST', body })).data;
}

export async function put<T>(path: string, body?: unknown): Promise<T> {
  return (await api<T>(path, { method: 'PUT', body })).data;
}

export async function patch<T>(path: string, body?: unknown): Promise<T> {
  return (await api<T>(path, { method: 'PATCH', body })).data;
}

export async function del<T>(path: string): Promise<T> {
  return (await api<T>(path, { method: 'DELETE' })).data;
}

export async function upload<T>(path: string, form: FormData): Promise<T> {
  return (await api<T>(path, { method: 'POST', form })).data;
}

/** Both the data and the meta, for the lists that carry a count or a cursor. */
export async function list<T>(path: string): Promise<Envelope<T>> {
  return api<T>(path);
}
