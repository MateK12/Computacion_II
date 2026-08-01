"""Tests del módulo de manejo de señales (self-pipe pattern)."""

import os
import signal
import unittest

from src.senales import (
    block_signals_in_child,
    read_signal,
    setup_signal_handlers,
)


class TestReadSignal(unittest.TestCase):
    def test_decodifica_cada_byte(self):
        """Cada byte mapea a la señal correcta."""
        casos = {
            b"i": signal.SIGINT,
            b"t": signal.SIGTERM,
            b"h": signal.SIGHUP,
            b"1": signal.SIGUSR1,
            b"2": signal.SIGUSR2,
        }
        for byte, esperado in casos.items():
            with self.subTest(byte=byte):
                r, w = os.pipe()
                os.write(w, byte)
                result = read_signal(r)
                os.close(r)
                os.close(w)
                self.assertEqual(result, esperado)

    def test_byte_desconocido_devuelve_none(self):
        r, w = os.pipe()
        os.write(w, b"x")
        result = read_signal(r)
        os.close(r)
        os.close(w)
        self.assertIsNone(result)


class TestBlockSignalsInChild(unittest.TestCase):
    def test_restaura_sigint_y_sigterm_a_default(self):
        """Después de block_signals_in_child, ambas señales vuelven a SIG_DFL."""
        # Guardar estado previo para restaurar al final
        prev_int = signal.getsignal(signal.SIGINT)
        prev_term = signal.getsignal(signal.SIGTERM)

        try:
            # Ponemos un handler dummy para que no esté en DFL
            dummy = lambda s, f: None
            signal.signal(signal.SIGINT, dummy)
            signal.signal(signal.SIGTERM, dummy)

            block_signals_in_child()

            self.assertEqual(signal.getsignal(signal.SIGINT), signal.SIG_DFL)
            self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_DFL)
        finally:
            signal.signal(signal.SIGINT, prev_int)
            signal.signal(signal.SIGTERM, prev_term)


class TestSetupSignalHandlers(unittest.TestCase):
    def test_registra_handlers_para_las_5_señales(self):
        """setup_signal_handlers pone un callable (no SIG_DFL) en cada señal."""
        r, w = os.pipe()
        prev = {sig: signal.getsignal(sig) for sig in (
            signal.SIGINT, signal.SIGTERM, signal.SIGHUP,
            signal.SIGUSR1, signal.SIGUSR2,
        )}

        try:
            setup_signal_handlers(w)
            for sig in prev:
                handler = signal.getsignal(sig)
                self.assertTrue(callable(handler), f"{sig} no tiene handler callable")
        finally:
            for sig, h in prev.items():
                signal.signal(sig, h)
            os.close(r)
            os.close(w)

    def test_self_pipe_end_to_end(self):
        """Enviamos SIGUSR1 a nosotros mismos y leemos el byte del pipe."""
        r, w = os.pipe()
        prev = {sig: signal.getsignal(sig) for sig in (
            signal.SIGINT, signal.SIGTERM, signal.SIGHUP,
            signal.SIGUSR1, signal.SIGUSR2,
        )}

        try:
            setup_signal_handlers(w)
            os.kill(os.getpid(), signal.SIGUSR1)
            sig = read_signal(r)
            self.assertEqual(sig, signal.SIGUSR1)
        finally:
            for sig, h in prev.items():
                signal.signal(sig, h)
            os.close(r)
            os.close(w)


if __name__ == "__main__":
    unittest.main()
