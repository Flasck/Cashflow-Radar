const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AuthPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = AuthPayload & {
  full_name: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
};

export type UserResponse = {
  id: number;
  full_name: string;
  email: string;
  role: string;
};

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail ?? "Не удалось выполнить запрос");
  }

  return response.json() as Promise<T>;
}

export function registerUser(payload: RegisterPayload) {
  return request<UserResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function loginUser(payload: AuthPayload) {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
