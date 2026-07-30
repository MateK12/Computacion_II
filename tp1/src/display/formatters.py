"""Funciones de formato para valores del sistema: uptime, memoria, timestamps, etc.
Reutilizables en varias vistas."""

from datetime import datetime


def format_uptime(seconds: int) -> str:
	"""Convierte segundos a formato legible: '5d 3h 42m 15s'.
	None -> None.
	"""
	if seconds is None:
		return None
	d, rem = divmod(int(seconds), 86400)
	h, rem = divmod(rem, 3600)
	m, s = divmod(rem, 60)
	parts = []
	if d:
		parts.append(f"{d}d")
	if h:
		parts.append(f"{h}h")
	if m:
		parts.append(f"{m}m")
	if s or not parts:
		parts.append(f"{s}s")
	return " ".join(parts)


def format_time_unix(timestamp: int) -> str:
	"""Convierte epoch unix a un string legible: '2026-07-27 10:30:42'.
	None -> None.
	"""
	if timestamp is None:
		return None
	return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def format_kb(kb: int) -> str:
	"""Convierte KB a unidades legibles: '1.5 GB', '256 MB', etc.
	None -> None.
	"""
	if kb is None:
		return None
	kb = float(kb)
	for unit in ("KB", "MB", "GB", "TB"):
		if abs(kb) < 1024:
			if 0 < kb < 10:
				return f"{kb:.1f} {unit}"
			else:
				return f"{int(kb)} {unit}"
		kb /= 1024
	return f"{kb:.1f} PB"


_KB_PER_UNIT = {"KB": 1, "MB": 1024, "GB": 1024**2, "TB": 1024**3, "PB": 1024**4}


def parse_kb(text: str) -> float:
	"""Inversa de format_kb: '1.5 GB' -> kB.	"""
	if not isinstance(text, str):
		return None
	try:
		num, unit = text.split()
		return float(num) * _KB_PER_UNIT[unit]
	except (ValueError, KeyError):
		return None


def format_proc_state(by_state: dict) -> str:
	"""Convierte dict de estados {R: 2, S: 38, ...} a 'R: 2  S: 38  ...'.
	Orden fijo: R, S, D, T, Z (solo los que tengan count > 0).
	None -> None.
	"""
	if not by_state:
		return None
	parts = []
	for state in ("R", "S", "D", "T", "Z"):
		count = by_state.get(state, 0)
		if count > 0:
			parts.append(f"{state}: {count}")
	return "  ".join(parts) if parts else None
