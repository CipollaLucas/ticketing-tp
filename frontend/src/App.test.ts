import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('Ticketing frontend demo', () => {
  it('presents the catalog and demo disclaimer without claiming a real purchase', () => {
    const markup = renderToStaticMarkup(createElement(App));
    expect(markup).toContain('Noche de bandas');
    expect(markup).toContain('Jornada de tecnología');
    expect(markup).toContain('DATOS FICTICIOS');
    expect(markup).toContain('SIN COMPRAS NI SESIONES REALES');
  });

  it('renders accessible navigation and a catalog state selector', () => {
    const markup = renderToStaticMarkup(createElement(App));
    expect(markup).toContain('aria-label="Navegación principal"');
    expect(markup).toContain('Ir al contenido');
    expect(markup).toContain('Sin eventos');
    expect(markup).toContain('Error de red');
  });
});
