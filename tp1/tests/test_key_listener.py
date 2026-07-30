"""Tests del listener de teclado de main. En lugar de una terminal usamos un
pipe: al listener le da igual de qué fd lee, y así los tests no necesitan tty."""

import multiprocessing as mp
import os
import unittest

from src.main import ANALYZER_SPECS, VIEW_ANALYZERS, run_key_listener


class TestRunKeyListener(unittest.TestCase):
	def setUp(self):
		self.read_fd, self.write_fd = os.pipe()
		self.active_view = mp.Value("i", 0)
		self.sort_mode = mp.Value("i", 0)
		self.intervals = [mp.Value("d", default) for _, default, _ in ANALYZER_SPECS]

	def tearDown(self):
		os.close(self.read_fd)
		os.close(self.write_fd)

	def _press(self, key: bytes) -> bool:
		os.write(self.write_fd, key)
		return run_key_listener(self.active_view, self.sort_mode, self.intervals, self.read_fd)

	def test_numero_cambia_la_vista(self):
		seguir = self._press(b"5")
		self.assertTrue(seguir)
		self.assertEqual(self.active_view.value, 4)

	def test_letra_cambia_la_vista(self):
		self._press(b"m")
		self.assertEqual(self.active_view.value, 1)

	def test_q_pide_salir(self):
		self.assertFalse(self._press(b"q"))

	def test_c_cicla_el_orden(self):
		for esperado in (1, 2, 0, 1):
			self._press(b"c")
			self.assertEqual(self.sort_mode.value, esperado)

	def test_tecla_no_mapeada_es_noop(self):
		seguir = self._press(b"x")
		self.assertTrue(seguir)
		self.assertEqual(self.active_view.value, 0)
		self.assertEqual(self.sort_mode.value, 0)

	def test_byte_no_ascii_es_noop(self):
		# Primer byte de 'ñ' en UTF-8: no debe explotar el decode ni cambiar nada.
		seguir = self._press(b"\xc3")
		self.assertTrue(seguir)
		self.assertEqual(self.active_view.value, 0)

	def test_flecha_son_tres_noops(self):
		# ↓ = ESC [ B: tres bytes que hoy no mapean a nada; no deben romper
		# ni cambiar la vista (queda para la sesión de navegación).
		os.write(self.write_fd, b"\x1b[B")
		for _ in range(3):
			self.assertTrue(run_key_listener(self.active_view, self.sort_mode, self.intervals, self.read_fd))
		self.assertEqual(self.active_view.value, 0)

	def test_mas_sube_el_intervalo_de_la_vista_activa(self):
		self.active_view.value = 4  # Señales -> analizador índice 4 (default 10.0)
		self._press(b"+")
		self.assertEqual(self.intervals[4].value, 10.5)

	def test_menos_baja_el_intervalo(self):
		self.active_view.value = 4
		self._press(b"-")
		self.assertEqual(self.intervals[4].value, 9.5)

	def test_menos_clampa_al_minimo_de_la_consigna(self):
		self.active_view.value = 4  # Señales: mínimo 5.0
		for _ in range(20):
			self._press(b"-")
		self.assertEqual(self.intervals[4].value, 5.0)

	def test_resumen_ajusta_summary_y_cpu_juntos(self):
		self.active_view.value = 0  # Resumen late con Summary (0) y CPU (1)
		self._press(b"+")
		self.assertEqual(self.intervals[0].value, 2.5)
		self.assertEqual(self.intervals[1].value, 2.5)
		self.assertEqual(self.intervals[3].value, 3.0)  # Memory intacto

	def test_mas_en_la_ayuda_no_toca_nada(self):
		self.active_view.value = 7
		self._press(b"+")
		for interval, (_, default, _) in zip(self.intervals, ANALYZER_SPECS):
			self.assertEqual(interval.value, default)

	def test_contrato_view_analyzers(self):
		# Toda vista alcanzable por teclado tiene entrada en VIEW_ANALYZERS
		# (aunque sea vacía) y sus índices caen dentro de ANALYZER_SPECS.
		from src.main import VIEW_KEYS
		for index in set(VIEW_KEYS.values()):
			self.assertIn(index, VIEW_ANALYZERS)
		for indices in VIEW_ANALYZERS.values():
			for i in indices:
				self.assertTrue(0 <= i < len(ANALYZER_SPECS))

	def test_h_y_signo_pregunta_van_a_la_ayuda(self):
		for key in (b"h", b"?"):
			self.active_view.value = 0
			self._press(key)
			self.assertEqual(self.active_view.value, 7)

	def test_contrato_view_keys_contra_views(self):
		# Invariante entre módulos: todo índice al que main puede mandar
		# la vista activa tiene que existir en la lista VIEWS del display.
		from src.display.display import VIEWS
		from src.main import VIEW_KEYS
		for key, index in VIEW_KEYS.items():
			self.assertTrue(0 <= index < len(VIEWS), f"tecla {key!r} apunta a índice {index} fuera de VIEWS")


if __name__ == "__main__":
	unittest.main()
