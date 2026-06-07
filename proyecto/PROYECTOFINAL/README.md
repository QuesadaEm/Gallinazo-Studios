# Motor de Persistencia e Indexación — Desarrollador A

Parte del *Sistema Distribuido de Consulta Geográfica de ASADAS de Costa Rica*.
Este componente es la **única fuente de verdad** de los datos: ingesta desde
ARESEP, archivo binario principal, índice por árbol binario de búsqueda,
actualización incremental y la API pública que consume el servidor (Dev B).

## Capas

| Capa | Paquete | Clases |
|------|---------|--------|
| Dominio | `src/modelo` | `Asada` |
| Ingesta | `src/ingesta` | `ClienteAresep`, `ActualizadorIncremental` |
| Persistencia | `src/persistencia` | `RepositorioBinario`, `NodoArbol`, `IndiceArbolBinario` |
| Aplicación (API) | `src/api` | `MotorConsulta` |

## Uso rápido

```python
from src.api.motor_consulta import MotorConsulta

motor = MotorConsulta(directorio_datos="data")
motor.iniciar()                      # descarga/sincroniza si está vacío

pos    = motor.buscar_por_id(50)     # posición física o None
asada  = motor.obtener_asada(50)     # objeto Asada o None
todas  = motor.obtener_todas()       # lista completa
cambio = motor.actualizar_datos()    # True si regeneró

# Desarrollo/pruebas sin conexión:
motor = MotorConsulta(directorio_datos="data", origen_local="tests/fixtures_asadas.json")
```

## Pruebas

```bash
python -m unittest discover -s tests -v
```

## Integración con el Desarrollador B

- El servidor consume **únicamente** `MotorConsulta`.
- La actualización puede disparar la reconstrucción del índice geográfico de B
  mediante el callback `al_regenerar(repositorio)` que recibe `MotorConsulta`.

## Uso

# Servidor con GUI (datos locales):
python -m src.main_servidor

# Servidor con datos reales de ARESEP:
python -m src.main_servidor --real

# Cliente remoto (GUI):
python -m src.main_cliente