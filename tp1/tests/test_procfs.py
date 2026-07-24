import os
import unittest
from src.procfs import ProcFS
import tempfile

class TestProcfs(unittest.TestCase):
    def test_procfs(self):
        proc = ProcFS('/proc')
        cpuinfo = proc._read_file('cpuinfo')
        self.assertIn('processor', cpuinfo)
        self.assertIn('model name', cpuinfo)
        self.assertIn('cpu MHz', cpuinfo)
    def test_parse_stat(self):
        # Ejemplo de contenido de /proc/[pid]/stat
        # Se rellena hasta fields[38] (policy) porque parse_stat ahora lo lee.
        stat_content = "12345 (python) R 6789 1234 5678 0 -1 4194560 100 0 0 0 10 20 0 0 20 0 1 0 123456789 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
        parsed = ProcFS.parse_stat(stat_content)
        self.assertEqual(parsed['pid'], 12345)
        self.assertEqual(parsed['comm'], 'python')
        self.assertEqual(parsed['state'], 'R')
        self.assertEqual(parsed['ppid'], 6789)
        self.assertEqual(parsed['utime'], 10)
    def test_parse_stat_with_spaces(self):
        # El comando tiene espacios y está entre paréntesis
        stat_content = "54321 (my python script) S 9876 5432 1234 0 -1 4194560 200 0 0 0 15 25 0 0 20 0 1 0 987654321 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
        parsed = ProcFS.parse_stat(stat_content)
        self.assertEqual(parsed['pid'], 54321)
        self.assertEqual(parsed['comm'], 'my python script')
        self.assertEqual(parsed['state'], 'S')
        self.assertEqual(parsed['ppid'], 9876)
        self.assertEqual(parsed['utime'], 15)

    def test_parse_stat_with_parentheses(self):
        # Caso maligno: el comm contiene paréntesis — solo el ÚLTIMO ')' cierra
        stat_content = "123 (hola) (mundo) S 1 123 123 0 -1 4194304 100 0 5 0 7 3 0 0 20 0 1 0 1000 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
        parsed = ProcFS.parse_stat(stat_content)
        self.assertEqual(parsed['pid'], 123)
        self.assertEqual(parsed['comm'], 'hola) (mundo')
        self.assertEqual(parsed['state'], 'S')
        self.assertEqual(parsed['utime'], 7)
        self.assertEqual(parsed['stime'], 3)

    STATUS_FIXTURE = (
        "Name:\tzsh\n"
        "State:\tS (sleeping)\n"
        "Pid:\t12345\n"
        "PPid:\t6789\n"
        "Uid:\t1000\t1000\t1000\t1000\n"
        "VmRSS:\t   12345 kB\n"
        "Threads:\t4\n"
        "SigBlk:\t0000000000010000\n"
    )

    def test_parse_status(self):
        parsed = ProcFS.parse_status(self.STATUS_FIXTURE)
        self.assertEqual(parsed['Name'], 'zsh')
        self.assertEqual(parsed['State'], 'S (sleeping)')
        self.assertEqual(parsed['PPid'], '6789')
        self.assertEqual(parsed['Threads'], '4')

    def test_parse_status_valores_crudos(self):
        # Los valores se devuelven crudos: Uid conserva sus 4 campos,
        # VmRSS conserva la unidad. Interpretarlos es del consumidor.
        parsed = ProcFS.parse_status(self.STATUS_FIXTURE)
        self.assertEqual(parsed['Uid'], '1000\t1000\t1000\t1000')
        self.assertEqual(parsed['VmRSS'], '12345 kB')
        self.assertEqual(parsed['SigBlk'], '0000000000010000')

    def test_parse_status_ignora_lineas_sin_clave(self):
        parsed = ProcFS.parse_status("Name:\tzsh\n\nlinea basura sin separador\n")
        self.assertEqual(parsed, {'Name': 'zsh'})
    def test_list_pids(self):
        proc = ProcFS('/proc')
        pids = list(proc.list_pids())
        self.assertIn(os.getpid(), pids)

    def test_list_pid_only_dirs_numeric(self):
      with tempfile.TemporaryDirectory() as tmp:
          os.mkdir(os.path.join(tmp, "1234"))
          os.mkdir(os.path.join(tmp, "5678"))
          os.mkdir(os.path.join(tmp, "bus"))      
          open(os.path.join(tmp, "cpuinfo"), "w").close()  
          proc = ProcFS(tmp)
          pids = sorted(proc.list_pids()) #ordenar para que ande assertEqual   
          self.assertEqual(pids, [1234, 5678])
    #region file descriptors
    def test_read_fd_links(self):
        # Fabricamos un /proc falso: tmp/<pid>/fd/ con symlinks reales, tal como
        # los tendría un proceso vivo. read_fd_links solo lee el destino crudo.
        with tempfile.TemporaryDirectory() as tmp:
            fd_dir = os.path.join(tmp, "1234", "fd")
            os.makedirs(fd_dir)
            os.symlink("/dev/null", os.path.join(fd_dir, "0"))
            os.symlink("socket:[12345]", os.path.join(fd_dir, "3"))
            proc = ProcFS(tmp)
            fd_links = proc.read_fd_links(1234)
            self.assertEqual(fd_links, {0: "/dev/null", 3: "socket:[12345]"})

    def test_read_fd_links_ignora_no_symlinks(self):
        # En /proc/<pid>/fd todo es symlink, pero por robustez read_fd_links
        # filtra con is_symlink(): un archivo regular en el dir no debe aparecer.
        with tempfile.TemporaryDirectory() as tmp:
            fd_dir = os.path.join(tmp, "1234", "fd")
            os.makedirs(fd_dir)
            os.symlink("/dev/null", os.path.join(fd_dir, "0"))
            open(os.path.join(fd_dir, "basura"), "w").close() #forma de crear archivo
            proc = ProcFS(tmp)
            fd_links = proc.read_fd_links(1234)
            self.assertEqual(fd_links, {0: "/dev/null"})
    #endregion