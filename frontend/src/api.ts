import { translate } from './i18n';
const BASE =
  import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

type Tokens = {
  access_token: string;
  refresh_token: string;
};

const SESSION_KEY = 'genlab_tokens';

function isTokens(value: unknown): value is Tokens {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.access_token === 'string' &&
    candidate.access_token.length > 0 &&
    typeof candidate.refresh_token === 'string' &&
    candidate.refresh_token.length > 0
  );
}

function readStoredTokens(): Tokens | null {
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;

    const parsed: unknown = JSON.parse(raw);
    if (isTokens(parsed)) return parsed;

    window.localStorage.removeItem(SESSION_KEY);
    return null;
  } catch {
    // Un valor de una versión anterior o un almacenamiento no disponible no
    // debe impedir que React muestre la pantalla de inicio de sesión.
    try {
      window.localStorage.removeItem(SESSION_KEY);
    } catch {
      // Algunos navegadores pueden bloquear por completo localStorage.
    }
    return null;
  }
}

function persistTokens(value: Tokens | null): void {
  try {
    if (value) {
      window.localStorage.setItem(SESSION_KEY, JSON.stringify(value));
    } else {
      window.localStorage.removeItem(SESSION_KEY);
    }
  } catch {
    // La sesión continuará en memoria aunque el navegador bloquee storage.
  }
}

let tokens: Tokens | null = readStoredTokens();

export const session = {
  get: () => tokens,
  set: (value: Tokens | null) => {
    tokens = value;
    persistTokens(value);
  },
};

async function refresh(): Promise<string> {
  if (!tokens) throw new Error(translate('api.noSession'));

  const response = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });

  if (!response.ok) {
    session.set(null);
    throw new Error(translate('api.sessionExpired'));
  }

  const refreshed = (await response.json()) as Tokens;
  session.set(refreshed);
  return refreshed.access_token;
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (tokens) headers.set('Authorization', `Bearer ${tokens.access_token}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  let response = await fetch(BASE + path, { ...init, headers });

  if (
    response.status === 401 &&
    tokens &&
    retry &&
    !path.startsWith('/auth/')
  ) {
    headers.set('Authorization', `Bearer ${await refresh()}`);
    response = await fetch(BASE + path, { ...init, headers });
  }

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Mantener el mensaje HTTP cuando la respuesta no es JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export { BASE };

export async function download(
  path: string,
  filename: string,
): Promise<void> {
  const headers = new Headers();
  if (tokens) headers.set('Authorization', `Bearer ${tokens.access_token}`);

  let response = await fetch(BASE + path, { headers });
  if (response.status === 401 && tokens) {
    headers.set('Authorization', `Bearer ${await refresh()}`);
    response = await fetch(BASE + path, { headers });
  }

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // La respuesta puede no ser JSON.
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Firefox puede requerir que la URL permanezca activa hasta que la
  // descarga haya comenzado.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}


export async function downloadJson(
  path: string,
  filename: string,
): Promise<void> {
  const payload = await api<unknown>(path);
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
