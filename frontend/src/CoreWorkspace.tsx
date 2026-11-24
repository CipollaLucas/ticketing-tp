import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { fetchEvents, formatEventDate, type PublicEvent } from './eventApi';
import {
  changeRole, createEvent, createZone, displayPrice, getInventory,
  login, logout, me, myTickets, ownerEvents, publishEvent, purchase, register,
  type EventItem, type Identity, type Inventory, type Order, type PurchaseBody,
  type Role, type Ticket,
} from './coreApi';

type Tab = 'buy' | 'manage' | 'roles' | 'tickets';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Ocurrió un error inesperado.';
}

export default function CoreWorkspace() {
  const [token, setToken] = useState('');
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [tab, setTab] = useState<Tab>('buy');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState<PublicEvent[]>([]);
  const [eventId, setEventId] = useState('');
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [zoneId, setZoneId] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [selectedSeats, setSelectedSeats] = useState<string[]>([]);
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  const [result, setResult] = useState<{ order: Order; replayed: boolean } | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [managedEvents, setManagedEvents] = useState<EventItem[]>([]);
  const [draftName, setDraftName] = useState('');
  const [draftDescription, setDraftDescription] = useState('');
  const [draftVenue, setDraftVenue] = useState('');
  const [draftStart, setDraftStart] = useState('');
  const [draftEnd, setDraftEnd] = useState('');
  const [managedId, setManagedId] = useState('');
  const [zoneName, setZoneName] = useState('General');
  const [zoneMode, setZoneMode] = useState<'general' | 'numbered'>('general');
  const [zoneCapacity, setZoneCapacity] = useState(10);
  const [zonePrice, setZonePrice] = useState('1500');
  const [seatLabels, setSeatLabels] = useState('A1, A2, A3');
  const [roleUserId, setRoleUserId] = useState('');
  const [newRole, setNewRole] = useState<Role>('event_owner');

  const refreshEvents = useCallback(async () => {
    const page = await fetchEvents();
    setEvents(page.items);
  }, []);

  useEffect(() => {
    void refreshEvents().catch(e => setMessage(errorMessage(e)));
  }, [refreshEvents]);

  useEffect(() => {
    if (!eventId) { setInventory(null); return; }
    let active = true;
    getInventory(eventId).then(data => {
      if (!active) return;
      setInventory(data);
      setZoneId(data.zones[0]?.id ?? '');
    }).catch(e => { if (active) setMessage(errorMessage(e)); });
    return () => { active = false; };
  }, [eventId]);

  const zone = inventory?.zones.find(z => z.id === zoneId);
  const chosen = useMemo<PurchaseBody>(() => ({
    event_id: eventId,
    items: [{ zone_id: zoneId, quantity: zone?.mode === 'numbered' ? selectedSeats.length : quantity,
      seat_ids: zone?.mode === 'numbered' ? [...selectedSeats].sort() : [] }],
  }), [eventId, zoneId, zone?.mode, quantity, selectedSeats]);

  function clearAttempt() {
    setResult(null);
    setIdempotencyKey(crypto.randomUUID());
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setMessage('');
    try { await action(); }
    catch (error) { setMessage(errorMessage(error)); }
    finally { setBusy(false); }
  }

  async function authenticate(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      if (mode === 'register') await register(username, password, displayName);
      const credential = await login(username, password);
      const user = await me(credential);
      setToken(credential);
      setIdentity(user);
      setPassword('');
      setTab(user.role === 'event_owner' ? 'manage' : user.role === 'administrator' ? 'roles' : 'buy');
      setMessage(`Sesión iniciada como ${user.display_name} (${user.role}).`);
    });
  }

  async function signOut() {
    await run(async () => {
      try { if (token) await logout(token); }
      finally {
        setToken(''); setIdentity(null); setTickets([]); setResult(null);
        setIdempotencyKey(crypto.randomUUID());
      }
    });
  }

  async function loadManaged() {
    await run(async () => {
      const response = await ownerEvents(token);
      setManagedEvents(response.items);
      if (!managedId && response.items.length) setManagedId(response.items[0].id);
    });
  }

  async function createDraft(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      const created = await createEvent(token, {
        name: draftName, description: draftDescription, venue: draftVenue,
        start_at: new Date(draftStart).toISOString(),
        end_at: new Date(draftEnd).toISOString(),
      });
      setManagedId(created.id);
      setManagedEvents(prev => [...prev, created]);
      setMessage('Borrador creado. Ahora podés configurar su inventario.');
    });
  }

  async function addZone(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      await createZone(token, managedId, {
        name: zoneName, mode: zoneMode,
        price_minor: Math.round(Number(zonePrice) * 100),
        currency: 'ARS',
        ...(zoneMode === 'general'
          ? { capacity: zoneCapacity }
          : { seats: seatLabels.split(',').map(label => ({ label: label.trim() })).filter(s => s.label) }),
      });
      setMessage('Zona creada. Ya podés publicar el evento.');
    });
  }

  async function publish() {
    await run(async () => {
      await publishEvent(token, managedId);
      const response = await ownerEvents(token);
      setManagedEvents(response.items);
      await refreshEvents();
      setMessage('Evento publicado y disponible en el catálogo.');
    });
  }

  async function submitPurchase(e: FormEvent) {
    e.preventDefault();
    if (!zone || !eventId || !identity || identity.role !== 'customer') return;
    if (result) return;
    await run(async () => {
      // IMPORTANT: preserve key and payload on a network error; never mint a key on retry.
      const outcome = await purchase(token, idempotencyKey, chosen);
      setResult({ order: outcome.data, replayed: outcome.replayed });
      setMessage(outcome.replayed
        ? 'Reintento reconocido. Se devolvió la misma orden, sin emitir entradas nuevas.'
        : 'Compra simulada confirmada y registrada en PostgreSQL.');
      setInventory(await getInventory(eventId));
      setTickets((await myTickets(token)).items);
    });
  }

  async function loadTickets() {
    await run(async () => setTickets((await myTickets(token)).items));
  }

  function setPurchaseEvent(next: string) {
    setEventId(next); setZoneId(''); setSelectedSeats([]); setQuantity(1); clearAttempt();
  }

  const loginPanel = (
    <form className="form-panel" onSubmit={authenticate}>
      <span className="panel-number">IDENTIDAD REAL · API</span>
      <h2>{mode === 'login' ? 'Ingresá a tu cuenta.' : 'Creá una cuenta cliente.'}</h2>
      <label>Usuario<input autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)} /></label>
      {mode === 'register' && <label>Nombre visible<input required value={displayName} onChange={e => setDisplayName(e.target.value)} /></label>}
      <label>Contraseña<input type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={mode === 'register' ? 12 : 1} required value={password} onChange={e => setPassword(e.target.value)} /></label>
      <button className="btn btn-dark" disabled={busy} type="submit">{busy ? 'Procesando…' : mode === 'login' ? 'Iniciar sesión ↗' : 'Registrarme ↗'}</button>
      <button type="button" className="text-link" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setPassword(''); }}>
        {mode === 'login' ? 'Crear cuenta de cliente' : 'Ya tengo una cuenta'}
      </button>
      <p className="fine-print">La sesión real se mantiene solo en memoria. Al recargar la página se deberá iniciar sesión nuevamente. No hay pago bancario.</p>
    </form>
  );

  return <section className="inner-page core-workspace">
    <p className="eyebrow">ETAPA I / RECORRIDO FUNCIONAL</p>
    <h1 className="inner-title">La ticketera<br /><em>en acción.</em></h1>
    <p className="page-intro">Operaciones reales sobre la API de desarrollo. Las compras generan órdenes y tickets, pero no procesan pagos.</p>
    {message && <div className="notice" role="status">{message}</div>}
    {!identity ? loginPanel : <>
      <div className="core-identity">
        <span><strong>{identity.display_name}</strong> · {identity.role}</span>
        <button type="button" className="btn btn-outline" disabled={busy} onClick={() => void signOut()}>Cerrar sesión</button>
      </div>
      <div className="core-tabs">
        <button className={tab === 'buy' ? 'nav-active' : ''} onClick={() => setTab('buy')}>Eventos y compra</button>
        {identity.role === 'customer' && <button className={tab === 'tickets' ? 'nav-active' : ''} onClick={() => { setTab('tickets'); void loadTickets(); }}>Mis tickets</button>}
        {identity.role !== 'customer' && <button className={tab === 'manage' ? 'nav-active' : ''} onClick={() => { setTab('manage'); void loadManaged(); }}>Mis eventos</button>}
        {identity.role === 'administrator' && <button className={tab === 'roles' ? 'nav-active' : ''} onClick={() => setTab('roles')}>Roles</button>}
      </div>
      {tab === 'buy' && <div className="two-panels">
        <div className="form-panel">
          <span className="panel-number">01 / EVENTO PUBLICADO</span>
          <h2>Elegí tu evento.</h2>
          <button className="text-link" onClick={() => void run(refreshEvents)} disabled={busy}>Actualizar catálogo ↻</button>
          <label>Evento
            <select value={eventId} onChange={e => setPurchaseEvent(e.target.value)}>
              <option value="">Seleccionar evento</option>
              {events.map(event => <option key={event.id} value={event.id}>{event.name} · {formatEventDate(event.start_at)}</option>)}
            </select>
          </label>
          {!events.length && <p className="fine-print">Todavía no hay eventos futuros publicados. Ingresá como organizador para crear uno.</p>}
          {inventory && <label>Zona
            <select value={zoneId} onChange={e => { setZoneId(e.target.value); setSelectedSeats([]); clearAttempt(); }}>
              <option value="">Seleccionar zona</option>
              {inventory.zones.map(item => <option key={item.id} value={item.id}>{item.name} · {displayPrice(item.price_minor, item.currency)} · {item.available} disponibles</option>)}
            </select>
          </label>}
          {zone && <form onSubmit={submitPurchase}>
            <p className="fine-print">{zone.name} · {zone.mode === 'general' ? 'Zona general' : 'Asientos numerados'} · {zone.available} disponibles</p>
            {zone.mode === 'general' ? <label>Cantidad
              <input type="number" min="1" max={Math.min(100, zone.available)} required value={quantity} onChange={e => { setQuantity(Number(e.target.value)); clearAttempt(); }} />
            </label> : <fieldset className="core-seats"><legend>Elegí los asientos</legend>{zone.seats.map(seat => <label key={seat.id}><input type="checkbox" disabled={!seat.available || (busy || !!result)} checked={selectedSeats.includes(seat.id)} onChange={e => { setSelectedSeats(old => e.target.checked ? [...old, seat.id] : old.filter(id => id !== seat.id)); clearAttempt(); }} />{seat.label}</label>)}</fieldset>}
            <p><strong>Total estimado: {displayPrice(zone.price_minor * (zone.mode === 'general' ? quantity : selectedSeats.length), zone.currency)}</strong></p>
            <p className="fine-print">El servidor calcula el total definitivo. Esta operación crea tickets reales de prueba; no utiliza pasarela de pago.</p>
            {identity.role === 'customer' ? <button className="btn btn-dark" type="submit" disabled={busy || !!result || zone.available < 1 || (zone.mode === 'general' ? quantity < 1 || quantity > zone.available : !selectedSeats.length)}> {busy ? 'Confirmando…' : 'Confirmar compra simulada ↗'}</button> :
              <p className="fine-print">Para comprar debés iniciar sesión con una cuenta customer.</p>}
          </form>}
        </div>
        <aside className="side-panel">
          <span className="eyebrow">02 / RESULTADO</span>
          <h3>{result ? 'Compra confirmada' : 'Esperando confirmación'}</h3>
          {result ? <>
            <span className="soft-pill">{result.replayed ? 'REINTENTO RECONOCIDO' : 'ORDEN CONFIRMADA'}</span>
            <p>Orden: <code>{result.order.id}</code></p>
            <p>Tickets emitidos: {result.order.tickets.length}</p>
            <p className="price">{displayPrice(result.order.total_minor, result.order.currency)}</p>
            <button className="btn btn-outline" onClick={() => { clearAttempt(); setSelectedSeats([]); }}>Iniciar otra compra</button>
          </> : <p className="fine-print">Si hay un error de red, reintentá sin cambiar el formulario: la misma clave evita emitir tickets duplicados.</p>}
        </aside>
      </div>}
      {tab === 'tickets' && identity.role === 'customer' && <div className="form-panel">
        <h2>Mis tickets emitidos</h2><button className="btn btn-outline" disabled={busy} onClick={() => void loadTickets()}>Actualizar lista</button>
        {tickets.length ? tickets.map(ticket => <article className="core-ticket" key={ticket.id}><span className="soft-pill">{ticket.status}</span><p>Ticket <code>{ticket.id}</code></p><p>{ticket.seat_id ? `Asiento ${ticket.seat_id}` : 'Zona general'}</p></article>) : <p>Sin tickets en esta página de resultados.</p>}
        <p className="fine-print">El ticket no contiene QR ni representa una entrada pagada.</p>
      </div>}
      {tab === 'manage' && identity.role !== 'customer' && <div className="two-panels">
        <form className="form-panel" onSubmit={createDraft}>
          <span className="panel-number">ORGANIZADOR / NUEVO EVENTO</span><h2>Crear borrador</h2>
          <label>Nombre<input required value={draftName} onChange={e => setDraftName(e.target.value)} /></label>
          <label>Descripción<input required value={draftDescription} onChange={e => setDraftDescription(e.target.value)} /></label>
          <label>Lugar<input required value={draftVenue} onChange={e => setDraftVenue(e.target.value)} /></label>
          <label>Inicio<input required type="datetime-local" value={draftStart} onChange={e => setDraftStart(e.target.value)} /></label>
          <label>Fin<input required type="datetime-local" value={draftEnd} onChange={e => setDraftEnd(e.target.value)} /></label>
          <button className="btn btn-dark" disabled={busy}>Crear evento ↗</button>
        </form>
        <div className="form-panel">
          <span className="panel-number">INVENTARIO / PUBLICACIÓN</span><h2>Configurá entradas</h2>
          <button className="text-link" disabled={busy} onClick={() => void loadManaged()}>Actualizar mis eventos ↻</button>
          <label>Evento<select value={managedId} onChange={e => setManagedId(e.target.value)}>
            <option value="">Seleccionar borrador</option>{managedEvents.map(event => <option key={event.id} value={event.id}>{event.name} ({event.status})</option>)}
          </select></label>
          <form onSubmit={addZone}>
            <label>Zona<input required value={zoneName} onChange={e => setZoneName(e.target.value)} /></label>
            <label>Modalidad<select value={zoneMode} onChange={e => setZoneMode(e.target.value as 'general' | 'numbered')}><option value="general">General</option><option value="numbered">Numerada</option></select></label>
            {zoneMode === 'general' ? <label>Cupo<input type="number" min="1" max="1000000" value={zoneCapacity} onChange={e => setZoneCapacity(Number(e.target.value))} /></label> :
              <label>Asientos (separados por coma)<input value={seatLabels} onChange={e => setSeatLabels(e.target.value)} /></label>}
            <label>Precio en ARS<input type="number" min="0" max="21474836" step="0.01" required value={zonePrice} onChange={e => setZonePrice(e.target.value)} /></label>
            <button className="btn btn-outline" disabled={busy || !managedId || managedEvents.find(e => e.id === managedId)?.status !== 'draft'}>Agregar zona</button>
          </form>
          <button type="button" className="btn btn-dark" disabled={busy || !managedId || managedEvents.find(e => e.id === managedId)?.status !== 'draft'} onClick={() => void publish()}>Publicar evento ↗</button>
          <p className="fine-print">Publicar da visibilidad al evento. Para comprar debe existir una zona con stock.</p>
        </div>
      </div>}
      {tab === 'roles' && identity.role === 'administrator' && <form className="form-panel" onSubmit={e => { e.preventDefault(); void run(async () => { const user = await changeRole(token, roleUserId.trim(), newRole); setMessage(`Rol de ${user.username} actualizado a ${user.role}.`); }); }}>
        <span className="panel-number">ADMIN / PERMISOS</span><h2>Asignación de rol</h2>
        <label>UUID de otro usuario<input required value={roleUserId} onChange={e => setRoleUserId(e.target.value)} /></label>
        <label>Nuevo rol<select value={newRole} onChange={e => setNewRole(e.target.value as Role)}><option value="customer">Cliente</option><option value="event_owner">Organizador</option><option value="administrator">Administrador</option></select></label>
        <button className="btn btn-dark" disabled={busy}>Cambiar rol ↗</button>
        <p className="fine-print">No podés cambiar tu propio rol. El servidor controla todos los permisos.</p>
      </form>}
    </>}
  </section>;
}
