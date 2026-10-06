const BASE_URL = ""; // Relative proxy through Vite or served directly

export function expireSession() {
  localStorage.removeItem("myairouter_token");
  window.dispatchEvent(new Event("myairouter:session-expired"));
}

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem("myairouter_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiRequestWithMeta<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<{ data: T; headers: Headers }> {
  const headers = {
    "Content-Type": "application/json",
    ...getAuthHeader(),
    ...(options.headers || {}),
  };

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401 && !path.includes("/auth/login")) {
    expireSession();
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    const body = await response.text();
    let errorDetail = body || `Error ${response.status}`;
    try {
      const errJson = JSON.parse(body);
      if (errJson.detail) {
        errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      } else if (errJson.error?.message) {
        errorDetail = errJson.error.message;
      }
    } catch {}
    throw new Error(errorDetail);
  }

  const data = await response.json();
  return { data, headers: response.headers };
}

export async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { data } = await apiRequestWithMeta<T>(path, options);
  return data;
}
