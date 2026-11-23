/** Public, read-only endpoints. No credentials or purchase calls. */
export type PublicEvent = {
  id: string;
  name: string;
  description: string;
  venue: string;
  start_at: string;
  end_at: string;
  status: 'published';
};

export type EventPage = {
  items: PublicEvent[];
  total: number;
  limit: number;
  offset: number;
};

const configuredBase = import.meta.env.VITE_API_BASE_URL?.trim() ?? '';
const apiBase = configuredBase.replace(/\/$/, '');

function isPublicEvent(value: unknown): value is PublicEvent {
  if (!value || typeof value !== 'object') return false;
  const event = value as Partial<PublicEvent>;
  return (
    typeof event.id === 'string' &&
    typeof event.name === 'string' &&
    typeof event.venue === 'string' &&
    typeof event.description === 'string' &&
    typeof event.start_at === 'string' &&
    typeof event.end_at === 'string' &&
    event.status === 'published'
  );
}

async function getJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(`${apiBase}${path}`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    signal,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<unknown>;
}

export async function fetchEvents(limit = 20, offset = 0, signal?: AbortSignal): Promise<EventPage> {
  const data = await getJson(`/api/v1/events?limit=${limit}&offset=${offset}`, signal);
  if (!data || typeof data !== 'object') throw new Error('Invalid events response');
  const page = data as Partial<EventPage>;
  if (!Array.isArray(page.items) || !page.items.every(isPublicEvent) ||
      !Number.isInteger(page.total) || !Number.isInteger(page.limit) ||
      !Number.isInteger(page.offset)) {
    throw new Error('Invalid events response');
  }
  return page as EventPage;
}

export async function fetchEvent(id: string, signal?: AbortSignal): Promise<PublicEvent> {
  const data = await getJson(`/api/v1/events/${encodeURIComponent(id)}`, signal);
  if (!isPublicEvent(data)) throw new Error('Invalid event response');
  return data;
}

export function formatEventDate(iso: string): string {
  const timestamp = new Date(iso);
  if (Number.isNaN(timestamp.getTime())) return 'Fecha por confirmar';
  return new Intl.DateTimeFormat('es-AR', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    timeZone: 'America/Argentina/Buenos_Aires',
  }).format(timestamp);
}
