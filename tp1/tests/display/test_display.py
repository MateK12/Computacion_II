"""Tests del orden de filas que aplica el display antes de renderizar (tecla 'c')."""

import unittest

from src.display.display import _sorted_view
from src.display.models import ViewTable


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


if __name__ == "__main__":
	unittest.main()
