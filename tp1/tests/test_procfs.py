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

    #region globales (/proc/stat, meminfo, loadavg, uptime)

    STAT_GLOBAL_FIXTURE = (
        "cpu  54114 517 16474 405222 2053 0 924 0 12 3\n"
        "cpu0 6665 38 2168 50622 259 0 53 0 0 0\n"
        "cpu1 6700 40 2100 50700 260 0 55 0 0 0\n"
        "intr 3921861 0 807 0 0 0 0 0 0 0 36\n"
        "ctxt 7098234\n"
        "btime 1784937473\n"
        "processes 16520\n"
        "procs_running 2\n"
        "procs_blocked 0\n"
        "softirq 1234567 1 2 3 4 5 6 7 8 9 10\n"
    )

    def test_parse_stat_global_linea_cpu(self):
        # Las 10 categorías salen nombradas, en el orden del kernel.
        parsed = ProcFS.parse_stat_global(self.STAT_GLOBAL_FIXTURE)
        self.assertEqual(parsed["cpu"], {
            "user": 54114, "nice": 517, "system": 16474, "idle": 405222,
            "iowait": 2053, "irq": 0, "softirq": 924, "steal": 0,
            "guest": 12, "guest_nice": 3,
        })

    def test_parse_stat_global_escalares(self):
        parsed = ProcFS.parse_stat_global(self.STAT_GLOBAL_FIXTURE)
        self.assertEqual(parsed["ctxt"], 7098234)
        self.assertEqual(parsed["btime"], 1784937473)
        self.assertEqual(parsed["processes"], 16520)
        self.assertEqual(parsed["procs_running"], 2)
        self.assertEqual(parsed["procs_blocked"], 0)

    def test_parse_stat_global_ignora_por_core_y_vectores(self):
        # Caso maligno: si el parser usara startswith("cpu"), las líneas cpu0/cpu1
        # pisarían la agregada. Y 'softirq' como LÍNEA no debe confundirse con la
        # CATEGORÍA 'softirq' de la línea cpu (924, no 1234567).
        parsed = ProcFS.parse_stat_global(self.STAT_GLOBAL_FIXTURE)
        self.assertEqual(parsed["cpu"]["user"], 54114)   # no 6665 ni 6700
        self.assertEqual(parsed["cpu"]["softirq"], 924)  # no 1234567
        self.assertNotIn("cpu0", parsed)
        self.assertNotIn("intr", parsed)
        self.assertNotIn("softirq", parsed)

    def test_parse_stat_global_campos_faltantes(self):
        # Kernel viejo: la línea cpu trae solo 8 categorías (sin guest/guest_nice).
        # No debe reventar; las que faltan quedan en 0.
        parsed = ProcFS.parse_stat_global("cpu  100 2 30 400 5 0 6 0\nctxt 999\n")
        self.assertEqual(parsed["cpu"]["steal"], 0)
        self.assertEqual(parsed["cpu"]["guest"], 0)
        self.assertEqual(parsed["cpu"]["guest_nice"], 0)
        self.assertEqual(parsed["cpu"]["user"], 100)
        self.assertEqual(len(parsed["cpu"]), 10)  # la forma no cambia

    def test_parse_stat_global_ignora_lineas_vacias(self):
        parsed = ProcFS.parse_stat_global("\ncpu  1 2 3 4 5 6 7 8 9 10\n\nbtime 42\n")
        self.assertEqual(parsed["cpu"]["user"], 1)
        self.assertEqual(parsed["btime"], 42)

    MEMINFO_FIXTURE = (
        "MemTotal:       24293772 kB\n"
        "MemFree:        14822604 kB\n"
        "MemAvailable:   19346884 kB\n"
        "Buffers:          424800 kB\n"
        "Cached:          4576184 kB\n"
        "SwapTotal:       8388604 kB\n"
        "SwapFree:        8388604 kB\n"
        "HugePages_Total:       0\n"
        "Hugepagesize:       2048 kB\n"
    )

    def test_parse_meminfo(self):
        # La unidad 'kB' se descarta: los valores salen como int.
        parsed = ProcFS.parse_meminfo(self.MEMINFO_FIXTURE)
        self.assertEqual(parsed["MemTotal"], 24293772)
        self.assertEqual(parsed["MemAvailable"], 19346884)
        self.assertEqual(parsed["SwapFree"], 8388604)
        self.assertIsInstance(parsed["MemFree"], int)

    def test_parse_meminfo_linea_sin_unidad(self):
        # No todas las líneas traen 'kB' (HugePages_* vienen peladas).
        parsed = ProcFS.parse_meminfo(self.MEMINFO_FIXTURE)
        self.assertEqual(parsed["HugePages_Total"], 0)

    def test_parse_meminfo_devuelve_todas_las_claves(self):
        parsed = ProcFS.parse_meminfo(self.MEMINFO_FIXTURE)
        self.assertEqual(len(parsed), 9)

    def test_parse_meminfo_ignora_lineas_sin_clave(self):
        parsed = ProcFS.parse_meminfo("MemTotal: 100 kB\n\nbasura sin separador\n")
        self.assertEqual(parsed, {"MemTotal": 100})

    def test_parse_loadavg(self):
        # El 4º campo es compuesto: 'runnable/threads_totales'.
        parsed = ProcFS.parse_loadavg("0.43 1.04 0.74 1/1534 16514\n")
        self.assertEqual(parsed, {
            "load_1m": 0.43, "load_5m": 1.04, "load_15m": 0.74,
            "runnable": 1, "total_threads": 1534, "last_pid": 16514,
        })

    def test_parse_uptime(self):
        # El 2º campo es idle SUMADO sobre todos los cores: puede ser mayor que el 1º.
        parsed = ProcFS.parse_uptime("607.19 4052.24\n")
        self.assertEqual(parsed, {"uptime": 607.19, "idle": 4052.24})

    def test_readers_globales_contra_proc_real(self):
        # Los read_* solo hacen open(); esto verifica el cableado nombre-de-archivo,
        # que es lo único que los parsers puros no pueden cubrir.
        proc = ProcFS('/proc')
        self.assertGreater(proc.read_stat_global()["cpu"]["idle"], 0)
        self.assertGreater(proc.read_meminfo()["MemTotal"], 0)
        self.assertGreaterEqual(proc.read_loadavg()["load_1m"], 0.0)
        self.assertGreater(proc.read_uptime()["uptime"], 0.0)
    #endregion