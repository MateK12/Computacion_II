"""Tests del listener de teclado de main. En lugar de una terminal usamos un
pipe: al listener le da igual de qué fd lee, y así los tests no necesitan tty."""

import multiprocessing as mp
import os
import unittest

from src.main import run_key_listener


class TestRunKeyListener(unittest.TestCase):
	def setUp(self):
		self.read_fd, self.write_fd = os.pipe()
		self.active_view = mp.Value("i", 0)
		self.sort_mode = mp.Value("i", 0)

	def tearDown(self):
		os.close(self.read_fd)
		os.close(self.write_fd)

	def _press(self, key: bytes) -> bool:
		os.write(self.write_fd, key)
		return run_key_listener(self.active_view, self.sort_mode, self.read_fd)

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
			self.assertTrue(run_key_listener(self.active_view, self.sort_mode, self.read_fd))
		self.assertEqual(self.active_view.value, 0)

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
