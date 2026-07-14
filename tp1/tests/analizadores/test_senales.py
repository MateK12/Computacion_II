import unittest

from src.analizadores.senales import AnalyzerSignals


class MockProcFS:
    """Doble de prueba: devuelve un status fijo por PID. Para simular un proceso
    que muere a mitad de lectura, registrá su PID en `dead` con la excepción a lanzar."""

    def __init__(self, status_por_pid, dead=None):
        self.status_por_pid = status_por_pid
        self.dead = dead or {}

    def read_status(self, pid):
        if pid in self.dead:
            raise self.dead[pid]
        return self.status_por_pid[pid]


def mock_status(**overrides):
    """Status de un proceso normal con las 5 máscaras de señales (formato real de /proc):
    SigCgt captura SIGINT (2), SigIgn ignora SIGPIPE (13), el resto vacío."""
    base = {
        "SigBlk": "0000000000000000",
        "SigIgn": "0000000000001000",   # bit 12 -> señal 13 (SIGPIPE)
        "SigCgt": "0000000000000002",   # bit 1  -> señal 2 (SIGINT)
        "SigPnd": "0000000000000000",
        "ShdPnd": "0000000000000000",
    }
    base.update(overrides)
    return base


class TestAnalyzerSignals(unittest.TestCase):

    def _analyzer(self):
        return AnalyzerSignals(MockProcFS({}), [], {}, 1)

    def test_decode_mask_bit_conocido(self):
        """'0000000000000002' tiene solo el bit 1 -> señal 2 (SIGINT)."""
        self.assertEqual(self._analyzer()._decode_mask("0000000000000002"), [2])

    def test_decode_mask_vacia(self):
        """Máscara toda en cero -> ninguna señal en el conjunto."""
        self.assertEqual(self._analyzer()._decode_mask("0000000000000000"), [])

    def test_decode_mask_multiples_bits_en_orden(self):
        """'0000000000010002' tiene los bits 1 y 16 -> señales 2 y 17, en orden ascendente."""
        self.assertEqual(self._analyzer()._decode_mask("0000000000010002"), [2, 17])

    def test_extract_mapea_las_cinco_mascaras(self):
        """_extract devuelve las 5 claves, cada una con la lista de señales decodificada."""
        resultado = self._analyzer()._extract(mock_status())
        self.assertEqual(
            resultado,
            {
                "blocked": [],
                "ignored": [13],
                "caught": [2],
                "pending_thread": [],
                "pending_shared": [],
            },
        )

    def test_ciclo_publica_la_clave_signals_con_ts_y_data(self):
        """Tras _ciclo(), snapshot['signals'] tiene la forma {'ts': ..., 'data': {...}}."""
        analyzer = self._analyzer()
        analyzer._ciclo()
        self.assertIn("signals", analyzer.snapshot)
        self.assertIn("ts", analyzer.snapshot["signals"])
        self.assertIn("data", analyzer.snapshot["signals"])

    def test_ciclo_indexa_la_data_por_pid(self):
        """snapshot['signals']['data'] tiene una entrada por cada PID vivo."""
        analyzer = self._analyzer()
        analyzer.shared_pids.extend([1, 2])
        analyzer.procfs.status_por_pid.update(
            {1: mock_status(), 2: mock_status(SigBlk="0000000000000004")}  # bit 2 -> señal 3
        )
        analyzer._ciclo()
        data = analyzer.snapshot["signals"]["data"]
        self.assertIn(1, data)
        self.assertIn(2, data)
        self.assertEqual(data[2]["blocked"], [3])

    def test_ciclo_saltea_proceso_muerto(self):
        """Un PID cuyo read_status lanza FileNotFoundError o ProcessLookupError
        (el proceso murió entre el listado y la lectura) no aparece en data y no crashea."""
        analyzer = self._analyzer()
        analyzer.shared_pids.extend([1, 2, 3])
        analyzer.procfs.status_por_pid.update({1: mock_status()})
        analyzer.procfs.dead[2] = FileNotFoundError()
        analyzer.procfs.dead[3] = ProcessLookupError()
        analyzer._ciclo()
        data = analyzer.snapshot["signals"]["data"]
        self.assertIn(1, data)
        self.assertNotIn(2, data)
        self.assertNotIn(3, data)


if __name__ == "__main__":
    unittest.main()
