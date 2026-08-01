"""Manejo de señales del monitor: self-pipe + handlers async-signal-safe.

El patrón self-pipe evita hacer cualquier cosa compleja dentro del handler
de señal. Cada handler solo escribe un byte identificador en el extremo de
escritura del pipe; el loop principal de main.py lee del extremo de lectura
y decide qué hacer.

Los hijos (analizadores, collector, display) ignoran SIGINT/SIGTERM para que
solo el padre orqueste el shutdown limpio.
"""

import os
import signal

_SIGNAL_BYTES = {
    signal.SIGINT: b"i",
    signal.SIGTERM: b"t",
    signal.SIGHUP: b"h",
    signal.SIGUSR1: b"1",
    signal.SIGUSR2: b"2",
}

_BYTE_TO_SIGNAL = {byte: sig for sig, byte in _SIGNAL_BYTES.items()}


def _make_handler(write_fd, byte):
    """Factory de handlers: el closure captura write_fd y byte."""

    def handler(signum, frame):
        # write(2) es async-signal-safe en POSIX. os.write en CPython
        # termina llamando a write(2) sin tomar locks del intérprete.
        os.write(write_fd, byte)

    return handler


def setup_signal_handlers(write_fd):
    """Registra los handlers de self-pipe para SIGINT, SIGTERM, SIGHUP,
    SIGUSR1 y SIGUSR2 en el proceso actual.
    """
    for sig, byte in _SIGNAL_BYTES.items():
        signal.signal(sig, _make_handler(write_fd, byte))


def block_signals_in_child():
    """Para llamar inmediatamente después del fork en cada hijo.
    Restaura SIGINT y SIGTERM a su comportamiento por defecto, evitando
    que los hijos hereden los handlers del padre y compitan en el shutdown.
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)


def read_signal(read_fd):
    """Lee un byte del self-pipe y devuelve la señal correspondiente
    (objeto signal.Signals) o None si el byte no es reconocido.
    """
    byte = os.read(read_fd, 1)
    return _BYTE_TO_SIGNAL.get(byte)
