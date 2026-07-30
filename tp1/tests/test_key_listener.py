"""Tests del listener de teclado de main. En lugar de una terminal usamos un
pipe: al listener le da igual de qué fd lee, y así los tests no necesitan tty."""

import multiprocessing as mp
import os
import unittest

from src.main import ANALYZER_SPECS, VIEW_ANALYZERS, run_key_listener
from src.ui_state import UIState


def _make_ui():
	return UIState(
		active_view=mp.Value("i", 0),
		sort_mode=mp.Value("i", 0),
		intervals=[mp.Value("d", default) for _, default, _ in ANALYZER_SPECS],
		selected_row=mp.Value("i", 0),
		pinned_pid=mp.Value("i", -1),
		pid_at_selected=mp.Value("i", -1),
		row_count=mp.Value("i", 0),
	)


class TestRunKeyListener(unittest.TestCase):
	def setUp(self):
		self.read_fd, self.write_fd = os.pipe()
		self.ui = _make_ui()

	def tearDown(self):
		os.close(self.read_fd)
		os.close(self.write_fd)

	def _press(self, key: bytes) -> bool:
		os.write(self.write_fd, key)
		return run_key_listener(self.ui, self.read_fd)

	def test_numero_cambia_la_vista(self):
		seguir = self._press(b"5")
		self.assertTrue(seguir)
		self.assertEqual(self.ui.active_view.value, 4)

	def test_letra_cambia_la_vista(self):
		self._press(b"m")
		self.assertEqual(self.ui.active_view.value, 1)

	def test_h_y_signo_pregunta_van_a_la_ayuda(self):
		for key in (b"h", b"?"):
			self.ui.active_view.value = 0
			self._press(key)
			self.assertEqual(self.ui.active_view.value, 7)

	def test_q_pide_salir(self):
		self.assertFalse(self._press(b"q"))

	def test_c_cicla_el_orden(self):
		for esperado in (1, 2, 0, 1):
			self._press(b"c")
			self.assertEqual(self.ui.sort_mode.value, esperado)

	def test_tecla_no_mapeada_es_noop(self):
		seguir = self._press(b"x")
		self.assertTrue(seguir)
		self.assertEqual(self.ui.active_view.value, 0)
		self.assertEqual(self.ui.sort_mode.value, 0)

	def test_byte_no_ascii_es_noop(self):
		# Primer byte de 'ñ' en UTF-8: no debe explotar el decode ni cambiar nada.
		seguir = self._press(b"\xc3")
		self.assertTrue(seguir)
		self.assertEqual(self.ui.active_view.value, 0)

	# --- intervalos (+/-) ---------------------------------------------------

	def test_mas_sube_el_intervalo_de_la_vista_activa(self):
		self.ui.active_view.value = 4  # Señales -> analizador índice 4 (default 10.0)
		self._press(b"+")
		self.assertEqual(self.ui.intervals[4].value, 10.5)

	def test_menos_baja_el_intervalo(self):
		self.ui.active_view.value = 4
		self._press(b"-")
		self.assertEqual(self.ui.intervals[4].value, 9.5)

	def test_menos_clampa_al_minimo_de_la_consigna(self):
		self.ui.active_view.value = 4  # Señales: mínimo 5.0
		for _ in range(20):
			self._press(b"-")
		self.assertEqual(self.ui.intervals[4].value, 5.0)

	def test_resumen_ajusta_summary_y_cpu_juntos(self):
		self.ui.active_view.value = 0  # Resumen late con Summary (0) y CPU (1)
		self._press(b"+")
		self.assertEqual(self.ui.intervals[0].value, 2.5)
		self.assertEqual(self.ui.intervals[1].value, 2.5)
		self.assertEqual(self.ui.intervals[3].value, 3.0)  # Memory intacto

	def test_mas_en_la_ayuda_no_toca_nada(self):
		self.ui.active_view.value = 7
		self._press(b"+")
		for interval, (_, default, _) in zip(self.ui.intervals, ANALYZER_SPECS):
			self.assertEqual(interval.value, default)

	# --- flechas y pin --------------------------------------------------------

	def test_flecha_abajo_mueve_el_cursor(self):
		self.ui.row_count.value = 10
		self._press(b"\x1b[B")
		self.assertEqual(self.ui.selected_row.value, 1)

	def test_flecha_arriba_clampa_en_cero(self):
		self.ui.row_count.value = 10
		self._press(b"\x1b[A")
		self.assertEqual(self.ui.selected_row.value, 0)

	def test_flecha_abajo_clampa_en_row_count(self):
		self.ui.row_count.value = 3
		for _ in range(6):
			self._press(b"\x1b[B")
		self.assertEqual(self.ui.selected_row.value, 2)

	def test_esc_solo_es_noop(self):
		seguir = self._press(b"\x1b")
		self.assertTrue(seguir)
		self.assertEqual(self.ui.selected_row.value, 0)

	def test_enter_pinnea_el_pid_publicado_por_el_display(self):
		self.ui.pid_at_selected.value = 123
		self._press(b"\r")
		self.assertEqual(self.ui.pinned_pid.value, 123)

	def test_enter_con_pin_activo_despinnea(self):
		self.ui.pinned_pid.value = 123
		self._press(b"\r")
		self.assertEqual(self.ui.pinned_pid.value, -1)

	def test_enter_sin_pid_publicado_es_noop(self):
		# El display todavía no publicó nada (-1): no hay qué pinnear.
		self._press(b"\n")
		self.assertEqual(self.ui.pinned_pid.value, -1)

	def test_mover_el_cursor_despinnea(self):
		self.ui.row_count.value = 10
		self.ui.pinned_pid.value = 123
		self._press(b"\x1b[B")
		self.assertEqual(self.ui.pinned_pid.value, -1)

	# --- contratos entre módulos ---------------------------------------------

	def test_contrato_view_keys_contra_views(self):
		# Todo índice al que main puede mandar la vista activa existe en VIEWS.
		from src.display.display import VIEWS
		from src.main import VIEW_KEYS
		for key, index in VIEW_KEYS.items():
			self.assertTrue(0 <= index < len(VIEWS), f"tecla {key!r} apunta a índice {index} fuera de VIEWS")

	def test_contrato_view_analyzers(self):
		# Toda vista alcanzable por teclado tiene entrada en VIEW_ANALYZERS
		# (aunque sea vacía) y sus índices caen dentro de ANALYZER_SPECS.
		from src.main import VIEW_KEYS
		for index in set(VIEW_KEYS.values()):
			self.assertIn(index, VIEW_ANALYZERS)
		for indices in VIEW_ANALYZERS.values():
			for i in indices:
				self.assertTrue(0 <= i < len(ANALYZER_SPECS))


if __name__ == "__main__":
	unittest.main()
