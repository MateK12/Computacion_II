import unittest

# from src.analizadores.summary import AnalyzerSummary



class TestFDs(unittest.TestCase):


    def test_lists_open_fds(self):
        """'S (sleeping)' -> 'S' (no la descripción completa)."""
        unittest.fail("TODO")
    def test_inferrs_fd_type_correctly(self):
        """Devuelve 'file', 'socket', 'pipe' o 'unknown' según el tipo de FD."""
        unittest.fail("TODO")
    def test_shows_symlink_destination(self):
        """Devuelve el destino del symlink (p. ej. '/dev/null' para un FD de /dev/null)."""
        unittest.fail("TODO")
if __name__ == "__main__":
    unittest.main()
