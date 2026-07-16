import time
import multiprocessing as mp

from src.procfs import ProcFS
from src.collector import Collector
from src.analizadores.summary import AnalyzerSummary



def run_collector(procfs, shared_pids):
    Collector(procfs, shared_pids, sleep_interval=2).collect()


def run_summary(procfs, shared_pids, snapshot):
    AnalyzerSummary(procfs, shared_pids, snapshot, interval=2).analyze()


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
        mp.Process(target=run_summary, args=(procfs, shared_pids, snapshot), name="summary"),
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
