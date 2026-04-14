import argparse
import os
import shutil #puedo usar execvp (busca el path)
import time


def parsear_comandos(tokens):
    comandos = []
    comando_actual = None
    path_actual = None
    args_actuales = []

    for token in tokens:
        exec_path = shutil.which(token)
        if exec_path is not None:
            if comando_actual is not None:
                comandos.append((path_actual, comando_actual, args_actuales))
            comando_actual = token
            path_actual = exec_path
            args_actuales = []
        else:
            if comando_actual is None:
                raise ValueError(
                    f"'{token}' no es un ejecutable válido y no hay comando previo para asociarlo como argumento"
                )
            args_actuales.append(token)

    if comando_actual is not None:
        comandos.append((path_actual, comando_actual, args_actuales))

    return comandos


parser = argparse.ArgumentParser(description="Ejemplo de argparse para procesos en paralelo")

#para recibir N argumentos posicionales, se usa nargs="+", que indica que se espera al menos un argumento
parser.add_argument("procesos", help="Números para procesar en paralelo", nargs="+")

#para obtener el valor 
args = parser.parse_args()

try:
    comandos = parsear_comandos(args.procesos)
except ValueError as e:
    parser.error(str(e))

pids = []
inicio = time.monotonic() # timestamp de inicio

for exec_path, comando, argumentos in comandos:
    pid = os.fork()
    if pid == 0:  # proceso hijo
        os.execv(exec_path, [comando] + argumentos)
    else:
        pids.append(pid)
        print(f"Lanzado: {comando} {' '.join(argumentos)} (pid={pid})")

for pid in pids:
    pid_hijo, status = os.waitpid(pid, 0)
    print(f"Proceso terminado: {pid_hijo} (status={status})")

fin = time.monotonic()
print(f"Tiempo total de ejecución: {fin - inicio:.3f} segundos")
        