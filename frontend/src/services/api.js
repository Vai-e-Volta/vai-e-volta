// Único ponto de acesso ao backend (Documento Técnico, seção 11.2).
// Páginas e componentes nunca chamam fetch diretamente.

const API_BASE = '/api';

const DEFAULT_ERROR_MESSAGE = 'Não foi possível concluir a ação. Tente novamente.';

export class ApiError extends Error {
  constructor({ status, code, message, fields }) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields ?? {};
  }
}

let unauthorizedHandler = null;

/**
 * Registra a função chamada quando a API responde 401 (RN-13): a sessão é limpa
 * e a pessoa é levada ao login. Retorna uma função para remover o registro.
 */
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = null;
  };
}

async function readBody(response) {
  if (response.status === 204) return null;
  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function toApiError(status, body) {
  const error = body?.error;
  return new ApiError({
    status,
    code: error?.code ?? (status >= 500 ? 'INTERNAL_ERROR' : 'UNKNOWN_ERROR'),
    message: error?.message ?? DEFAULT_ERROR_MESSAGE,
    fields: error?.fields ?? {},
  });
}

/**
 * Faz uma requisição à API.
 *
 * @param {string} path caminho relativo a /api (ex.: '/auth/me')
 * @param {object} [options]
 * @param {string} [options.method]
 * @param {object|FormData} [options.body] objeto (enviado como JSON) ou FormData
 * @param {boolean} [options.handleUnauthorized] quando false, um 401 não dispara o
 *   redirecionamento ao login (usado na verificação inicial da sessão)
 */
export async function request(path, { method = 'GET', body, handleUnauthorized = true } = {}) {
  const headers = { Accept: 'application/json' };
  let payload;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: payload,
      credentials: 'same-origin',
    });
  } catch {
    throw new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Sem conexão com o servidor. Verifique sua internet e tente novamente.',
    });
  }

  const data = await readBody(response);
  if (response.ok) return data;

  if (response.status === 401 && handleUnauthorized && unauthorizedHandler) {
    unauthorizedHandler();
  }
  throw toApiError(response.status, data);
}

export const api = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  delete: (path, body, options) => request(path, { ...options, method: 'DELETE', body }),
};

/** Usuário logado, ou erro 401 quando não há sessão. Não redireciona ao login. */
export function getCurrentUser() {
  return api.get('/auth/me', { handleUnauthorized: false });
}
