# Claude Code Prompt — Refactoring VPF Pipeline

> Prompt de refactoring completo basado en el análisis del `project_map.md`.
> Ejecutar con `claude` en la raíz del proyecto (`vpf/`).
> Leer **todos** los ficheros afectados antes de modificar nada.

---

## INSTRUCCIONES GENERALES PARA CLAUDE CODE

Antes de tocar cualquier fichero:
1. Lee el fichero completo con `Read`
2. Identifica exactamente qué líneas están afectadas
3. Aplica los cambios con `Edit` de forma quirúrgica
4. Después de cada bloque de cambios, ejecuta `python run_analysis.py --dry-run` (o los tests relevantes) para confirmar que no hay regresiones
5. No reescribas un fichero entero si solo cambian 10 líneas

---

## BLOQUE 1 — ESTRUCTURA DEL PROYECTO

### 1.1 Renombrar el paquete interno (typo crítico)

El directorio del paquete se llama `vfp_analysis` pero el proyecto se llama **VPF**.
Esto es una inconsistencia de nomenclatura que genera confusión en imports.

**Acción:** Renombrar `src/vfp_analysis/` → `src/vpf_analysis/` y actualizar **todos** los imports en el proyecto.

```bash
# Verificar todos los imports afectados antes de renombrar:
grep -r "vfp_analysis" vpf/ --include="*.py" -l
```

Ficheros que con certeza importan de `vfp_analysis`:
- `run_analysis.py`
- todos los `run_*.py` de cada stage
- `tests/conftest.py` y todos los `test_*.py`

Después del rename, ejecutar:
```bash
python -c "import vpf_analysis" && echo "OK"
pytest tests/ -x -q
```

### 1.2 Eliminar `xfoil_runner.py` huérfano de la raíz del paquete

`src/vpf_analysis/xfoil_runner.py` es la implementación original de XFOIL.
Fue reemplazado por `adapters/xfoil/xfoil_runner_adapter.py` (arquitectura de
puertos y adaptadores), pero el fichero original nunca se borró.

**Acción:**
1. Confirmar que ningún fichero importa de `xfoil_runner.py` directamente:
   ```bash
   grep -r "from.*xfoil_runner import\|import.*xfoil_runner" vpf/ --include="*.py"
   ```
2. Si el grep devuelve 0 resultados → `rm src/vpf_analysis/xfoil_runner.py`
3. Si hay imports residuales → redirigirlos a `adapters/xfoil/xfoil_runner_adapter.py` primero

### 1.3 Consolidar `settings.py` y `config_loader.py`

`settings.py` (443 líneas) y `config_loader.py` (206 líneas) se solapan en responsabilidades:
- `settings.py` tiene dataclasses de configuración (`SimulationSettings`, etc.)
- `config_loader.py` también crea objetos de configuración desde YAML

**Acción:** Separar responsabilidades de forma limpia:
- `settings.py` → **solo constantes y rutas** (`ROOT_DIR`, `RESULTS_DIR`, `get_stage_dir()`, `XFOIL_EXECUTABLE`, etc.)
- `config_loader.py` → **toda la lógica de lectura de YAML** + instanciación de dataclasses de configuración

Mover las dataclasses de configuración (`SimulationSettings`, `CompressibilitySettings`, `PitchKinematicsSettings`, `PipelineSettings`) a un nuevo fichero:
```
src/vpf_analysis/config/domain.py   ← dataclasses de configuración
```

Y actualizar imports en todos los ficheros que usen estas clases.

---

## BLOQUE 2 — CONSISTENCIA DEL PROYECTO

### 2.1 Unificar convención de nombres de módulos por stage

La estructura interna es inconsistente entre stages:

| Stage | Tiene `application/` | Tiene `core/domain/` | Tiene `adapters/` |
|-------|---------------------|----------------------|-------------------|
| 3     | ✗                   | ✗                    | ✗                 |
| 4     | ✗                   | ✗                    | ✗                 |
| 5     | ✓                   | ✓                    | ✓                 |
| 6     | ✓                   | ✓                    | ✓                 |
| 7     | ✓                   | ✓                    | ✗                 |

Stages 3 y 4 son los únicos que no siguen la arquitectura de puertos/adaptadores.
**No refactorizarlos a esa arquitectura** (coste alto, beneficio bajo).
En cambio, añadir un comentario de cabecera en sus ficheros principales explicando
que son módulos de procesamiento directo sin capa de aplicación, para que sea
intencional y documentado:

```python
# stage3_compressibility_correction/correction_service.py
# NOTE: Este módulo no sigue la arquitectura ports/adapters de stages 5-7.
# Es un módulo de transformación directa: recibe polares y devuelve polares corregidos.
# No hay adaptadores de filesystem porque la E/S la gestiona run_analysis.py.
```

### 2.2 Estandarizar nombres de columnas de polares en todo el pipeline

Verificar que todos los CSVs de polares usan exactamente la misma convención.
El fichero `aerodynamics_utils.py` tiene `resolve_efficiency_column()` que busca
en una lista de 5 nombres posibles (`ld_corrected`, `CL_CD_corrected`, `ld_kt`,
`ld`, `CL_CD`). Esto es un síntoma de inconsistencia histórica.

**Acción:**
1. Auditar los headers de los CSVs generados por stages 2 y 3:
   ```bash
   head -1 results/stage2/polars/*.csv
   head -1 results/stage3/**/*.csv
   ```
2. Elegir UNA convención: **`ld`** para Cl/Cd sin corregir, **`ld_corrected`** para corregido
3. Actualizar los writers de Stage 2 (`pitch_map.py`) y Stage 3 (`correction_service.py`) para escribir siempre esos nombres
4. Simplificar `resolve_efficiency_column()` a:
   ```python
   def resolve_efficiency_column(df: pd.DataFrame) -> str:
       for col in ("ld_corrected", "ld"):
           if col in df.columns:
               return col
       raise KeyError(f"No efficiency column found. Available: {list(df.columns)}")
   ```

### 2.3 Consistencia en el flujo de datos Stage 6 → Stage 7

El `project_map.md` indica que Stage 6 (`stage5/tables/blade_twist_design.csv`)
**no es usado** por Stage 7 a pesar de que el diagrama muestra una flecha.
Stage 7 solo usa Stage 6 para logging.

**Acción:**
1. Leer `run_sfc_analysis.py` y confirmar si `stage6` se carga o no
2. Si no se carga → eliminar la referencia en el diagrama del `project_map.md`
   y en el contrato `Stage7Result`
3. Si sí se carga → documentar exactamente qué dato de Stage 6 entra en Stage 7
   y añadirlo como campo en `Stage7Result`

---

## BLOQUE 3 — REDUCCIÓN DE GRÁFICAS

### 3.1 Auditoría de figuras actuales

Antes de eliminar nada, listar todas las figuras generadas:
```bash
find results/ -name "*.png" | sort
# También buscar en el código todas las llamadas a savefig:
grep -rn "savefig\|plt.save" src/ --include="*.py"
```

### 3.2 Stage 4 — Reducir de N figuras a 3 figuras esenciales

Leer `stage4_performance_metrics/plots.py` y `narrative_figures.py`.
Mantener **solo estas 3 figuras**:

| Figura | Qué muestra | Por qué es esencial |
|--------|-------------|---------------------|
| `polar_efficiency.png` | Cl/Cd vs α para todas las condiciones y secciones | Figura central del análisis aerodinámico |
| `lift_drag_curves.png` | Cl vs α y Cd vs α superpuestos | Validación del polar XFOIL |
| `compressibility_comparison.png` | Cl/Cd antes/después de corrección de compresibilidad | Justifica Stage 3 |

Eliminar el código de cualquier otra figura en Stage 4 (gráficas de Cl solo,
gráficas de Cd solo, figuras duplicadas de Stage 3, etc.).

### 3.3 Stage 7 — Reducir de 7 PNG a 3 figuras esenciales

`run_sfc_analysis.py` genera actualmente 7 PNG. Mantener **solo**:

| Figura | Qué muestra |
|--------|-------------|
| `sfc_improvement_by_condition.png` | Reducción de SFC por condición de vuelo (takeoff/cruise/descent) |
| `fuel_saving_vs_clcd.png` | Ahorro de combustible vs Cl/Cd (barrido paramétrico GE9X) |
| `sfc_sensitivity_k_throttle.png` | Sensibilidad del modelo al parámetro k_throttle |

Las otras 4 figuras (desglose por sección, figuras del ciclo termodinámico,
figuras de barrido τ redundantes con la tabla) → **eliminar código completo**,
no solo comentar.

### 3.4 Procedure de eliminación (aplicar a cada figura a eliminar)

Para cada figura a eliminar en cada `plots.py` o `run_*.py`:
1. Localizar la función que la genera
2. Verificar que no es llamada desde ningún otro sitio: `grep -rn "nombre_funcion" src/`
3. Eliminar la función completa
4. Eliminar la llamada en el orquestador (`run_*.py`)
5. Eliminar el nombre del fichero de cualquier lista de outputs esperados

---

## BLOQUE 4 — LIMPIEZA DE CÓDIGO RESIDUAL

### 4.1 Eliminar imports no usados en todo el proyecto

```bash
# Detectar imports no usados (requiere ruff o flake8):
pip install ruff -q
ruff check src/ --select F401 --fix
```

Prestar atención especial a:
- `run_analysis.py` — 804 líneas, muy probable que tenga imports de módulos
  de stages que se refactorizaron
- `stage7_sfc_analysis/application/run_sfc_analysis.py` — 725 líneas,
  módulo que creció orgánicamente

### 4.2 Eliminar variables asignadas y nunca leídas

```bash
ruff check src/ --select F841 --fix
```

### 4.3 Limpiar `run_analysis.py` de lógica de plotting interna

`run_analysis.py` tiene 804 líneas. Un orquestador no debe contener lógica
de plotting. Verificar si hay bloques `plt.*` o `fig, ax = plt.subplots()`
dentro de `run_analysis.py`. Si los hay, moverlos al módulo `plots.py` del
stage correspondiente y reemplazarlos por una llamada a función.

### 4.4 Eliminar `ge9x_analysis.py` como módulo separado e integrarlo

`stage7_sfc_analysis/engine/ge9x_analysis.py` (247 líneas) orquesta el análisis
GE9X con lógica mezclada: carga datos, ejecuta ciclo, genera figuras, escribe
tablas. Esto duplica responsabilidades con `run_sfc_analysis.py`.

**Acción:**
- Mover la lógica de análisis puro (barrido Cl/Cd, extracción de α_opt) a
  `sfc_model.py` como funciones auxiliares
- Mover la validación del ciclo termodinámico a `turbofan_cycle.py`
- Eliminar `ge9x_analysis.py` como fichero
- Las llamadas a `run_ge9x_analysis()` en `run_sfc_analysis.py` pasan a llamar
  directamente a las funciones de `sfc_model.py` y `turbofan_cycle.py`

---

## BLOQUE 5 — CUATRO MEJORAS ADICIONALES

### 5.1 Añadir tipos a todas las firmas de funciones públicas

El código carece de anotaciones de tipos en muchas funciones, especialmente
en los stages más antiguos (3 y 4). Esto dificulta el mantenimiento.

```bash
# Detectar funciones sin anotación de retorno:
ruff check src/ --select ANN201
```

Prioridad alta (funciones de interfaz entre stages):
```python
# ANTES (stage3/correction_service.py):
def apply_corrections(polar_df, mach, method):
    ...

# DESPUÉS:
def apply_corrections(
    polar_df: pd.DataFrame,
    mach: float,
    method: str,
) -> pd.DataFrame:
    ...
```

Aplicar al menos en:
- Todas las funciones en `aerodynamics_utils.py`
- Todas las funciones en `sfc_model.py`, `turbofan_cycle.py`, `engine_data.py`
- Las firmas públicas de `correction_service.py`
- Los métodos `validate()` de todos los contratos en `contracts.py`

### 5.2 Centralizar la lógica de escritura de tablas LaTeX

Actualmente Stage 7 escribe directamente un fichero `.tex` desde
`ge9x_analysis.py` usando `df.to_latex()`. Si en el futuro se quieren más
tablas LaTeX, cada módulo replicará ese código.

**Acción:** Crear `src/vpf_analysis/postprocessing/latex_exporter.py`:

```python
# latex_exporter.py
from pathlib import Path
import pandas as pd

def export_table(
    df: pd.DataFrame,
    path: Path,
    caption: str,
    label: str,
    float_format: str = "%.4f",
    column_format: str | None = None,
) -> None:
    """Exporta un DataFrame como tabla LaTeX con booktabs."""
    n_cols = len(df.columns)
    col_fmt = column_format or ("c" * n_cols)
    latex = df.to_latex(
        index=False,
        float_format=float_format,
        caption=caption,
        label=label,
        column_format=col_fmt,
        escape=False,
        booktabs=True,
    )
    path.write_text(latex, encoding="utf-8")
```

Reemplazar todas las llamadas directas a `to_latex()` con esta función.

### 5.3 Añadir `--dry-run` y `--stages` flags a `run_analysis.py`

Actualmente el pipeline siempre ejecuta los 8 pasos completos. Durante
desarrollo esto es lento (XFOIL en Stage 2 puede tardar varios minutos).

**Acción:** Añadir argparse al inicio de `run_analysis.py`:

```python
import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VPF Pipeline")
    parser.add_argument(
        "--stages",
        nargs="+",
        type=int,
        choices=range(1, 9),
        metavar="N",
        help="Ejecutar solo los stages indicados (ej: --stages 4 5 7)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validar configuración sin ejecutar ningún stage",
    )
    return parser.parse_args()
```

Modificar el bucle principal para saltarse los stages no incluidos en `--stages`.
Si `--dry-run`, solo cargar configs y validar que los YAMLs son correctos.

### 5.4 Ampliar cobertura de tests para Stage 7

Los tests existentes cubren bien stages 1-4 pero Stage 7 (el más nuevo y
complejo) no tiene tests unitarios propios. El fichero `test_efficiency.py`
cubre `aerodynamics_utils.py` pero no el modelo de motor.

**Acción:** Crear `tests/test_sfc_model.py`:

```python
# tests/test_sfc_model.py
import pytest
from vpf_analysis.stage7_sfc_analysis.engine.sfc_model import compute_sfc_improvement
from vpf_analysis.stage7_sfc_analysis.engine.engine_data import sfc_lbh_to_si, GE9X_PARAMS

SFC_GE9X_SI = sfc_lbh_to_si(GE9X_PARAMS["SFC_ref_cruise"])


def test_no_improvement_when_clcd_equal():
    """Si Cl/Cd no cambia, el ahorro de combustible debe ser 0."""
    result = compute_sfc_improvement(100, 100, SFC_GE9X_SI)
    assert result["fuel_saving_pct"] == pytest.approx(0.0, abs=1e-6)


def test_improvement_direction():
    """Aumentar Cl/Cd debe reducir consumo de combustible."""
    result = compute_sfc_improvement(100, 120, SFC_GE9X_SI)
    assert result["fuel_saving_pct"] > 0


def test_improvement_magnitude_reasonable():
    """Cl/Cd 100→120 debe dar entre 10% y 25% de ahorro (rango físico razonable)."""
    result = compute_sfc_improvement(100, 120, SFC_GE9X_SI)
    assert 10 < result["fuel_saving_pct"] < 25


def test_worse_clcd_increases_consumption():
    """Si Cl/Cd empeora, el consumo debe aumentar."""
    result = compute_sfc_improvement(100, 80, SFC_GE9X_SI)
    assert result["fuel_saving_pct"] < 0


def test_k_throttle_sensitivity():
    """Mayor k_throttle → menor ahorro (motor penaliza más el throttle parcial)."""
    r_low  = compute_sfc_improvement(100, 120, SFC_GE9X_SI, k_throttle=0.05)
    r_high = compute_sfc_improvement(100, 120, SFC_GE9X_SI, k_throttle=0.15)
    assert r_low["fuel_saving_pct"] > r_high["fuel_saving_pct"]


def test_turbofan_cycle_converges_to_ge9x():
    """El ciclo termodinámico debe converger a ≈0.49 lb/lbf·h ± 5%."""
    from vpf_analysis.stage7_sfc_analysis.engine.turbofan_cycle import compute_turbofan_sfc
    result = compute_turbofan_sfc(GE9X_PARAMS, phase="cruise", FPR=1.5)
    from vpf_analysis.stage7_sfc_analysis.engine.engine_data import sfc_si_to_lbh
    sfc_lbh = sfc_si_to_lbh(result["SFC"])
    assert abs(sfc_lbh - 0.49) / 0.49 < 0.05, f"SFC = {sfc_lbh:.4f}, expected ≈ 0.49"
```

Ejecutar con:
```bash
pytest tests/test_sfc_model.py -v
```

---

## ORDEN DE EJECUCIÓN RECOMENDADO

Ejecutar los bloques en este orden para minimizar conflictos:

```
1. BLOQUE 4.1 y 4.2 → limpiar imports/variables (sin cambios de lógica, bajo riesgo)
2. BLOQUE 1.1       → renombrar paquete (requiere actualizar todos los imports)
3. BLOQUE 2.2       → estandarizar columnas de polares (afecta al core de datos)
4. BLOQUE 1.2       → eliminar xfoil_runner.py huérfano
5. BLOQUE 3         → reducir gráficas (eliminar código de plotting)
6. BLOQUE 4.3/4.4   → limpiar run_analysis.py y ge9x_analysis.py
7. BLOQUE 1.3       → separar settings.py y config_loader.py
8. BLOQUE 2.1       → añadir comentarios de arquitectura
9. BLOQUE 2.3       → clarificar flujo Stage 6 → Stage 7
10. BLOQUE 5.1      → añadir tipos
11. BLOQUE 5.2      → centralizar exportación LaTeX
12. BLOQUE 5.3      → añadir flags CLI
13. BLOQUE 5.4      → crear tests Stage 7
```

Tras cada bloque: `pytest tests/ -x -q` para confirmar que no hay regresiones.

---

## VALIDACIÓN FINAL

Al terminar todos los bloques, verificar:

```bash
# 1. Tests pasan
pytest tests/ -v

# 2. Sin imports no usados ni variables muertas
ruff check src/ --select F401,F841

# 3. Pipeline completo ejecuta sin errores
python run_analysis.py --dry-run
python run_analysis.py --stages 4 7

# 4. Número de figuras generadas es el esperado (6 total: 3 Stage4 + 3 Stage7)
find results/ -name "*.png" | wc -l
```

---

*Prompt generado el 2026-04-25 a partir del análisis de `docs/project_map.md`.*
