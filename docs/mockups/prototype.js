const sections = [...document.querySelectorAll('main > section')];
const roleSelect = document.querySelector('#role');
const notice = document.querySelector('#notice');
const rolePages = { tickets: 'customer', owner: 'event_owner', admin: 'administrator' };

function showPage() {
  const requested = window.location.hash.slice(1);
  if (requested === 'content') {
    document.querySelector('#content').focus({ preventScroll: true });
    return;
  }
  const page = sections.some(section => section.id === requested) ? requested : 'catalog';
  for (const section of sections) section.hidden = section.id !== page;
  for (const link of document.querySelectorAll('nav a')) {
    if (link.hash === `#${page}`) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
  notice.hidden = true;
  if (rolePages[page] && rolePages[page] !== roleSelect.value) {
    notice.textContent = 'Vista de ejemplo: seleccioná el rol correspondiente para revisar su navegación. Esto no concede permisos reales.';
    notice.hidden = false;
  }
  document.title = `${document.querySelector(`#${page} h1`).innerText.replace(/\s+/g, ' ')} · Demo Ticketing`;
  document.querySelector('#content').focus({ preventScroll: true });
}

roleSelect.addEventListener('change', () => {
  for (const link of document.querySelectorAll('[data-role]')) {
    link.hidden = link.dataset.role !== roleSelect.value;
  }
  window.location.hash = { customer: 'tickets', event_owner: 'owner', administrator: 'admin', visitor: 'catalog' }[roleSelect.value];
  showPage();
});

for (const button of document.querySelectorAll('[data-demo]')) {
  button.addEventListener('click', () => {
    notice.textContent = 'Acción de demostración. No se enviaron datos, no se cambió ningún rol y no se realizó ninguna operación real.';
    notice.hidden = false;
    notice.scrollIntoView({ block: 'nearest' });
  });
}

document.querySelector('#catalog-state').addEventListener('change', event => {
  const state = event.target.value;
  document.querySelector('#event-grid').hidden = state !== 'ready';
  const message = document.querySelector('#catalog-message');
  message.hidden = state === 'ready';
  message.textContent = { loading: 'Buscando próximos eventos…', empty: 'Todavía no hay eventos publicados. No hay entradas a la venta.', error: 'No pudimos cargar los eventos. Volvé a intentar más tarde.' }[state] ?? '';
});

document.querySelector('#zone').addEventListener('change', event => {
  document.querySelector('#seat-hint').textContent = event.target.selectedIndex === 1
    ? 'Platea numerada: en el flujo real elegirás asientos específicos (por ejemplo A1). No se reservan en esta maqueta.'
    : 'General: cantidad sin selección de asientos.';
});

document.querySelector('#checkout-form').addEventListener('submit', event => {
  event.preventDefault();
  notice.textContent = 'Compra no disponible: esta demostración no cobró, reservó cupo ni emitió tickets.';
  notice.hidden = false;
  notice.scrollIntoView({ block: 'nearest' });
});

for (const link of document.querySelectorAll('[data-role]')) link.hidden = true;
window.addEventListener('hashchange', showPage);
showPage();
