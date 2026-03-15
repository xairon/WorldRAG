/**
 * Base API client. All fetch calls go through apiFetch.
 */

function getApiBase() {
  if (typeof window === "undefined") {
    return process.env.BACKEND_URL ?? "http://localhost:8000"
  }
  return "/api"
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: HeadersInit = { ...(init?.headers as Record<string, string>) }
  if (!(init?.body instanceof FormData)) {
    (headers as Record<string, string>)["Content-Type"] = "application/json"
  }
  const apiKey = process.env.NEXT_PUBLIC_API_KEY
  if (apiKey) {
    (headers as Record<string, string>)["X-API-Key"] = apiKey
  }
  const res = await fetch(`${getApiBase()}${path}`, { ...init, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `API error ${res.status}`)
  }
  return res.json()
}
