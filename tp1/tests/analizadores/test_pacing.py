"""Tests del sleep de a ticks que comparte todo analizador."""

import multiprocessing as mp
import threading
import time
import unittest

from src.analizadores.pacing import sleep_interval


class TestSleepInterval(unittest.TestCase):
	def test_intervalo_cero_vuelve_inmediato(self):
		interval = mp.Value("d", 0.0)
		start = time.monotonic()
		sleep_interval(interval)
		self.assertLess(time.monotonic() - start, 0.1)

	def test_duerme_al_menos_el_intervalo(self):
		interval = mp.Value("d", 0.05)
		start = time.monotonic()
		sleep_interval(interval, tick=0.01)
		self.assertGreaterEqual(time.monotonic() - start, 0.05)

	def test_achicar_el_intervalo_despierta_antes(self):
		# La razón de ser del módulo: dormimos "60 segundos" pero alguien
		# (main con '-') achica el Value a mitad de camino -> volvemos en
		# ~1 tick, no en 60s.
		interval = mp.Value("d", 60.0)

		def acortar():
			time.sleep(0.03)
			interval.value = 0.0

		threading.Thread(target=acortar).start()
		start = time.monotonic()
		sleep_interval(interval, tick=0.01)
		self.assertLess(time.monotonic() - start, 1.0)


if __name__ == "__main__":
	unittest.main()
