# Stage 5 — Generación de figuras de publicación

## Objetivo

Producir todas las figuras de alta resolución (300 DPI) para la tesis, con estilo académico uniforme (fuente serif, grid punteada, sin bordes superior/derecho).

## Figuras generadas

### Figuras base (polares Stage 2)

| Archivo | Descripción |
|---|---|
| `efficiency_{cond}_{sect}.png` | CL/CD vs α con α_opt marcado — una por caso (12 total) |
| `efficiency_by_section_{cond}.png` | Root, mid-span y tip solapados — uno por condición (4 total) |
| `alpha_opt_vs_condition.png` | Diagrama de barras: α_opt por condición y sección — figura central |

### Figura A — Comparación de secciones con polares corregidas

`section_polar_comparison_{cond}.png` (4 archivos)

Dos paneles para cada condición de vuelo:
- Izquierdo: polar de eficiencia CL/CD_corr vs α, root + mid + tip solapados
- Derecho: polar de sustentación CL_corr vs α, root + mid + tip solapados
- **★** marca el segundo pico (punto operativo real) en cada curva

### Figura B — Penalización por paso fijo de crucero

`cruise_penalty_{cond}.png` (3 archivos: takeoff, climb, descent)

**Figura central de la tesis.** Para cada condición no-crucero muestra:
- Las 3 curvas de eficiencia (Re distinto por sección, indicado en leyenda)
- **★ verde** en cada curva = α_opt óptimo (operación con VPF)
- **Línea roja discontinua** = α_design de crucero (operación con paso fijo)
- **Anotación** sobre mid-span: porcentaje de pérdida de eficiencia por paso fijo

## Paleta de colores

| Sección | Color |
|---|---|
| Root | `#2166AC` (azul) |
| Mid-span | `#D6604D` (rojo-naranja) |
| Tip | `#4DAC26` (verde) |

| Condición | Color |
|---|---|
| Takeoff | `#E31A1C` (rojo) |
| Climb | `#FF7F00` (naranja) |
| Cruise | `#1F78B4` (azul) |
| Descent | `#6A3D9A` (morado) |

## Código relevante

- `src/vfp_analysis/postprocessing/figure_generator.py` — todas las funciones de figura
- `src/vfp_analysis/postprocessing/aerodynamics_utils.py` — utilidades compartidas
