import select
import multiprocessing as mp

from src.procfs import ProcFS
from src.collector import Collector
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

ANALYZERS = [
    AnalyzerSummary,
    AnalyzerCPU,
    AnalyzerThreads,
    AnalyzerMemory,
    AnalyzerSignals,
    AnalyzerFileDescriptor,
    AnalyzerScheduling,
    AnalyzerSystem,
]

VIEW_KEYS = {
    "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6,
    "r": 0, "m": 1, "f": 2, "t": 3, "s": 4, "p": 5, "g": 6,
    "h": 7, "?": 7,
}

def run_collector(procfs, shared_pids):
    Collector(procfs, shared_pids, sleep_interval=2).collect()

def run_analyzer(cls, procfs, shared_pids, snapshot, interval):
    """Crea y ejecuta un analizador de la clase `cls`."""
    analyzer = cls(procfs, shared_pids, snapshot, interval)
    analyzer.analyze()

def run_display(snapshot, active_view, sort_mode):
    """Crea y ejecuta el display."""
    from src.display.display import Display
    from src.display.rich_renderer import RichRenderer

    renderer = RichRenderer()
    display = Display(renderer, snapshot, active_view, sort_mode)
    display.run_display()

# --- orquestador -------------------------------------------------------------
def run_key_listener(active_view, sort_mode, fd):
    """Escucha una tecla (con timeout de 1s) y actualiza el estado de UI
    compartido. Devuelve False cuando el usuario pide salir con 'q'.
    """
    key_ready, _, _ = select.select([fd], [], [], 1)
    if key_ready:
        # errors="ignore": un byte suelto de una secuencia multibyte (ñ, flechas)
        # no debe tirar abajo a main; queda como no-op.
        key = os.read(fd, 1).decode(errors="ignore")
        if key == "q":
            return False
        elif key == "c":
            # 0 natural(PID) → 1 CPU% → 2 RSS; el significado vive en
            # display._SORT_MODES. Único escritor: sin lock.
            sort_mode.value = (sort_mode.value + 1) % 3
        elif key in VIEW_KEYS:
            active_view.value = VIEW_KEYS[key]
    return True

def main():
    mp.set_start_method("fork")

    procfs = ProcFS("/proc")

    manager = mp.Manager()
    snapshot = manager.dict()
    shared_pids = manager.list()
    
    active_view = mp.Value("i", 0)
    sort_mode = mp.Value("i", 0)

    procs = [
        mp.Process(target=run_display, args=(snapshot, active_view, sort_mode), name="display"),
        mp.Process(target=run_collector, args=(procfs, shared_pids), name="collector"),
        *[
            mp.Process(
                target=run_analyzer,
                args=(cls, procfs, shared_pids, snapshot, 2),
                name=cls.__name__,
            )
            for cls in ANALYZERS
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
            running = run_key_listener(active_view, sort_mode, fd)
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
