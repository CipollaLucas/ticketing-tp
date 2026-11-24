/** Stage I API client. Tokens only live in React memory, never in storage. */
export type Role = 'customer' | 'event_owner' | 'administrator';
export type Identity = { id: string; username: string; display_name: string; role: Role };
export type EventItem = { id: string; name: string; description: string; venue: string; start_at: string; end_at: string; status: 'draft' | 'published' };
export type Zone = { id: string; name: string; mode: 'general' | 'numbered'; price_minor: number; currency: string; capacity: number | null; available: number; seats: { id: string; label: string; available: boolean }[] };
export type Inventory = { event_id: string; zones: Zone[] };
export type Ticket = { id: string; order_item_id: string; zone_id: string; seat_id: string | null; status: string };
export type Order = { id: string; customer_id: string; event_id: string; status: string; currency: string; total_minor: number; tickets: Ticket[] };
type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type PurchaseBody = { event_id: string; items: { zone_id: string; quantity: number; seat_ids: string[] }[] };

const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim() ?? '';
const apiBase = configuredBase.replace(/\/$/, '');

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function api<T>(path: string, options: { method?: string; token?: string; body?: unknown; key?: string } = {}): Promise<{ data: T; replayed: boolean }> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.token) headers.Authorization = `Bearer ${options.token}`;
  if (options.key) headers['Idempotency-Key'] = options.key;
  let response: Response;
  try {
    response = await fetch(`${apiBase}/api/v1${path}`, {
      method: options.method ?? 'GET', headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, 'No se pudo conectar con el servidor. Podés reintentar la operación.');
  }
  if (!response.ok) {
    let detail = '';
    try {
      const payload: unknown = await response.json();
      if (payload && typeof payload === 'object' && 'detail' in payload) {
        const field = (payload as { detail: unknown }).detail;
        detail = typeof field === 'string' ? field : '';
      }
    } catch { /* Error HTTP sin JSON */ }
    const messages: Record<number, string> = {
      401: 'Sesión inválida o vencida. Volvé a iniciar sesión.',
      403: 'Tu usuario no tiene permisos para esta acción.',
      404: 'El recurso solicitado no existe.',
      409: 'Conflicto: la disponibilidad o el estado cambió. Verificá los datos.',
      422: 'Los datos enviados no son válidos.',
    };
    throw new ApiError(response.status, detail || messages[response.status] || `Error HTTP ${response.status}`);
  }
  const data = response.status === 204 ? null : await response.json() as T;
  return { data: data as T, replayed: response.headers.get('Idempotent-Replayed') === 'true' };
}

export async function register(username: string, password: string, display_name: string): Promise<Identity> {
  return (await api<Identity>('/auth/register', { method: 'POST', body: { username, password, display_name } })).data;
}
export async function login(username: string, password: string): Promise<string> {
  return (await api<{ access_token: string }>('/auth/login', { method: 'POST', body: { username, password } })).data.access_token;
}
export async function me(token: string): Promise<Identity> {
  return (await api<Identity>('/auth/me', { token })).data;
}
export async function logout(token: string): Promise<void> {
  await api<null>('/auth/logout', { method: 'POST', token });
}
export async function changeRole(token: string, userId: string, role: Role): Promise<Identity> {
  return (await api<Identity>(`/admin/users/${encodeURIComponent(userId)}/role`, { method: 'PATCH', token, body: { role } })).data;
}
export async function ownerEvents(token: string): Promise<Page<EventItem>> {
  return (await api<Page<EventItem>>('/owner/events', { token })).data;
}
export async function createEvent(token: string, body: Omit<EventItem, 'id' | 'status'>): Promise<EventItem> {
  return (await api<EventItem>('/events', { method: 'POST', token, body })).data;
}
export async function createZone(token: string, eventId: string, body: { name: string; mode: 'general' | 'numbered'; price_minor: number; currency: string; capacity?: number; seats?: { label: string }[] }): Promise<Zone> {
  return (await api<Zone>(`/events/${encodeURIComponent(eventId)}/zones`, { method: 'POST', token, body })).data;
}
export async function publishEvent(token: string, eventId: string): Promise<EventItem> {
  return (await api<EventItem>(`/events/${encodeURIComponent(eventId)}/publish`, { method: 'POST', token, body: {} })).data;
}
export async function getInventory(eventId: string): Promise<Inventory> {
  return (await api<Inventory>(`/events/${encodeURIComponent(eventId)}/inventory`)).data;
}
export async function purchase(token: string, key: string, body: PurchaseBody): Promise<{ data: Order; replayed: boolean }> {
  return api<Order>('/orders', { method: 'POST', token, key, body });
}
export async function myTickets(token: string): Promise<Page<Ticket>> {
  return (await api<Page<Ticket>>('/me/tickets', { token })).data;
}
export function displayPrice(minor: number, currency: string): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency }).format(minor / 100);
}
