import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchEvent, fetchEvents, formatEventDate } from './eventApi';

const event = {
  id: 'fded9f06-7518-43d4-8cee-c8d9cbf61321',
  name: 'Festival real',
  description: 'Música en vivo',
  venue: 'Centro Cultural',
  start_at: '2027-05-15T23:00:00Z',
  end_at: '2027-05-16T02:00:00Z',
  status: 'published',
};

afterEach(() => vi.unstubAllGlobals());

describe('public events API', () => {
  it('accepts the published list contract with pagination', async () => {
    const mocked = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [event], total: 1, limit: 20, offset: 0 }) });
    vi.stubGlobal('fetch', mocked);
    const page = await fetchEvents();
    expect(page.items[0].name).toBe('Festival real');
    expect(page.total).toBe(1);
    expect(mocked.mock.calls[0][0]).toContain('/api/v1/events?limit=20&offset=0');
  });

  it('accepts an empty catalog', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 0, limit: 20, offset: 0 }) }));
    expect((await fetchEvents()).items).toEqual([]);
  });

  it('rejects failed responses without showing placeholder events', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }));
    await expect(fetchEvents()).rejects.toThrow('HTTP 503');
  });

  it('rejects unpublished or malformed events returned by the server', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ...event, status: 'draft' }) }));
    await expect(fetchEvent(event.id)).rejects.toThrow('Invalid event response');
  });

  it('propagates 404 on missing detail and encodes its path segment', async () => {
    const mocked = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    vi.stubGlobal('fetch', mocked);
    await expect(fetchEvent('not/a/uuid')).rejects.toThrow('HTTP 404');
    expect(mocked.mock.calls[0][0]).toContain('not%2Fa%2Fuuid');
  });

  it('formats dates in Buenos Aires rather than naive browser timezone', () => {
    expect(formatEventDate('2027-05-15T23:00:00Z')).toContain('20:00');
  });
});
