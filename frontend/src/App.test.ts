import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import App from './App';

describe('Ticketing frontend with live catalog', () => {
  it('defaults to real events without displaying fictitious prices or tickets', () => {
    const markup = renderToStaticMarkup(createElement(App));
    expect(markup).toContain('CATÁLOGO REAL');
    expect(markup).toContain('Eventos reales');
    expect(markup).toContain('Buscando experiencias');
    expect(markup).not.toContain('ARS 12.000');
    expect(markup).not.toContain('Noche de bandas');
  });

  it('has accessible navigation and an explicit demo mode option', () => {
    const markup = renderToStaticMarkup(createElement(App));
    expect(markup).toContain('aria-label="Navegación principal"');
    expect(markup).toContain('Ir al contenido');
    expect(markup).toContain('Fuente de eventos');
    expect(markup).toContain('Demostración');
  });
});
