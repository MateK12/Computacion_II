"""Tests de _reload_config: verifica que SIGHUP realmente cambia los intervalos."""

import multiprocessing as mp
import os
import tempfile
import unittest

from src.main import ANALYZER_SPECS, _reload_config
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
        filter_mode=mp.Value("i", 0),
        filter_value=mp.Array("u", 128),
        verbose_mode=mp.Value("i", 0),
    )


class TestReloadConfig(unittest.TestCase):
    def test_cambia_intervalos_presentes_en_json(self):
        """Las claves que existen en el JSON pisan el intervalo actual."""
        ui = _make_ui()
        # Intervalo original de Summary (índice 0) es 2.0
        self.assertEqual(ui.intervals[0].value, 2.0)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"AnalyzerSummary": 0.7, "AnalyzerMemory": 5.0}')
            path = f.name

        try:
            _reload_config(ui, path=path)
            self.assertEqual(ui.intervals[0].value, 0.7)   # Summary cambió
            self.assertEqual(ui.intervals[3].value, 5.0)   # Memory cambió
        finally:
            os.remove(path)

    def test_respeta_el_minimo_de_la_consigna(self):
        """Si el JSON pone un valor menor al mínimo, se clampa."""
        ui = _make_ui()
        # Señales (índice 4) tiene mínimo 5.0
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"AnalyzerSignals": 0.1}')
            path = f.name

        try:
            _reload_config(ui, path=path)
            self.assertEqual(ui.intervals[4].value, 5.0)
        finally:
            os.remove(path)

    def test_json_inexistente_es_silencioso(self):
        """Si el archivo no existe, no explota y los intervalos quedan intactos."""
        ui = _make_ui()
        originales = [iv.value for iv in ui.intervals]
        _reload_config(ui, path="/no/existe/config.json")
        self.assertEqual([iv.value for iv in ui.intervals], originales)

    def test_json_malformado_es_silencioso(self):
        """JSON inválido: no explota, intervalos intactos."""
        ui = _make_ui()
        originales = [iv.value for iv in ui.intervals]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("esto no es json")
            path = f.name

        try:
            _reload_config(ui, path=path)
            self.assertEqual([iv.value for iv in ui.intervals], originales)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
