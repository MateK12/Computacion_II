# Dudas

Archivo de honestidad intelectual: dudas que me quedaron sin resolver del
todo durante el desarrollo del TP.

---

## Codificación de varias señales en un solo hexadecimal (`SigBlk`/`SigIgn`/`SigCgt`)

Los campos `SigBlk`, `SigIgn` y `SigCgt` de `/proc/<pid>/status` aparecen
como un número hexadecimal (ej. `SigBlk: 0000000000010002`). Entiendo que
es un `sigset_t` (máscara de 64 bits) y que representa un **conjunto** de
señales, no una sola.

**Lo que todavía no me termina de cerrar:** cómo se lee que un mismo número
codifique *varias* señales a la vez. La idea de que cada bit encendido
corresponde a la señal `bit + 1` (bit 1 → SIGINT, bit 16 → SIGCHLD) la
sigo en el ejemplo, pero me cuesta manipularlo con soltura y quiero
afianzar la decodificación con máscaras de bits (`mask & (1 << i)`).

---
