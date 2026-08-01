"""Prueba de integración: levanta main.py real, envía señales y verifica comportamiento.

Corre sin TTY para verificar que el monitor no explota en entornos headless.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest


class TestIntegracionSenales(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.dump_pattern = os.path.join(self.tmpdir, "dump_*.json")
        # Cambiamos al directorio del TP para que main encuentre config.json y escriba dumps ahí
        self.orig_dir = os.getcwd()
        os.chdir(os.path.join(os.path.dirname(__file__), ".."))

    def tearDown(self):
        os.chdir(self.orig_dir)
        # Limpieza de dumps
        import glob
        for f in glob.glob("dump_*.json"):
            os.remove(f)

    def _start_monitor(self):
        """Levanta main.py sin TTY y devuelve el objeto Popen."""
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        proc = subprocess.Popen(
            [sys.executable, "-m", "src.main"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=env,
        )
        return proc

    def _wait_for_processes(self, parent_pid, timeout=10):
        """Espera a que el padre y sus hijos estén vivos."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            try:
                # Verificamos que el padre exista
                os.kill(parent_pid, 0)
                # Contamos hijos
                result = subprocess.run(
                    ["pgrep", "-P", str(parent_pid)],
                    capture_output=True, text=True
                )
                hijos = [int(x) for x in result.stdout.strip().split("\n") if x]
                if len(hijos) >= 9:  # display + collector + 7 analizadores
                    return hijos
            except (ProcessLookupError, OSError):
                pass
            time.sleep(0.5)
        return []

    def test_sigusr1_crea_dump_y_sigint_termina_limpio(self):
        """End-to-end: levanta el monitor, envía SIGUSR1 (dump), luego SIGINT (shutdown)."""
        proc = self._start_monitor()
        try:
            hijos = self._wait_for_processes(proc.pid, timeout=10)
            self.assertTrue(len(hijos) >= 9, f"No arrancaron todos los hijos: {len(hijos)}")

            # SIGUSR1 → dump
            os.kill(proc.pid, signal.SIGUSR1)
            time.sleep(1)
            import glob
            dumps = glob.glob("dump_*.json")
            self.assertTrue(len(dumps) >= 1, "SIGUSR1 no creó ningún dump")

            # SIGINT → shutdown limpio
            os.kill(proc.pid, signal.SIGINT)
            proc.wait(timeout=15)

            # Verificamos que no haya muerto por señal (exit code 0 o 130 para SIGINT)
            self.assertIn(proc.returncode, (0, 130), f"Exit code inesperado: {proc.returncode}")

            # Verificamos que no queden hijos huérfanos
            for hijo in hijos:
                try:
                    os.kill(hijo, 0)
                    self.fail(f"Hijo {hijo} sigue vivo después del shutdown")
                except ProcessLookupError:
                    pass  # bien, no existe

            # Verificamos stderr: no debe tener BrokenPipeError ni ConnectionResetError
            stderr = proc.stderr.read().decode("utf-8", errors="ignore")
            self.assertNotIn("BrokenPipeError", stderr)
            self.assertNotIn("ConnectionResetError", stderr)
            self.assertNotIn("EOFError", stderr)

        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    unittest.main()
