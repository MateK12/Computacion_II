"""Ritmo de los analizadores: dormir el intervalo en ticks cortos.

El intervalo llega como mp.Value('d') que main puede cambiar en caliente
(teclas +/-). Un time.sleep(intervalo) entero no se entera del cambio hasta
agotarse; dormir de a ticks releyendo el Value hace que el cambio se aplique
en <=1 tick. (El shutdown por bandera va a reusar este mismo patrón: un
analizador dormido también tiene que enterarse rápido de que hay que parar.)
"""

import time


def sleep_interval(interval, shutdown_event=None, tick=1.0):
	"""Duerme `interval.value` segundos, releyendo el Value cada `tick` como
	máximo. Si `shutdown_event` se setea, despierta inmediatamente.

	Retorna `True` si el evento de shutdown fue señalizado, `False` si el
	tiempo de intervalo se agotó normalmente.
	"""
	start = time.monotonic()
	while True:
		remaining = interval.value - (time.monotonic() - start)
		if remaining <= 0:
			return False
		wait_time = min(remaining, tick)
		if shutdown_event is not None:
			if shutdown_event.wait(wait_time):
				return True
		else:
			time.sleep(wait_time)
