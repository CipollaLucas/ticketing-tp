"""Real Chromium H5 Stage I browser UAT, never pointed at Legacy.

Only executable against loopback Vite with H5 isolated Gateway proxy.
Run after the disposable H5 HTTP smoke has passed.
"""
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = "http://127.0.0.1:5173"
EVIDENCE = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "h5-browser"


def login(page, username: str, password: str) -> None:
    page.get_by_label("Usuario", exact=True).fill(username)
    page.get_by_label("Contraseña", exact=True).fill(password)
    page.get_by_role("button", name="Iniciar sesión").click()
    expect(page.get_by_role("button", name="Cerrar sesión")).to_be_visible(timeout=15000)


def sign_out(page) -> None:
    page.get_by_role("button", name="Cerrar sesión").click()
    expect(page.get_by_label("Usuario", exact=True)).to_be_visible(timeout=15000)


def main() -> None:
    if os.environ.get("H5_DISPOSABLE_BROWSER_UAT") != "yes":
        raise SystemExit("REFUSED: browser UAT must be explicitly disposable")
    password = os.environ["H3_TEST_PASSWORD"]
    if len(password) < 16:
        raise SystemExit("REFUSED: disposable password too short")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    name = "H5 React Browser " + datetime.now(UTC).strftime("%Y%m%d%H%M%S")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        failures: list[str] = []
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.goto(BASE + "/#workspace", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="La ticketera")).to_be_visible()

        # Owner: create a draft, configure a zone and publish.
        login(page, "h3owner", password)
        expect(page.locator(".core-identity")).to_contain_text("event_owner")
        expect(page.get_by_role("heading", name="Crear borrador")).to_be_visible()
        page.get_by_label("Nombre", exact=True).fill(name)
        page.get_by_label("Descripción", exact=True).fill("H5 real Chromium acceptance")
        page.get_by_label("Lugar", exact=True).fill("Disposable Browser Fixture")
        future = datetime.now(UTC) + timedelta(days=14)
        page.get_by_label("Inicio", exact=True).fill(future.strftime("%Y-%m-%dT%H:%M"))
        page.get_by_label("Fin", exact=True).fill(
            (future + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")
        )
        page.get_by_role("button", name="Crear evento").click()
        expect(page.get_by_text("Borrador creado. Ahora podés configurar su inventario.")).to_be_visible(timeout=15000)
        page.get_by_label("Zona", exact=True).fill("H5 General")
        page.get_by_label("Cupo", exact=True).fill("2")
        page.get_by_label("Precio en ARS", exact=True).fill("15")
        page.get_by_role("button", name="Agregar zona").click()
        expect(page.get_by_text("Zona creada. Ya podés publicar el evento.")).to_be_visible(timeout=15000)
        page.get_by_role("button", name="Publicar evento").click()
        expect(page.get_by_text("Evento publicado y disponible en el catálogo.")).to_be_visible(timeout=20000)
        page.screenshot(path=str(EVIDENCE / "owner-published.png"), full_page=True)
        sign_out(page)

        # Customer: browse published event, buy exactly one and read ticket.
        login(page, "h3customer", password)
        expect(page.locator(".core-identity")).to_contain_text("customer")
        page.get_by_role("button", name="Eventos y compra").click()
        page.get_by_role("button", name="Actualizar catálogo").click()
        event_select = page.get_by_label("Evento", exact=True)
        expect(event_select.locator("option", has_text=name)).to_have_count(1, timeout=15000)
        event_select.select_option(label=event_select.locator("option", has_text=name).inner_text())
        expect(page.get_by_label("Zona", exact=True)).to_be_visible(timeout=15000)
        page.get_by_label("Zona", exact=True).select_option(
            label=page.get_by_label("Zona", exact=True).locator("option", has_text="H5 General").inner_text()
        )
        page.get_by_role("button", name="Confirmar compra simulada").click()
        expect(page.get_by_text("Compra simulada confirmada y registrada en PostgreSQL.")).to_be_visible(timeout=20000)
        expect(page.get_by_text("ORDEN CONFIRMADA")).to_be_visible()
        page.get_by_role("button", name="Mis tickets").click()
        expect(page.get_by_role("heading", name="Mis tickets emitidos")).to_be_visible()
        expect(page.locator(".core-ticket").first).to_be_visible(timeout=15000)
        page.screenshot(path=str(EVIDENCE / "customer-ticket.png"), full_page=True)
        sign_out(page)

        # Administrator: authenticate in real UI and verify role-management view.
        login(page, "h5admin", password)
        expect(page.locator(".core-identity")).to_contain_text("administrator")
        expect(page.get_by_role("heading", name="Asignación de rol")).to_be_visible()
        page.screenshot(path=str(EVIDENCE / "administrator.png"), full_page=True)
        sign_out(page)

        assert not failures, "Browser JavaScript errors: " + "; ".join(failures)
        context.close()
        browser.close()
    print("PASS: Chromium React UI owner, customer and administrator via isolated H5 Gateway")
    print("PASS: draft, zone, publication, simulated purchase and ticket listing without Legacy")


if __name__ == "__main__":
    main()
