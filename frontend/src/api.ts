const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

type ErrorPayload = {
  detail?: unknown;
  error?: unknown;
  error_description?: unknown;
  message?: unknown;
  msg?: unknown;
};

type SupabaseSignupResponse = {
  user?: {
    identities?: unknown[] | null;
  } | null;
};

type EmailAvailabilityResponse = {
  available: boolean;
};

function friendlyErrorMessage(message: string): string {
  const normalized = message.trim();
  const lower = normalized.toLowerCase();

  if (!normalized) {
    return "Something went wrong. Please try again.";
  }

  if (lower.includes("invalid login credentials")) {
    return "Invalid email or password.";
  }

  if (
    lower.includes("user already registered") ||
    lower.includes("already exists") ||
    lower.includes("already been registered") ||
    lower.includes("already been taken")
  ) {
    return "An account with this email already exists. Please log in instead.";
  }

  if (lower.includes("email not confirmed")) {
    return "Please confirm your email address before logging in.";
  }

  if (lower.includes("password should be at least") || lower.includes("password must be at least")) {
    return "Password must be at least 8 characters.";
  }

  if (
    lower.includes("unable to validate email address") ||
    lower.includes("invalid email") ||
    (lower.includes("email address") && lower.includes("invalid"))
  ) {
    return "Use an email address with a real public domain, such as name@example.com.";
  }

  if (lower.includes("rate limit") || lower.includes("too many")) {
    return "Too many attempts. Please wait a moment and try again.";
  }

  return normalized;
}

function messageFromDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }
        if (item && typeof item === "object" && "msg" in item) {
          const msg = (item as { msg?: unknown }).msg;
          return typeof msg === "string" ? msg : null;
        }
        return null;
      })
      .filter((item): item is string => Boolean(item));

    if (messages.length > 0) {
      return messages.join(" ");
    }
  }

  return null;
}

function messageFromErrorPayload(payload: ErrorPayload): string | null {
  const detailMessage = messageFromDetail(payload.detail);
  if (detailMessage) {
    return detailMessage;
  }

  for (const key of ["error_description", "message", "msg", "error"] as const) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }

  return null;
}

function parseErrorBody(text: string, fallback: string): string {
  if (!text.trim()) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(text) as ErrorPayload;
    return friendlyErrorMessage(messageFromErrorPayload(parsed) || fallback);
  } catch {
    return friendlyErrorMessage(text);
  }
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  const text = await response.text();
  return new Error(parseErrorBody(text, fallback || `Request failed with ${response.status}`));
}

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
    throw await responseError(response, `Request failed with ${response.status}`);
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
    throw await responseError(response, "Supabase login failed");
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

  const availability = await apiRequest<EmailAvailabilityResponse>("/auth/email-availability", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  if (!availability.available) {
    throw new Error("An account with this email already exists. Please log in instead.");
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
    throw await responseError(response, "Supabase signup failed");
  }

  const data = (await response.json()) as SupabaseSignupResponse;
  if (Array.isArray(data.user?.identities) && data.user.identities.length === 0) {
    throw new Error("An account with this email already exists. Please log in instead.");
  }
}

export function wsUrl(path: string, token: string): string {
  const base =
    import.meta.env.VITE_WS_BASE_URL ||
    `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/api/v1`;
  const separator = path.includes("?") ? "&" : "?";
  return `${base}${path}${separator}token=${encodeURIComponent(token)}`;
}
