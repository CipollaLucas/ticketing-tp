import { useEffect, useState } from 'react';
import { fetchEvent, fetchEvents, formatEventDate, type PublicEvent } from './eventApi';
import CoreWorkspace from './CoreWorkspace';
import './App.css';

type Page = 'catalog' | 'detail' | 'access' | 'checkout' | 'tickets' | 'owner' | 'admin' | 'workspace';
type Role = 'visitor' | 'customer' | 'event_owner' | 'administrator';
type CatalogState = 'ready' | 'loading' | 'empty' | 'error';
type SourceMode = 'live' | 'demo';

const sampleEvents = [
  { id: 'bands', type: 'EN VIVO · MÚSICA', title: 'Noche de bandas', date: '15 MAY 2027 · 20:00', venue: 'Centro Cultural · La Plata', price: 'ARS 12.000', poster: 'lime', word: 'La ciudad\nsuena.', description: 'Una noche para encontrarnos con bandas locales y música en vivo.' },
  { id: 'tech', type: 'COMUNIDAD · TECNOLOGÍA', title: 'Jornada de tecnología', date: '22 MAY 2027 · 10:00', venue: 'Auditorio · La Plata', price: 'Venta no habilitada', poster: 'peach', word: 'Ideas que\nconectan.', description: 'Charlas y encuentros para compartir nuevas ideas.' },
  { id: 'art', type: 'CULTURA · ENCUENTRO', title: 'Festival creativo', date: '30 MAY 2027 · 17:00', venue: 'Espacio Cultural · Buenos Aires', price: 'Próximamente', poster: 'lavender', word: 'Crear es\ncompartir.', description: 'Una tarde dedicada al arte, la cultura y la creatividad.' },
] as const;

function initialPage(): Page {
  if (typeof window === 'undefined') return 'catalog';
  const value = window.location.hash.slice(1);
  return (['catalog', 'detail', 'access', 'checkout', 'tickets', 'owner', 'admin', 'workspace'] as string[]).includes(value)
    ? value as Page : 'catalog';
}

export default function App() {
  const [page, setPage] = useState<Page>(initialPage);
  const [role, setRole] = useState<Role>('visitor');
  const [catalogState, setCatalogState] = useState<CatalogState>('ready');
  const [sourceMode, setSourceMode] = useState<SourceMode>('live');
  const [liveState, setLiveState] = useState<CatalogState>('loading');
  const [liveEvents, setLiveEvents] = useState<PublicEvent[]>([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selectedLiveEvent, setSelectedLiveEvent] = useState<PublicEvent | null>(null);
  const [detailState, setDetailState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [eventId, setEventId] = useState('bands');
  const [quantity, setQuantity] = useState(1);
  const [zone, setZone] = useState<'general' | 'numbered'>('general');
  const [notice, setNotice] = useState('');
  const isDemo = sourceMode === 'demo';
  const catalogViewState = isDemo ? catalogState : liveState;
  const cards = isDemo
    ? [...sampleEvents]
    : liveEvents.map((event, index) => ({
      id: event.id,
      type: 'EVENTO PUBLICADO · VENTA NO HABILITADA',
      title: event.name,
      date: formatEventDate(event.start_at),
      venue: event.venue,
      price: 'Venta no habilitada',
      poster: (['lime', 'peach', 'lavender'] as const)[index % 3],
      word: event.name,
      description: event.description,
    }));
  const currentEvent = isDemo
    ? (sampleEvents.find(event => event.id === eventId) ?? sampleEvents[0])
    : selectedLiveEvent
      ? {
        id: selectedLiveEvent.id, type: 'EVENTO PUBLICADO', title: selectedLiveEvent.name,
        date: formatEventDate(selectedLiveEvent.start_at),
        venue: selectedLiveEvent.venue, price: 'Venta no habilitada',
        poster: 'lime', word: selectedLiveEvent.name,
        description: selectedLiveEvent.description,
      }
      : sampleEvents[0];

  useEffect(() => {
    if (isDemo) return;
    const controller = new AbortController();
    fetchEvents(20, offset, controller.signal).then(result => {
      if (controller.signal.aborted) return;
      setLiveEvents(result.items);
      setTotalEvents(result.total);
      setLiveState(result.items.length ? 'ready' : 'empty');
    }).catch(() => {
      if (!controller.signal.aborted) setLiveState('error');
    });
    return () => controller.abort();
  }, [isDemo, offset]);

  useEffect(() => {
    if (isDemo || page !== 'detail') return;
    const controller = new AbortController();
    fetchEvent(eventId, controller.signal).then(event => {
      if (controller.signal.aborted) return;
      setSelectedLiveEvent(event);
      setDetailState('ready');
    }).catch(() => {
      if (!controller.signal.aborted) setDetailState('error');
    });
    return () => controller.abort();
  }, [isDemo, page, eventId]);

  function chooseEvent(id: string) {
    setEventId(id);
    if (!isDemo) {
      setSelectedLiveEvent(null);
      setDetailState('loading');
    }
    navigate('detail');
  }

  function switchMode(mode: SourceMode) {
    setSourceMode(mode);
    setOffset(0);
    setLiveState('loading');
    setSelectedLiveEvent(null);
    navigate('catalog');
  }


  function navigate(next: Page) {
    setPage(next);
    setNotice('');
    window.location.hash = next;
    window.scrollTo({ top: 0, behavior: 'auto' });
  }

  function demoAction(action = 'Esta acción') {
    setNotice(`${action} es una demostración: no se enviaron datos ni se modificó el sistema.`);
  }

  function selectRole(next: Role) {
    setRole(next);
    navigate(next === 'customer' ? 'tickets' : next === 'event_owner' ? 'owner' : next === 'administrator' ? 'admin' : 'catalog');
  }

  return (
    <div className="app">
      <a className="skip-link" href="#page-content">Ir al contenido</a>
      <div className="preview-banner"><span className="preview-dot" /> {isDemo ? 'MODO DEMOSTRACIÓN · DATOS FICTICIOS · SIN COMPRAS NI SESIONES REALES' : 'ETAPA I · CATÁLOGO REAL CONECTADO · COMPRA SIMULADA EN OPERAR TICKETERA'}</div>
      <header className="site-header">
        <button className="brand" type="button" onClick={() => navigate('catalog')}>ticketing<span className="brand-mark">.</span><span className="brand-suffix">/ tp</span></button>
        <nav aria-label="Navegación principal">
          <button className={page === 'catalog' ? 'nav-active' : ''} onClick={() => navigate('catalog')}>Explorar</button>
          <button className={page === 'access' ? 'nav-active' : ''} onClick={() => navigate('access')}>Acceder</button>
          <button className={page === 'workspace' ? 'nav-active' : ''} onClick={() => { setSourceMode('live'); navigate('workspace'); }}>Operar ticketera</button>
          {role === 'customer' && <button onClick={() => navigate('tickets')}>Mis tickets</button>}
          {role === 'event_owner' && <button onClick={() => navigate('owner')}>Mis eventos</button>}
          {role === 'administrator' && <button onClick={() => navigate('admin')}>Administración</button>}
        </nav>
        <label className="role-selector">Catálogo
          <select aria-label="Fuente de eventos" value={sourceMode} onChange={event => switchMode(event.target.value as SourceMode)}><option value="live">Eventos reales</option><option value="demo">Demostración</option></select>
        </label>
        <label className="role-selector">Ver como
          <select value={role} onChange={event => selectRole(event.target.value as Role)}>
            <option value="visitor">Visitante</option><option value="customer">Cliente</option>
            <option value="event_owner">Organizador</option><option value="administrator">Administrador</option>
          </select>
        </label>
      </header>
      {!isDemo && page === 'checkout' && <div className="notice" role="status">Las compras no están habilitadas. Volvé al catálogo.</div>}
      {notice && <div className="notice" role="status"><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Cerrar aviso">×</button></div>}

      <main id="page-content" tabIndex={-1}>
        {page === 'workspace' && <CoreWorkspace />}
        {page === 'catalog' && <>
          <section className="hero">
            <div className="hero-copy"><p className="eyebrow">LA AGENDA QUE NOS REÚNE <span className="eyebrow-line" /></p>
              <h1>Algo bueno<br /><em>está por pasar.</em></h1>
              <p>Descubrí música, encuentros y experiencias que valen la pena vivir. Tu próximo plan empieza acá.</p>
              <button className="btn btn-dark" onClick={() => document.getElementById('events-heading')?.scrollIntoView({ behavior: 'smooth' })}>Explorar eventos <span>↗</span></button>
            </div>
            <div className="hero-art" aria-hidden="true"><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" /><span className="hero-art-small">HACÉ LUGAR<br />A LO NUEVO</span><strong>EN<br />VIVO<span>✳</span></strong><span className="hero-art-bottom">2027 / EXPERIENCIAS</span></div>
          </section>
          <section className="events-section">
            <div className="section-head"><div><p className="eyebrow">01 / DESCUBRIR</p><h2 id="events-heading">Planes para vos<span className="title-dot">.</span></h2></div>
              {isDemo && <label className="state-select">Estado de muestra <select value={catalogState} onChange={event => setCatalogState(event.target.value as CatalogState)}>
                <option value="ready">Con resultados</option><option value="loading">Cargando</option><option value="empty">Sin eventos</option><option value="error">Error de red</option>
              </select></label>}
            </div>
            {catalogViewState !== 'ready' ? <div className="empty-state" role="status"><span className="empty-icon">◎</span><h3>{catalogViewState === 'loading' ? 'Buscando experiencias…' : catalogViewState === 'empty' ? 'Todavía no hay eventos' : 'No pudimos cargar los eventos'}</h3><p>{catalogViewState === 'loading' ? (isDemo ? 'Estado de carga de demostración.' : 'Consultando el servidor de eventos.') : catalogViewState === 'empty' ? 'Los eventos publicados van a aparecer acá.' : (isDemo ? 'Probá nuevamente más tarde. La conexión es simulada.' : 'No fue posible consultar la API. Verificá que el backend esté iniciado.')}</p></div> : <div className="event-grid">{cards.map((item, index) => <article className="event-card" key={item.id}>
              <button className={`event-poster ${item.poster}`} onClick={() => chooseEvent(item.id)} aria-label={`Ver ${item.title}`}><span className="poster-index">0{index + 1} / 2027</span><strong>{item.word}</strong><span className="poster-arrow">↗</span></button>
              <div className="event-info"><span className="eyebrow">{item.type}</span><h3>{item.title}</h3><p>{item.date} · {item.venue}</p><div className="event-bottom"><strong>{item.price}</strong><button className="text-link" onClick={() => chooseEvent(item.id)}>Ver evento ↗</button></div></div>
            </article>)}</div>}
            {!isDemo && catalogViewState === 'ready' && <div className="page-controls">
              <button className="btn btn-outline" disabled={offset === 0} onClick={() => { setLiveState('loading'); setOffset(Math.max(0, offset - 20)); }}>← Anteriores</button>
              <span>Mostrando {offset + 1}–{Math.min(offset + liveEvents.length, totalEvents)} de {totalEvents}</span>
              <button className="btn btn-outline" disabled={offset + liveEvents.length >= totalEvents} onClick={() => { setLiveState('loading'); setOffset(offset + 20); }}>Siguientes →</button>
            </div>}
            <p className="disclaimer">{isDemo ? 'Los eventos y precios son ficticios. Cambiá a Eventos reales para consultar el backend.' : 'Eventos publicados desde FastAPI. Para comprar entradas de prueba utilizá Operar ticketera.'}</p>
          </section>
        </>}

        {page === 'detail' && (!isDemo && detailState !== 'ready' ? <section className="inner-page"><button className="back-link" onClick={() => navigate('catalog')}>← Volver al catálogo</button><div className="empty-state" role="status">{detailState === 'loading' ? 'Cargando evento…' : 'No se pudo mostrar este evento. Puede no existir o ya no estar publicado.'}</div></section> : currentEvent && <section className="inner-page"><button className="back-link" onClick={() => navigate('catalog')}>← Volver al catálogo</button><p className="eyebrow">{currentEvent.type} · {isDemo ? 'EVENTO DE DEMOSTRACIÓN' : 'EVENTO PUBLICADO'}</p><h1 className="inner-title">{currentEvent.title}<span className="title-dot">.</span></h1>
          <div className="detail-grid"><div><div className={`detail-poster ${currentEvent.poster}`}><span>EXPERIENCIA / 2027</span><strong>{currentEvent.word}</strong></div><h2>Nos encontramos ahí.</h2><p className="long-copy">{currentEvent.description} {isDemo ? 'Este evento es ficticio y sirve para validar la experiencia visual.' : 'Información del evento publicada por su organizador.'}</p><dl className="info-list"><dt>Cuándo</dt><dd>{currentEvent.date}</dd><dt>Dónde</dt><dd>{currentEvent.venue}</dd></dl></div><aside className="side-panel"><span className="eyebrow">ENTRADAS</span><h3>{isDemo ? 'Elegí tu experiencia' : 'Próximamente'}</h3>{isDemo && <p>Zona general · sin numeración</p>}<p className="price">{currentEvent.price}</p>{isDemo ? <><span className="soft-pill">Disponibilidad de muestra</span><button className="btn btn-dark btn-block" onClick={() => navigate('checkout')}>Ver compra simulada ↗</button><p className="fine-print">El precio y el cupo reales deben confirmarse en el servidor. No se venden entradas en esta demo.</p></> : <p className="fine-print">Para consultar zonas disponibles y comprar entradas de prueba, ingresá en Operar ticketera. No se procesan pagos.</p>}</aside></div>
        </section>)}

        {page === 'access' && <section className="inner-page"><p className="eyebrow">IDENTIDAD / DEMOSTRACIÓN</p><h1 className="inner-title">Tu lugar<br /><em>empieza acá.</em></h1><p className="page-intro">Vista visual de ingreso y registro. No introduzcas datos reales.</p><div className="two-panels">
          <div className="form-panel"><span className="panel-number">01 / INGRESAR</span><h2>Qué bueno verte.</h2><label>Usuario de ejemplo<input readOnly value="cliente_demo" /></label><p className="fine-print">El formulario real pedirá contraseña y llamará a /api/v1/auth/login.</p><button className="btn btn-dark" onClick={() => demoAction('El inicio de sesión')}>Simular acceso ↗</button></div>
          <div className="form-panel alt-panel"><span className="panel-number">02 / REGISTRARSE</span><h2>Sumate al plan.</h2><label>Nombre visible de ejemplo<input readOnly value="Ana" /></label><p className="fine-print">El registro real requiere usuario, contraseña y nombre. Crea únicamente cuentas de cliente.</p><button className="btn btn-outline" onClick={() => demoAction('El registro')}>Simular registro ↗</button></div>
        </div></section>}

        {page === 'checkout' && isDemo && <section className="inner-page"><button className="back-link" onClick={() => navigate('detail')}>← Volver al evento</button><p className="eyebrow">COMPRA / RECORRIDO SIMULADO</p><h1 className="inner-title">Tu próximo<br /><em>recuerdo.</em></h1><div className="detail-grid"><form className="form-panel" onSubmit={event => { event.preventDefault(); demoAction('La confirmación de compra'); }}><h2>Seleccioná tu entrada</h2><label>Zona<select value={zone} onChange={event => setZone(event.target.value as 'general' | 'numbered')}><option value="general">General · sin numerar</option><option value="numbered">Platea · numerada (ejemplo)</option></select></label><label>Cantidad<input type="number" min="1" max="4" required value={quantity} onChange={event => setQuantity(Number(event.target.value))} /></label><p className="fine-print">{zone === 'general' ? 'La zona general no necesita seleccionar asientos.' : 'La selección de asientos numerados se desarrollará con el módulo de inventario.'}</p><button className="btn btn-dark" type="submit">Probar confirmación ↗</button></form>
          <aside className="side-panel"><span className="eyebrow">RESUMEN DE EJEMPLO</span><h3>{currentEvent.title}</h3><p>{quantity} {quantity === 1 ? 'entrada' : 'entradas'} · {zone === 'general' ? 'General' : 'Platea'}</p><p className="price">{currentEvent.price}</p><p className="fine-print">No se realizan pagos, reservas ni emisiones de tickets. El total mostrado no se calcula en el servidor.</p><button className="text-link" onClick={() => navigate('tickets')}>Ver tickets de ejemplo ↗</button></aside></div></section>}

        {page === 'tickets' && <section className="inner-page"><p className="eyebrow">CLIENTE / VISTA SIMULADA</p><h1 className="inner-title">Tus próximos<br /><em>recuerdos.</em></h1><p className="page-intro">Ejemplos visuales. No representan entradas emitidas.</p><article className="sample-ticket"><div><span className="soft-pill">EJEMPLO · NO VÁLIDO</span><h2>Noche de bandas</h2><p>15 MAY 2027 · Zona general · 1 entrada</p><span>Orden DEMO-001 · Sin QR ni código de ingreso</span></div><button className="btn btn-outline" onClick={() => demoAction('La solicitud de devolución')}>Devolución (Etapa III)</button></article></section>}

        {page === 'owner' && <section className="inner-page"><p className="eyebrow">ORGANIZADOR / VISTA SIMULADA</p><h1 className="inner-title">Tus eventos,<br /><em>tu escenario.</em></h1><p className="page-intro">El backend administrará borradores, permisos y publicación. Estos botones son solo una vista previa.</p><div className="section-head"><h2>Mis eventos</h2><button className="btn btn-dark" onClick={() => demoAction('Crear borrador')}>+ Crear evento</button></div><article className="sample-ticket"><div><span className="soft-pill">BORRADOR</span><h2>Nueva fecha acústica</h2><p>Faltan zonas de entradas para publicar.</p></div><button className="btn btn-outline" onClick={() => demoAction('Editar evento')}>Editar borrador ↗</button></article></section>}

        {page === 'admin' && <section className="inner-page"><p className="eyebrow">ADMINISTRACIÓN / VISTA SIMULADA</p><h1 className="inner-title">Todo en<br /><em>su lugar.</em></h1><p className="page-intro">La navegación no concede permisos. La API verificará los roles reales.</p><div className="form-panel admin-card"><span className="panel-number">GESTIÓN DE USUARIOS</span><h2>Roles y permisos</h2><label>Usuario de ejemplo<input readOnly value="usuario_demo" /></label><label>Rol a asignar<select defaultValue="customer"><option value="customer">Cliente</option><option value="event_owner">Organizador</option><option value="administrator">Administrador</option></select></label><button className="btn btn-dark" onClick={() => demoAction('El cambio de rol')}>Simular cambio de rol ↗</button></div></section>}
      </main>
      <footer><strong>ticketing<span className="brand-mark">.</span></strong><span>Trabajo práctico · Tópicos II 2026</span><span>{isDemo ? 'Vista de demostración / Datos ficticios' : 'Etapa I / Backend conectado / Sin pago real'}</span></footer>
    </div>
  );
}
