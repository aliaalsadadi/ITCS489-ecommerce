const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

function buildHeaders(token?: string, headers?: HeadersInit, body?: BodyInit | null): Headers {
  const h = new Headers(headers || {});
  if (body instanceof FormData) {
    h.delete("Content-Type");
  } else if (!h.has("Content-Type")) {
    h.set("Content-Type", "application/json");
  }
  if (token) {
    h.set("Authorization", `Bearer ${token}`);
  }
  return h;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: buildHeaders(token, options.headers, options.body),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}

export async function signInWithPassword(email: string, password: string): Promise<string> {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new Error("Missing Supabase frontend env values.");
  }

  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: {
      apikey: SUPABASE_ANON_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Supabase login failed");
  }

  const data = (await response.json()) as { access_token?: string };
  if (!data.access_token) {
    throw new Error("No access_token returned from Supabase");
  }

  return data.access_token;
}

export async function signUpWithPassword(email: string, password: string, displayName?: string): Promise<void> {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new Error("Missing Supabase frontend env values.");
  }

  const response = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
    method: "POST",
    headers: {
      apikey: SUPABASE_ANON_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      password,
      data: displayName ? { full_name: displayName } : undefined,
    }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Supabase signup failed");
  }
}

export function wsUrl(path: string, token: string): string {
  const base =
    import.meta.env.VITE_WS_BASE_URL ||
    `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/api/v1`;
  const separator = path.includes("?") ? "&" : "?";
  return `${base}${path}${separator}token=${encodeURIComponent(token)}`;
}
