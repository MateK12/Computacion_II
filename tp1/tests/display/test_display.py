"""Tests del post-procesado que aplica el display antes de renderizar:
orden de filas (tecla 'c') y selección/ventana (flechas + Enter)."""

import multiprocessing as mp
import unittest

from src.display.display import _apply_selection, _sorted_view, _window
from src.display.models import ViewTable
from src.main import ANALYZER_SPECS
from src.ui_state import UIState


def _tabla_resumen():
	# Filas al estilo view_summary: PID crudo, CPU% crudo, RSS ya formateado.
	return ViewTable(
		title="Resumen",
		columns=["PID", "Estado", "CPU%", "RSS", "Threads", "Comando"],
		rows=[
			[1, "S", 0.5, "8.0 MB", 1, "init"],
			[2, "R", 90.0, "512 KB", 4, "hog"],
			[3, "S", None, None, 1, "kthread"],
			[4, "R", 12.0, "1.5 GB", 2, "browser"],
		],
		ts=1.0,
	)


class TestSortedView(unittest.TestCase):
	def test_modo_0_devuelve_la_vista_intacta(self):
		# Modo 0 = orden natural (PID): el display no toca nada, ni el título.
		table = _tabla_resumen()
		self.assertIs(_sorted_view(table, 0), table)

	def test_modo_1_ordena_por_cpu_descendente(self):
		result = _sorted_view(_tabla_resumen(), 1)
		self.assertEqual([row[0] for row in result.rows], [2, 4, 1, 3])

	def test_modo_1_none_al_final(self):
		result = _sorted_view(_tabla_resumen(), 1)
		self.assertIsNone(result.rows[-1][2])

	def test_modo_2_ordena_por_rss_parseando_unidades(self):
		# '1.5 GB' > '8.0 MB' > '512 KB' aunque alfabéticamente sea al revés.
		result = _sorted_view(_tabla_resumen(), 2)
		self.assertEqual([row[0] for row in result.rows], [4, 1, 2, 3])

	def test_titulo_indica_el_orden_activo(self):
		result = _sorted_view(_tabla_resumen(), 1)
		self.assertEqual(result.title, "Resumen ↓CPU%")

	def test_vista_sin_la_columna_queda_intacta(self):
		# view_sistema no tiene CPU%/RSS/PID: se muestra tal cual vino.
		table = ViewTable(title="Sistema", columns=["Métrica", "Valor 1"], rows=[["Uptime", "5d"]], ts=1.0)
		self.assertIs(_sorted_view(table, 1), table)

	def test_no_muta_la_vista_original(self):
		table = _tabla_resumen()
		pids_antes = [row[0] for row in table.rows]
		_sorted_view(table, 1)
		self.assertEqual([row[0] for row in table.rows], pids_antes)

	def test_modo_2_usa_vmrss_en_vista_memoria(self):
		table = ViewTable(
			title="Memoria",
			columns=["PID", "VmRSS", "Comando"],
			rows=[[1, "512 KB", "a"], [2, "2.0 MB", "b"]],
			ts=1.0,
		)
		result = _sorted_view(table, 2)
		self.assertEqual([row[0] for row in result.rows], [2, 1])


def _make_ui(selected_row=0, pinned_pid=-1):
	return UIState(
		active_view=mp.Value("i", 0),
		sort_mode=mp.Value("i", 0),
		intervals=[mp.Value("d", default) for _, default, _ in ANALYZER_SPECS],
		selected_row=mp.Value("i", selected_row),
		pinned_pid=mp.Value("i", pinned_pid),
		pid_at_selected=mp.Value("i", -1),
		row_count=mp.Value("i", 0),
		filter_mode=mp.Value("i", 0),
		filter_value=mp.Array("u", 128),
		verbose_mode=mp.Value("i", 0),
	)


def _tabla_pids(pids):
	return ViewTable(
		title="Resumen",
		columns=["PID", "Comando"],
		rows=[[pid, f"proc{pid}"] for pid in pids],
		ts=1.0,
	)


class TestApplySelection(unittest.TestCase):
	def test_seleccion_posicional_y_publicaciones(self):
		ui = _make_ui(selected_row=2)
		result = _apply_selection(_tabla_pids([10, 20, 30, 40]), ui, page=10)
		self.assertEqual(result.selected, 2)
		self.assertEqual(ui.pid_at_selected.value, 30)
		self.assertEqual(ui.row_count.value, 4)

	def test_cursor_mas_alla_de_la_tabla_clampea(self):
		# main puede tener un cursor viejo más grande que la tabla actual
		ui = _make_ui(selected_row=99)
		result = _apply_selection(_tabla_pids([10, 20, 30]), ui, page=10)
		self.assertEqual(result.selected, 2)
		self.assertEqual(ui.pid_at_selected.value, 30)

	def test_pin_sigue_al_pid_aunque_cambie_el_orden(self):
		# El pin es identidad: 30 pinneado, la tabla llega reordenada y el
		# cursor posicional apunta a otro lado -> se resalta donde esté el 30.
		ui = _make_ui(selected_row=0, pinned_pid=30)
		result = _apply_selection(_tabla_pids([30, 10, 20]), ui, page=10)
		self.assertEqual(result.selected, 0)
		result = _apply_selection(_tabla_pids([10, 20, 30]), ui, page=10)
		self.assertEqual(result.selected, 2)
		self.assertEqual(ui.pid_at_selected.value, 30)

	def test_pin_de_pid_muerto_cae_a_posicional(self):
		ui = _make_ui(selected_row=1, pinned_pid=999)
		result = _apply_selection(_tabla_pids([10, 20, 30]), ui, page=10)
		self.assertEqual(result.selected, 1)
		self.assertEqual(ui.pid_at_selected.value, 20)

	def test_ventana_recorta_y_rebasa_el_indice(self):
		# 10 filas, página de 3, selección en la 5: la ventana la contiene
		# y `selected` queda relativo a la ventana.
		ui = _make_ui(selected_row=5)
		result = _apply_selection(_tabla_pids(list(range(1, 11))), ui, page=3)
		self.assertEqual(len(result.rows), 3)
		fila = result.rows[result.selected]
		self.assertEqual(fila[0], 6)  # el PID 6 es la fila 5 (0-based)

	def test_vista_sin_pid_queda_intacta(self):
		ui = _make_ui(selected_row=3)
		table = ViewTable(title="Ayuda", columns=["Tecla", "Acción"], rows=[["q", "Salir"]], ts=None)
		result = _apply_selection(table, ui, page=10)
		self.assertIs(result, table)
		self.assertIsNone(result.selected)
		self.assertEqual(ui.pid_at_selected.value, -1)
		self.assertEqual(ui.row_count.value, 0)

	def test_tabla_vacia(self):
		ui = _make_ui()
		table = ViewTable(title="Resumen", columns=["PID", "Comando"], rows=[], ts=1.0)
		result = _apply_selection(table, ui, page=10)
		self.assertIs(result, table)
		self.assertEqual(ui.pid_at_selected.value, -1)


class TestWindow(unittest.TestCase):
	def test_seleccion_al_principio(self):
		self.assertEqual(_window(0, 100, 10), (0, 10))

	def test_seleccion_centrada(self):
		start, end = _window(50, 100, 10)
		self.assertTrue(start <= 50 < end)

	def test_seleccion_al_final_no_pasa_el_total(self):
		start, end = _window(99, 100, 10)
		self.assertEqual((start, end), (90, 100))

	def test_tabla_mas_chica_que_la_pagina(self):
		self.assertEqual(_window(2, 5, 10), (0, 10))


if __name__ == "__main__":
	unittest.main()
