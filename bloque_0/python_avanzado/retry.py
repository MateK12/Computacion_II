from functools import wraps
import time


def retry(retries=3, delay=1, exceptions=None):
    """Decorator parametrizable para reintentar la ejecución de una función."""

    handled_exceptions = tuple(exceptions or (Exception,))

    def decorator(func):
        @wraps(func) #esto permite que mas abajo pueda usar func.__name__
        def wrapper(*args, **kwargs):
            tries = 0
            while tries < retries:
                try:
                    return func(*args, **kwargs)
                except handled_exceptions as error:
                    tries += 1
                    if tries == retries:
                        print(f"{func.__name__} falló después de {retries} intentos")
                        raise error
                    print(f"Error: {error}. Reintentando ({tries}/{retries})...")
                    time.sleep(delay)

        return wrapper

    return decorator




@retry(retries=5, delay=2, exceptions=(ValueError,))
def fails():
    """Función de ejemplo que va a fallar."""
    raise ValueError("¡Algo salió mal!")


fails()