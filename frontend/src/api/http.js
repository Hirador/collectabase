// Cookie-based session transport.
// - credentials:'include' sends the httpOnly access cookie on every request.
// - On unsafe methods we echo the cb_csrf cookie as X-CSRF-Token (double-submit).
// - X-Collection-Id selects the active collection (workspace).
// - A 401 triggers one silent refresh; if that fails we broadcast auth:expired
//   so the app can redirect to the login screen.

const ACTIVE_COLLECTION_STORAGE = 'collectabase.active_collection'
const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

function readCookie(name) {
  if (typeof document === 'undefined') return ''
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : ''
}

export function getActiveCollectionId() {
  if (typeof window === 'undefined') return ''
  try {
    return String(window.localStorage.getItem(ACTIVE_COLLECTION_STORAGE) || '').trim()
  } catch {
    return ''
  }
}

export function setActiveCollectionId(value) {
  if (typeof window === 'undefined') return
  try {
    const cleaned = String(value || '').trim()
    if (cleaned) window.localStorage.setItem(ACTIVE_COLLECTION_STORAGE, cleaned)
    else window.localStorage.removeItem(ACTIVE_COLLECTION_STORAGE)
  } catch {
    // ignore storage errors
  }
}

function withSessionHeaders(method, headers = {}) {
  const result = { ...(headers || {}) }
  const collectionId = getActiveCollectionId()
  if (collectionId) result['X-Collection-Id'] = collectionId
  if (UNSAFE.has(method.toUpperCase())) {
    const csrf = readCookie('cb_csrf')
    if (csrf) result['X-CSRF-Token'] = csrf
  }
  return result
}

async function parseJsonSafe(res) {
  try {
    return await res.json()
  } catch {
    return null
  }
}

function getFilenameFromDisposition(disposition) {
  if (!disposition) return null
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1])
  const asciiMatch = disposition.match(/filename=\"?([^\";]+)\"?/i)
  return asciiMatch?.[1] || null
}

let refreshPromise = null

function notifyExpired() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('auth:expired'))
  }
}

async function tryRefresh() {
  // Collapse concurrent refreshes into a single in-flight request.
  if (!refreshPromise) {
    refreshPromise = fetch('/api/auth/refresh', {
      method: 'POST',
      credentials: 'include',
      headers: withSessionHeaders('POST'),
    })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

// Core fetch with one transparent refresh-retry on 401.
async function coreFetch(url, init = {}, { allowRefresh = true } = {}) {
  const res = await fetch(url, { credentials: 'include', ...init })
  if (res.status === 401 && allowRefresh && !url.startsWith('/api/auth/')) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      return fetch(url, { credentials: 'include', ...init })
    }
    notifyExpired()
  }
  return res
}

export async function apiGet(url) {
  const res = await coreFetch(url, { headers: withSessionHeaders('GET') })
  const data = await parseJsonSafe(res)
  return { ok: res.ok, status: res.status, data }
}

export async function apiDelete(url) {
  const res = await coreFetch(url, { method: 'DELETE', headers: withSessionHeaders('DELETE') })
  const data = await parseJsonSafe(res)
  return { ok: res.ok, status: res.status, data }
}

export async function apiPost(url, body, options = {}) {
  const init = { method: 'POST', ...options }
  const customHeaders = withSessionHeaders('POST', options.headers || {})
  if (body !== undefined) {
    init.headers = { 'Content-Type': 'application/json', ...customHeaders }
    init.body = JSON.stringify(body)
  } else {
    init.headers = customHeaders
  }
  const res = await coreFetch(url, init)
  const data = await parseJsonSafe(res)
  return { ok: res.ok, status: res.status, data }
}

export async function apiPut(url, body) {
  const res = await coreFetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...withSessionHeaders('PUT') },
    body: JSON.stringify(body),
  })
  const data = await parseJsonSafe(res)
  return { ok: res.ok, status: res.status, data }
}

export async function apiPatch(url, body) {
  const res = await coreFetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...withSessionHeaders('PATCH') },
    body: JSON.stringify(body),
  })
  const data = await parseJsonSafe(res)
  return { ok: res.ok, status: res.status, data }
}

export async function apiPostForm(url, formData) {
  const res = await coreFetch(url, { method: 'POST', headers: withSessionHeaders('POST'), body: formData })
  const data = await parseJsonSafe(res)
  return { ok: res.ok, status: res.status, data }
}

export async function apiDownload(url, fallbackFilename = 'download.bin') {
  const res = await coreFetch(url, { headers: withSessionHeaders('GET') })
  if (!res.ok) {
    const data = await parseJsonSafe(res)
    return { ok: false, status: res.status, data }
  }

  const blob = await res.blob()
  const disposition = res.headers.get('content-disposition')
  const filename = getFilenameFromDisposition(disposition) || fallbackFilename
  const objectUrl = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = filename
    a.click()
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
  return { ok: true, status: res.status, data: { filename } }
}

// --- deprecated admin-key shims (kept so legacy imports still compile) -------
// Auth is now cookie-based; these are inert. Remove once Settings.vue drops the
// old admin-key panel.
export function getAdminApiKey() {
  return ''
}

export function setAdminApiKey() {
  // no-op
}
