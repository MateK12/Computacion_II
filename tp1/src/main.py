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

ANALYZERS = [
    AnalyzerSummary,
    AnalyzerCPU,
    AnalyzerThreads,
    AnalyzerMemory,
    AnalyzerSignals,
    AnalyzerFileDescriptor,
    AnalyzerScheduling,
]

def run_collector(procfs, shared_pids):
    Collector(procfs, shared_pids, sleep_interval=2).collect()



def run_analyzer(cls, procfs, shared_pids, snapshot, interval):
    """Crea y ejecuta un analizador de la clase `cls`."""
    analyzer = cls(procfs, shared_pids, snapshot, interval)
    analyzer.analyze()

#TO DO separar en otro archivo
def _print_summary(snapshot):
    resumen = snapshot.get("summary")
    if resumen is None:
        print("esperando primer snapshot del analizador...")
        return
    data = resumen["data"]
    print(f"\n=== summary @ {resumen['ts']:.0f}  ({len(data)} procesos) ===")
    for pid, info in list(data.items())[:10]:
        print(f"{pid:>7}  {info['state']}  thr={info['threads']:<3}  {info['name']}")

# --- orquestador -------------------------------------------------------------

def main():
    mp.set_start_method("fork")

    procfs = ProcFS("/proc")

    manager = mp.Manager()
    snapshot = manager.dict()
    shared_pids = manager.list()

    procs = [
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

    try:
        while True:
            time.sleep(2)
            _print_summary(snapshot)
    except KeyboardInterrupt:
        print("\nbajando...")
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            p.join()


if __name__ == "__main__":
    main()
