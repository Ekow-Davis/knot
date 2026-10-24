/**
 * Thin fetch wrapper. The API lives on the same origin (/api), and the session is an httpOnly
 * cookie, so there's no token handling here at all.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public extra: Record<string, unknown> = {},
  ) {
    super(message)
  }
}

/** Set by main.ts: called when a signed-in request finds the session has expired. */
let onSessionExpired: (() => void) | null = null
export function setSessionExpiredHandler(fn: () => void) {
  onSessionExpired = fn
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'offline', 'No connection')
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    // Our errors look like {"detail": {"code": "...", "message": "...", ...extra}}.
    // FastAPI's own validation errors are {"detail": [...]}, which become code "invalid".
    const detail = data?.detail
    let code = `http_${res.status}`
    let message = res.statusText
    let extra: Record<string, unknown> = {}
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const { code: c, message: m, ...rest } = detail as Record<string, unknown>
      if (typeof c === 'string') code = c
      if (typeof m === 'string') message = m
      extra = rest
    } else if (Array.isArray(detail)) {
      code = 'invalid'
      message = 'Something in that didn’t look right.'
    } else if (typeof detail === 'string') {
      message = detail
    }
    if (code === 'session_expired' && path !== '/auth/me') onSessionExpired?.()
    throw new ApiError(res.status, code, message, extra)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
}
