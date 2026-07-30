"""Ritmo de los analizadores: dormir el intervalo en ticks cortos.

El intervalo llega como mp.Value('d') que main puede cambiar en caliente
(teclas +/-). Un time.sleep(intervalo) entero no se entera del cambio hasta
agotarse; dormir de a ticks releyendo el Value hace que el cambio se aplique
en <=1 tick. (El shutdown por bandera va a reusar este mismo patrón: un
analizador dormido también tiene que enterarse rápido de que hay que parar.)
"""

import time


def sleep_interval(interval, tick=1.0):
	"""Duerme `interval.value` segundos, releyendo el Value cada `tick` como
	máximo. El objetivo puede cambiar bajo nuestros pies: se compara el tiempo
	ya dormido contra el valor ACTUAL, así achicar el intervalo despierta antes.
	"""
	start = time.monotonic()
	while True:
		remaining = interval.value - (time.monotonic() - start)
		if remaining <= 0:
			return
		time.sleep(min(remaining, tick))
