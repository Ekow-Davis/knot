/**
 * Thin fetch wrapper. The API lives on the same origin (/api), and the session is an httpOnly
 * cookie, so there's no token handling here at all.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
  }
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
    // FastAPI errors look like {"detail": "..."} or {"detail": {"code": "...", "message": "..."}}
    const detail = data?.detail
    const code = typeof detail === 'object' && detail?.code ? detail.code : `http_${res.status}`
    const message = typeof detail === 'string' ? detail : detail?.message ?? res.statusText
    throw new ApiError(res.status, code, message)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
}
