import { afterEach, describe, expect, it, vi } from 'vitest';
import { changeRole, createEvent, createZone, getInventory, login, logout, me, myTickets, purchase, register, ApiError, displayPrice } from './coreApi';

const json = (data: unknown, status = 200, headers = {}) => ({ ok: status < 400, status, headers: { get: (name: string) => (headers as Record<string, string>)[name] ?? null }, json: async () => data });
afterEach(() => vi.unstubAllGlobals());

describe('Stage I authenticated frontend API', () => {
  it('registers a customer, logs in and verifies real identity', async () => {
    const mocked = vi.fn().mockResolvedValueOnce(json({ id: '1', role: 'customer' }, 201))
      .mockResolvedValueOnce(json({ access_token: 'temporary-secret' }))
      .mockResolvedValueOnce(json({ id: '1', role: 'customer' }));
    vi.stubGlobal('fetch', mocked);
    await register('customer_demo', 'secret-example-2026', 'Customer');
    const token = await login('customer_demo', 'secret-example-2026');
    expect(token).toBe('temporary-secret');
    expect((await me(token)).role).toBe('customer');
    expect(mocked.mock.calls[2][1].headers.Authorization).toBe('Bearer temporary-secret');
    expect(mocked.mock.calls[0][1].body).toContain('"display_name":"Customer"');
  });
  it('only uses authenticated owner and admin routes', async () => {
    const mocked = vi.fn().mockResolvedValueOnce(json({ id: 'e', status: 'draft' }, 201))
      .mockResolvedValueOnce(json({ id: 'z', mode: 'general' }, 201))
      .mockResolvedValueOnce(json({ id: 'u', role: 'event_owner' }));
    vi.stubGlobal('fetch', mocked);
    await createEvent('tok', { name: 'Evento', description: 'Ejemplo', venue: 'Lugar', start_at: '2028-01-01Z', end_at: '2028-01-02Z' });
    await createZone('tok', 'e', { name: 'General', mode: 'general', price_minor: 150000, currency: 'ARS', capacity: 2 });
    await changeRole('tok', 'u', 'event_owner');
    expect(mocked.mock.calls[0][0]).toContain('/api/v1/events');
    expect(mocked.mock.calls[1][0]).toContain('/events/e/zones');
    expect(mocked.mock.calls[2][0]).toContain('/admin/users/u/role');
  });
  it('uses a stable idempotency key and reports server replay header', async () => {
    const order = { id: 'o1', tickets: [{ id: 't1' }], total_minor: 150000, currency: 'ARS' };
    const mocked = vi.fn().mockResolvedValueOnce(json(order, 201, { 'Idempotent-Replayed': 'false' }))
      .mockResolvedValueOnce(json(order, 200, { 'Idempotent-Replayed': 'true' }));
    vi.stubGlobal('fetch', mocked);
    const body = { event_id: 'e1', items: [{ zone_id: 'z1', quantity: 1, seat_ids: [] }] };
    const first = await purchase('token', 'same-key', body);
    const replay = await purchase('token', 'same-key', body);
    expect(first.replayed).toBe(false);
    expect(replay.replayed).toBe(true);
    expect(first.data.id).toBe(replay.data.id);
    expect(mocked.mock.calls[0][1].headers['Idempotency-Key']).toBe('same-key');
    expect(mocked.mock.calls[1][1].headers['Idempotency-Key']).toBe('same-key');
  });
  it('propagates stock exhaustion and does not claim a purchase', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ detail: 'Insufficient capacity' }, 409)));
    await expect(purchase('tok', 'key', { event_id: 'e', items: [{ zone_id: 'z', quantity: 1, seat_ids: [] }] }))
      .rejects.toMatchObject({ status: 409, message: 'Insufficient capacity' });
  });
  it('supports ticket lists, inventory and logout', async () => {
    const mocked = vi.fn().mockResolvedValueOnce(json({ event_id: 'e', zones: [] }))
      .mockResolvedValueOnce(json({ items: [], total: 0, limit: 20, offset: 0 }))
      .mockResolvedValueOnce({ ok: true, status: 204, headers: { get: () => null } });
    vi.stubGlobal('fetch', mocked);
    expect((await getInventory('e')).zones).toEqual([]);
    expect((await myTickets('tok')).items).toEqual([]);
    await logout('tok');
    expect(mocked.mock.calls[2][0]).toContain('/auth/logout');
  });
  it('reports network failures explicitly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Offline')));
    await expect(login('u', 'p')).rejects.toBeInstanceOf(ApiError);
  });
  it('formats integer minor units', () => {
    expect(displayPrice(150000, 'ARS')).toContain('1.500');
  });
});
