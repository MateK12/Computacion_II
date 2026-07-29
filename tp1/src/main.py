import time
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

def run_collector(procfs, shared_pids):
    Collector(procfs, shared_pids, sleep_interval=2).collect()

def run_analyzer(cls, procfs, shared_pids, snapshot, interval):
    """Crea y ejecuta un analizador de la clase `cls`."""
    analyzer = cls(procfs, shared_pids, snapshot, interval)
    analyzer.analyze()

def run_display(snapshot, active_view):
    """Crea y ejecuta el display."""
    from src.display.display import Display
    from src.display.rich_renderer import RichRenderer

    renderer = RichRenderer()
    display = Display(renderer, snapshot, active_view)
    display.run_display()

# --- orquestador -------------------------------------------------------------

def main():
    mp.set_start_method("fork")

    procfs = ProcFS("/proc")

    manager = mp.Manager()
    snapshot = manager.dict()
    shared_pids = manager.list()
    
    active_view = mp.Value("i", 0)

    procs = [
        mp.Process(target=run_display, args=(snapshot, active_view), name="display"),
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
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nbajando...")
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.join()


if __name__ == "__main__":
    main()
