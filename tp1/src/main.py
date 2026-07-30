import select
import multiprocessing as mp

from src.procfs import ProcFS
from src.collector import Collector
from src.ui_state import UIState
from src.analizadores.summary import AnalyzerSummary
from src.analizadores.cpu import AnalyzerCPU
from src.analizadores.threads import AnalyzerThreads
from src.analizadores.memory import AnalyzerMemory
from src.analizadores.senales import AnalyzerSignals
from src.analizadores.fds import AnalyzerFileDescriptor
from src.analizadores.scheduling import AnalyzerScheduling
from src.analizadores.sistema import AnalyzerSystem
import sys
import termios
import tty
import os

# (clase, intervalo default, intervalo mínimo) según la tabla de la consigna.
# CPU no tiene vista propia: acompaña a Resumen, mismo default/mínimo que Summary.
ANALYZER_SPECS = [
    (AnalyzerSummary, 2.0, 0.5),
    (AnalyzerCPU, 2.0, 0.5),
    (AnalyzerThreads, 2.0, 0.5),
    (AnalyzerMemory, 3.0, 1.0),
    (AnalyzerSignals, 10.0, 5.0),
    (AnalyzerFileDescriptor, 5.0, 2.0),
    (AnalyzerScheduling, 10.0, 5.0),
    (AnalyzerSystem, 2.0, 1.0),
]

VIEW_KEYS = {
    "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6,
    "r": 0, "m": 1, "f": 2, "t": 3, "s": 4, "p": 5, "g": 6,
    "h": 7, "?": 7,
}

# Vista activa -> índices en ANALYZER_SPECS cuyos intervalos ajustan '+'/'-'.
# Resumen late al ritmo de summary Y cpu (decisión: los dos son su pulso);
# la Ayuda no ajusta a nadie.
VIEW_ANALYZERS = {
    0: (0, 1),   # Resumen -> Summary + CPU
    1: (3,),     # Memoria
    2: (5,),     # File Descriptors
    3: (2,),     # Threads
    4: (4,),     # Señales
    5: (6,),     # Scheduling
    6: (7,),     # Sistema
    7: (),       # Ayuda
}

INTERVAL_STEP = 0.5
INTERVAL_MAX = 60.0

def run_collector(procfs, shared_pids):
    Collector(procfs, shared_pids, sleep_interval=2).collect()

def run_analyzer(cls, procfs, shared_pids, snapshot, interval):
    """Crea y ejecuta un analizador de la clase `cls`."""
    analyzer = cls(procfs, shared_pids, snapshot, interval)
    analyzer.analyze()

def run_display(snapshot, ui):
    """Crea y ejecuta el display."""
    from src.display.display import Display
    from src.display.rich_renderer import RichRenderer

    renderer = RichRenderer()
    display = Display(renderer, snapshot, ui)
    display.run_display()

# --- orquestador -------------------------------------------------------------
# Secuencias de escape que entendemos (flechas: ESC [ A/B).
_ESCAPE_SEQUENCES = {b"[A": "up", b"[B": "down"}


def _read_key(fd, timeout=1.0):
    """Lee una "tecla" del fd y la devuelve como string: un carácter normal,
    o un nombre simbólico ("up"/"down"/"enter"). None si no llegó nada en
    `timeout` o si llegó algo que no entendemos (no-op).

    Una flecha son 3 bytes (ESC [ A): tras ver el ESC se espera brevemente el
    resto de la secuencia; un ESC solo, o una secuencia desconocida, es None.
    """
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        return None
    byte = os.read(fd, 1)
    if byte in (b"\r", b"\n"):
        return "enter"
    if byte != b"\x1b":
        # errors="ignore": un byte suelto de un carácter multibyte (ñ) no
        # debe tirar abajo a main; queda como no-op.
        return byte.decode(errors="ignore") or None
    sequence = b""
    while len(sequence) < 2:
        ready, _, _ = select.select([fd], [], [], 0.05)
        if not ready:
            return None  # ESC solo
        sequence += os.read(fd, 1)
    return _ESCAPE_SEQUENCES.get(sequence)


def _is_printable(char: str) -> bool:
    """True si `char` es un único carácter imprimible ASCII."""
    return len(char) == 1 and " " <= char <= "~"


def run_key_listener(ui, fd):
    """Escucha una tecla (con timeout de 1s) y actualiza el estado de UI
    compartido. Devuelve False cuando el usuario pide salir con 'q'.
    """
    key = _read_key(fd)
    if key is None:
        return True

    # ── modo input (filtro por comando o usuario) ──────────────────────────
    if ui.filter_mode.value != 0:
        if key == "enter":
            ui.filter_mode.value = 0          # confirmar: mantener texto, volver a normal
        elif key == "\x1b":                   # ESC — cancelar y limpiar
            ui.filter_value.get_obj().value = ""
            ui.filter_mode.value = 0
        elif key == "\x7f":                   # Backspace
            cur = ui.filter_value.get_obj().value
            ui.filter_value.get_obj().value = cur[:-1]
        elif _is_printable(key):
            cur = ui.filter_value.get_obj().value
            ui.filter_value.get_obj().value = cur + key
        return True

    # ── modo normal ────────────────────────────────────────────────────────
    if key == "q":
        return False
    elif key == "c":
        # 0 natural(PID) → 1 CPU% → 2 RSS; el significado vive en
        # display._SORT_MODES. Único escritor: sin lock.
        ui.sort_mode.value = (ui.sort_mode.value + 1) % 3
    elif key in ("+", "-"):
        delta = INTERVAL_STEP if key == "+" else -INTERVAL_STEP
        for i in VIEW_ANALYZERS.get(ui.active_view.value, ()):
            minimum = ANALYZER_SPECS[i][2]
            interval = ui.intervals[i]
            interval.value = min(max(interval.value + delta, minimum), INTERVAL_MAX)
    elif key in ("up", "down"):
        # Mover el cursor despinnea: la selección vuelve a ser posicional.
        ui.pinned_pid.value = -1
        step = -1 if key == "up" else 1
        # El techo sale de row_count, que publica el display (main no conoce
        # la tabla); puede venir 1 frame viejo — tolerable, igual que siempre.
        top = max(0, ui.row_count.value - 1)
        ui.selected_row.value = min(max(0, ui.selected_row.value + step), top)
    elif key == "enter":
        if ui.pinned_pid.value != -1:
            ui.pinned_pid.value = -1          # Enter con pin activo = despinnear
        elif ui.pid_at_selected.value != -1:
            # La selección se vuelve identidad: el PID que el display publicó
            # como "bajo el cursor" (tu opción C: estado puro, 1 frame de atraso).
            ui.pinned_pid.value = ui.pid_at_selected.value
    elif key == "/":
        ui.filter_mode.value = 1
        ui.filter_value.get_obj().value = ""
    elif key == "u":
        ui.filter_mode.value = 2
        ui.filter_value.get_obj().value = ""
    elif key in VIEW_KEYS:
        ui.active_view.value = VIEW_KEYS[key]
    return True

def main():
    mp.set_start_method("fork")

    procfs = ProcFS("/proc")

    manager = mp.Manager()
    snapshot = manager.dict()
    shared_pids = manager.list()
    
    # Todo el estado de UI compartido, creado ANTES del fork. Un escritor por
    # campo (ver ui_state.py); los intervalos son un Value('d') por analizador
    # que cada uno relee en su sleep de a ticks (pacing.py).
    ui = UIState(
        active_view=mp.Value("i", 0),
        sort_mode=mp.Value("i", 0),
        intervals=[mp.Value("d", default) for _, default, _ in ANALYZER_SPECS],
        selected_row=mp.Value("i", 0),
        pinned_pid=mp.Value("i", -1),
        pid_at_selected=mp.Value("i", -1),
        row_count=mp.Value("i", 0),
        filter_mode=mp.Value("i", 0),
        filter_value=mp.Array("u", 128)
    )

    procs = [
        mp.Process(target=run_display, args=(snapshot, ui), name="display"),
        mp.Process(target=run_collector, args=(procfs, shared_pids), name="collector"),
        *[
            mp.Process(
                target=run_analyzer,
                args=(cls, procfs, shared_pids, snapshot, interval),
                name=cls.__name__,
            )
            for (cls, _, _), interval in zip(ANALYZER_SPECS, ui.intervals)
        ],
    ]
    for p in procs:
        p.start()


    try: #TO do quitar cuando se implemente el shutdown de los analizadores y del collector
        fd = sys.stdin.fileno() 

        estado_original = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        running = True
        while running:
            running = run_key_listener(ui, fd)
    except KeyboardInterrupt:
        print("\nbajando...")
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.join()
        termios.tcsetattr(fd, termios.TCSADRAIN, estado_original)



if __name__ == "__main__":
    main()
