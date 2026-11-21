"""Apoyo de las pruebas de principio a fin: servidor, base y navegador de verdad.

Decisión de Sophia del 19 de noviembre de 2026: las pruebas de la pantalla no
se hacen en un PostgreSQL temporal ni fuera del repositorio. Se hacen aquí,
contra su base `integro`, arrancando el servidor, la base y el navegador.

Qué arranca cada fixture:

- site (una vez por archivo de pruebas): la API de verdad, en un hilo de este
  mismo proceso y en un puerto libre, con las páginas de web/ y la base
  `integro` del usuario de backend/.env. Todo lo que el navegador escriba en
  la base va dentro de una sola transacción que se deshace al terminar: no
  queda ninguna fila. Los códigos no se envían: se leen de un anotador.
- browser (una vez por archivo): Edge o Chrome sin ventana, que se maneja por
  el protocolo de depuración (CDP). Hace falta websocket-client.
- page (una por prueba): un contexto limpio del navegador, sin cookies de
  otra prueba y con su propio nombre de navegador, para que la espera por
  dispositivo (ADR 0014) de una prueba no cuente en la siguiente.

El navegador teclea y da clic de verdad (eventos de entrada del navegador);
no cambia valores ni dispara eventos por JavaScript.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.core.config import ENV_FILE, load_settings  # noqa: E402
from app.database.connection import create_pool  # noqa: E402
from app.database.transaction import system_transaction  # noqa: E402
from app.main import create_app  # noqa: E402

BROWSER_CANDIDATES = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)

# Cuenta las peticiones que hace la página, para saber cuándo empezó una.
COUNT_REQUESTS = """
(() => {
  const original = window.fetch;
  window.__net = { started: 0 };
  window.fetch = function () { window.__net.started++; return original.apply(this, arguments); };
})();
"""


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def find_browser() -> str | None:
    """El navegador: el de INTEGRO_BROWSER, Edge, Chrome o el que haya en el PATH."""
    chosen = os.environ.get("INTEGRO_BROWSER")
    if chosen and Path(chosen).is_file():
        return chosen
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    for name in ("msedge", "chrome", "google-chrome", "chromium"):
        found = shutil.which(name)
        if found:
            return found
    return None


# ---------------------------------------------------------------------------
# La base y el servidor
# ---------------------------------------------------------------------------


class SingleConnectionPool:
    """Se hace pasar por el grupo de conexiones y entrega siempre la misma, que ya
    tiene una transacción abierta que se deshace al final (igual que en tests/backend)."""

    def __init__(self, connection):
        self._connection = connection

    @contextmanager
    def connection(self, timeout=None):
        yield self._connection


class CodeBox:
    """En lugar de enviar los códigos los anota, para que la prueba los lea."""

    def __init__(self):
        self.sent = []
        self.notices = []

    def send_code(self, **message):
        self.sent.append(message)

    def send_notice(self, **notice):
        self.notices.append(notice)

    def code_for(self, email: str, purpose: str) -> str:
        found = [m["code"] for m in self.sent if m["destination"] == email and m["purpose"] == purpose]
        assert found, f"no se envió ningún código «{purpose}» a {email}"
        return found[-1]


@dataclass
class Site:
    url: str
    pool: SingleConnectionPool
    codes: CodeBox
    settings: object

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
        """Una petición a la API como un programa cualquiera, sin navegador."""
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.url + path, data=data, method=method,
            headers={"Content-Type": "application/json", "Origin": self.url},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"null")


@pytest.fixture(scope="module")
def site():
    """La API de verdad sobre la base real, con todo lo que se escriba deshecho al terminar."""
    if not ENV_FILE.exists():
        pytest.skip("Falta backend/.env: sin él no hay con qué conectarse a la base real.")
    import uvicorn

    # El servidor local no tiene HTTPS: la cookie de sesión viaja sin Secure.
    settings = load_settings().model_copy(update={"session_cookie_secure": False})
    real_pool = create_pool(settings)
    real_pool.open(wait=True, timeout=10)
    server = None
    try:
        with real_pool.connection() as connection:
            with connection.transaction(force_rollback=True):
                application = create_app(settings)
                port = free_port()
                server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=port, log_level="warning"))
                thread = threading.Thread(target=server.run, daemon=True)
                thread.start()
                deadline = time.time() + 20
                while not server.started:
                    assert thread.is_alive() and time.time() < deadline, "el servidor no arrancó"
                    time.sleep(0.05)
                codes = CodeBox()
                pool = SingleConnectionPool(connection)
                application.state.pool = pool
                application.state.code_sender = codes
                try:
                    yield Site(url=f"http://127.0.0.1:{port}", pool=pool, codes=codes, settings=settings)
                finally:
                    server.should_exit = True
                    thread.join(15)
    finally:
        real_pool.close()


# ---------------------------------------------------------------------------
# El navegador
# ---------------------------------------------------------------------------


class Page:
    """Una pestaña. Teclea, da clic y lee la pantalla por el protocolo de depuración."""

    def __init__(self, browser: "Browser", websocket_url: str, target_id: str, context_id: str):
        import websocket

        self.browser = browser
        self.target_id = target_id
        self.context_id = context_id
        self._ws = websocket.create_connection(websocket_url, timeout=30, suppress_origin=True)
        self._counter = 0
        self._events: list[dict] = []
        self.send("Page.enable")
        self.send("Page.addScriptToEvaluateOnNewDocument", source=COUNT_REQUESTS)

    # --- protocolo ---------------------------------------------------------

    def _receive(self) -> dict:
        message = json.loads(self._ws.recv())
        if "method" in message:
            self._events.append(message)
        return message

    def send(self, method: str, **params) -> dict:
        self._counter += 1
        self._ws.send(json.dumps({"id": self._counter, "method": method, "params": params}))
        while True:
            message = self._receive()
            if message.get("id") == self._counter:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def js(self, expression: str):
        result = self.send("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in result:
            raise RuntimeError(f"{result['exceptionDetails'].get('text')}: {expression[:100]}")
        return result.get("result", {}).get("value")

    # --- navegación --------------------------------------------------------

    def goto(self, url: str) -> None:
        self._events.clear()
        self.send("Page.navigate", url=url)
        deadline = time.time() + 20
        # Una carga completa avisa con loadEventFired; un cambio solo del ancla (#) no recarga y avisa con
        # navigatedWithinDocument.
        done = ("Page.loadEventFired", "Page.navigatedWithinDocument")
        while not any(event["method"] in done for event in self._events):
            assert time.time() < deadline, f"la página no terminó de cargar: {url}"
            self._receive()

    def set_user_agent(self, user_agent: str) -> None:
        self.send("Emulation.setUserAgentOverride", userAgent=user_agent)

    def set_viewport(self, width: int, height: int, mobile: bool = False) -> None:
        self.send("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=mobile)

    def screenshot(self, path: Path) -> None:
        import base64

        path.write_bytes(base64.b64decode(self.send("Page.captureScreenshot", format="png")["data"]))

    # --- lo que hace una persona -------------------------------------------

    def _center(self, selector: str) -> dict:
        point = self.js(
            "(() => { const e = document.querySelector(" + json.dumps(selector) + "); if (!e) return null; "
            # behavior instant: la hoja de estilos tiene scroll suave y las coordenadas se tomarían a mitad de camino.
            "e.scrollIntoView({ block: 'center', behavior: 'instant' }); const r = e.getBoundingClientRect(); "
            "return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()"
        )
        assert point, f"no hay nada que coincida con {selector}\n{self.state()}"
        return point

    def click(self, selector: str) -> None:
        self.click_at(**self._center(selector))

    def click_at(self, x: float, y: float) -> None:
        self.send("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
        self.send("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
        self.send("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)

    def type(self, selector: str, text: str) -> None:
        """Pone el cursor en el campo, selecciona lo que tenga y teclea el texto."""
        focused = self.js(
            "(() => { const e = document.querySelector(" + json.dumps(selector) + "); if (!e) return false; "
            "e.focus(); if (e.select) e.select(); return document.activeElement === e; })()"
        )
        assert focused, f"no se pudo enfocar {selector}\n{self.state()}"
        self.send("Input.insertText", text=text)

    def clear(self, selector: str) -> None:
        """Borra lo que tenga el campo: lo selecciona y da Retroceso, como una persona."""
        selected = self.js(
            "(() => { const e = document.querySelector(" + json.dumps(selector) + "); if (!e) return false; "
            "e.focus(); e.select(); return document.activeElement === e; })()"
        )
        assert selected, f"no se pudo enfocar {selector}\n{self.state()}"
        self.press("Backspace")

    def set_value(self, selector: str, value: str) -> None:
        """Pone el valor de una lista o de una fecha y avisa a la página, como al elegirlo.

        La lista y el calendario del navegador son ventanas propias que no se manejan en modo sin ventana;
        todo lo que se escribe se teclea de verdad con type().
        """
        found = self.js(
            "(() => { const e = document.querySelector(" + json.dumps(selector) + "); if (!e) return false; "
            "e.focus(); e.value = " + json.dumps(value) + "; "
            "e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); "
            "return e.value === " + json.dumps(value) + "; })()"
        )
        assert found, f"no se pudo poner {value!r} en {selector}\n{self.state()}"

    def count(self, selector: str) -> int:
        return self.js("document.querySelectorAll(" + json.dumps(selector) + ").length")

    def press(self, key: str) -> None:
        keys = {
            "Enter": {"key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"},
            "Escape": {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
            "Backspace": {"key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
        }[key]
        self.send("Input.dispatchKeyEvent", type="keyDown", **keys)
        self.send("Input.dispatchKeyEvent", type="keyUp", **{k: v for k, v in keys.items() if k != "text"})

    # --- lo que se ve --------------------------------------------------------

    def requests(self) -> int:
        return self.js("window.__net ? window.__net.started : 0")

    def wait_for(self, condition: str, seconds: float = 8.0) -> bool:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self.js(f"!!({condition})"):
                return True
            time.sleep(0.05)
        return False

    def expect(self, condition: str, seconds: float = 8.0) -> None:
        assert self.wait_for(condition, seconds), f"no llegó a cumplirse: {condition}\n{self.state()}"

    def state(self) -> str:
        """Lo que hay en pantalla, para explicar una falla."""
        return json.dumps(self.js(STATE_JS), ensure_ascii=False)

    def header(self) -> list[str]:
        """Lo que se ve en la zona de la cuenta: enlaces y botones con lugar en la pantalla, en orden.

        Con el menú cerrado, una persona con sesión ve solo su nombre; con el menú abierto, también sus opciones.
        """
        return self.js(
            "Array.from(document.querySelector('[data-cuenta]').querySelectorAll('a, button'))"
            ".filter(e => e.getClientRects().length > 0).map(e => e.textContent.trim())"
        )

    def menu_is_open(self) -> bool:
        return self.js("(() => { const l = document.querySelector('.cuenta-lista'); return !!l && !l.hidden; })()")

    def open_menu(self) -> None:
        """Abre el menú de la cuenta dando clic en el nombre, como una persona."""
        if not self.menu_is_open():
            self.click(".cuenta-nombre")
        self.expect("!document.querySelector('.cuenta-lista').hidden")

    def log_out(self) -> None:
        self.open_menu()
        self.click(".cuenta-salir")

    def nav(self) -> list[str]:
        """Los enlaces de la barra junto a la marca, en el orden en que se ven."""
        return self.js("Array.from(document.querySelectorAll('header.cabecera .enlaces-cabecera a')).map(a => a.textContent.trim())")

    def current_tab(self) -> list[str]:
        return self.js(
            "Array.from(document.querySelectorAll('header.cabecera [data-pestana][aria-current=page]')).map(a => a.textContent.trim())"
        )

    def window_open(self) -> bool:
        """La ventana se ve de verdad: no basta con que no tenga el atributo hidden, tiene que ocupar lugar en la pantalla."""
        return self.js(
            "(() => { const v = document.getElementById('ventana-entrar'); "
            "return !!v && !v.hidden && getComputedStyle(v).display !== 'none' && v.getBoundingClientRect().width > 0; })()"
        )

    def covers_the_page(self) -> bool:
        """Dice si algo de la ventana tapa el centro de la página, es decir, si quitaría los clics."""
        return self.js(
            "(() => { const e = document.elementFromPoint(innerWidth / 2, innerHeight / 2); "
            "return !!e && !!e.closest('#ventana-entrar'); })()"
        )

    def is_clickable(self, selector: str) -> bool:
        """Dice si un clic en el centro de ese elemento le llegaría a él y no a otra cosa."""
        return self.js(
            "(() => { const e = document.querySelector(" + json.dumps(selector) + "); if (!e) return false; "
            "const r = e.getBoundingClientRect(); const t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); "
            "return !!t && (t === e || e.contains(t)); })()"
        )

    def step(self) -> str | None:
        return self.js(
            "(() => { const f = (n) => document.querySelector('#ventana-entrar form[data-paso=' + n + ']'); "
            "return f('correo') && !f('correo').hidden ? 'correo' : f('codigo') && !f('codigo').hidden ? 'codigo' : null; })()"
        )

    def warning(self) -> str | None:
        return self.js(
            "(() => { const a = document.querySelector('#ventana-entrar [data-aviso]'); return a && !a.hidden ? a.textContent : null; })()"
        )

    def text(self, selector: str) -> str | None:
        return self.js("(() => { const e = document.querySelector(" + json.dumps(selector) + "); return e ? e.textContent : null; })()")

    def value(self, selector: str) -> str | None:
        return self.js("(() => { const e = document.querySelector(" + json.dumps(selector) + "); return e ? e.value : null; })()")

    def location(self) -> str:
        return self.js("location.pathname + location.search")

    def close(self) -> None:
        try:
            self._ws.close()
        finally:
            self.browser.close_page(self)


STATE_JS = (
    "({ url: location.href, cabecera: document.querySelector('[data-cuenta]') ? "
    "Array.from(document.querySelector('[data-cuenta]').children).map(e => e.textContent.trim()) : null, "
    "ventana_abierta: !!document.getElementById('ventana-entrar') && !document.getElementById('ventana-entrar').hidden, "
    "ventana_se_ve: !!document.getElementById('ventana-entrar') && document.getElementById('ventana-entrar').getBoundingClientRect().width > 0, "
    "aviso: document.querySelector('#ventana-entrar [data-aviso]') ? document.querySelector('#ventana-entrar [data-aviso]').textContent : null, "
    "texto: document.querySelector('#ventana-entrar [data-texto]') ? document.querySelector('#ventana-entrar [data-texto]').textContent : null, "
    "peticiones: window.__net ? window.__net.started : null })"
)


class Browser:
    """Edge o Chrome sin ventana, con un perfil nuevo que se borra al terminar."""

    def __init__(self, executable: str):
        self._profile = tempfile.mkdtemp(prefix="integro-e2e-")
        port = free_port()
        self._process = subprocess.Popen(
            [executable, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
             "--no-default-browser-check", f"--remote-debugging-port={port}", f"--user-data-dir={self._profile}",
             "--window-size=1280,900", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self._port = port
        deadline = time.time() + 30
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as response:
                    version = json.loads(response.read())
                break
            except Exception:
                assert time.time() < deadline and self._process.poll() is None, "el navegador no respondió"
                time.sleep(0.3)
        import websocket

        self._ws = websocket.create_connection(version["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
        self._counter = 0
        self.version = version["Browser"]

    def _call(self, method: str, **params) -> dict:
        self._counter += 1
        self._ws.send(json.dumps({"id": self._counter, "method": method, "params": params}))
        while True:
            message = json.loads(self._ws.recv())
            if message.get("id") == self._counter:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})

    def new_page(self) -> Page:
        """Una pestaña en un contexto nuevo: sin cookies ni nada de otra prueba."""
        context_id = self._call("Target.createBrowserContext")["browserContextId"]
        target_id = self._call("Target.createTarget", url="about:blank", browserContextId=context_id)["targetId"]
        for _ in range(100):
            with urllib.request.urlopen(f"http://127.0.0.1:{self._port}/json/list", timeout=5) as response:
                targets = {t["id"]: t for t in json.loads(response.read())}
            if target_id in targets:
                return Page(self, targets[target_id]["webSocketDebuggerUrl"], target_id, context_id)
            time.sleep(0.05)
        raise AssertionError("la pestaña nueva no apareció")

    def close_page(self, page: Page) -> None:
        try:
            self._call("Target.closeTarget", targetId=page.target_id)
            self._call("Target.disposeBrowserContext", browserContextId=page.context_id)
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._ws.close()
        finally:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
            shutil.rmtree(self._profile, ignore_errors=True)


@pytest.fixture(scope="module")
def browser():
    pytest.importorskip("websocket", reason="Falta websocket-client: pip install -r backend/requirements-dev.txt")
    executable = find_browser()
    if executable is None:
        pytest.skip("No hay Edge ni Chrome instalado. Se puede indicar otro con la variable INTEGRO_BROWSER.")
    instance = Browser(executable)
    yield instance
    instance.close()


@pytest.fixture
def page(browser):
    """Una pestaña limpia, con un nombre de navegador propio de esta prueba."""
    tab = browser.new_page()
    tab.set_user_agent(f"IntegroE2E/{uuid.uuid4().hex[:12]}")
    tab.set_viewport(1280, 800)
    yield tab
    tab.close()


# ---------------------------------------------------------------------------
# La base, vista desde la prueba
# ---------------------------------------------------------------------------


def make_account(site: Site, *, first_name: str = "Ana", verified: bool = True, password: str = "Ejemplo-2026") -> dict:
    """Crea una cuenta por la API y, si se pide, comprueba su correo."""
    tag = uuid.uuid4().hex[:12]
    account = {
        "first_name": first_name,
        "last_name": "Torres",
        "email": f"{first_name.lower()}.{tag}@prueba.invalid",
        "password": password,
        "phone": "+52" + str(int(tag, 16))[:10].rjust(10, "5"),
        "country": "MX",
        "birth_date": "1995-03-14",
    }
    status, body = site.request("POST", "/api/v1/auth/register", account)
    assert status == 201, body
    if verified:
        code = site.codes.code_for(account["email"], "verify_email")
        status, body = site.request("POST", "/api/v1/auth/verify-email", {"email": account["email"], "code": code})
        assert status == 200, body
    return account


def make_host(site: Site, email: str) -> None:
    """Le da a esa persona su perfil de anfitrión, como lo hará Verificación más adelante."""
    with system_transaction(site.pool) as connection:
        connection.execute("insert into host_profiles (user_id) select id from users where email = %s", (email,))


def make_admin(site: Site, email: str) -> None:
    """Pone a esa persona como administradora en una tabla temporal que tapa a la verdadera, solo en esta prueba.

    Las pruebas no tienen permiso de escribir en admins (solo se llena a mano en pgAdmin), y la tabla verdadera no se
    toca: la temporal vive en la transacción única de las pruebas y se deshace al terminar.
    """
    with site.pool.connection() as connection:
        connection.execute("create temp table if not exists admins (user_id uuid primary key)")
        connection.execute("grant select, insert, delete on admins to integro_service, integro_app")
    with system_transaction(site.pool) as connection:
        connection.execute("insert into admins (user_id) select id from users where email = %s", (email,))


def sessions_of(site: Site, email: str) -> tuple[int, int]:
    """(abiertas, total) de las sesiones de esa persona."""
    with system_transaction(site.pool) as connection:
        return connection.execute(
            "select count(*) filter (where revoked_at is null), count(*) from sessions "
            "where user_id = (select id from users where email = %s)",
            (email,),
        ).fetchone()


def age_codes(site: Site, email: str, seconds: int) -> None:
    """Hace que los códigos de esa persona parezcan creados hace tantos segundos."""
    with system_transaction(site.pool) as connection:
        connection.execute(
            "update one_time_codes set created_at = created_at - make_interval(secs => %s), "
            "expires_at = expires_at - make_interval(secs => %s) "
            "where user_id = (select id from users where email = %s)",
            (seconds, seconds, email),
        )
