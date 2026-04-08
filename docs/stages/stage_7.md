# Stage 7 — Cinemática: triángulos de velocidad y paso mecánico

## Objetivo

Convertir los ajustes de paso aerodinámico (Δα_aero de Stage 6) en ajustes de paso mecánico reales, resolviendo los triángulos de velocidad en cada sección de la pala.

## Modelo físico

```
Velocidad axial:    V_ax = M · a   (a = 340 m/s velocidad del sonido)
Velocidad tangencial: U = ω · r   (ω = 2π · RPM/60,  r = radio de sección)
Ángulo de entrada:  φ = arctan(V_ax / U)

Ajuste de paso mecánico:
Δβ_mech = Δα_aero + Δφ

donde Δφ = φ(condición) − φ(crucero)
```

### Parámetros del motor

| Parámetro | Valor |
|---|---|
| RPM del fan | 3 000 |
| Radio raíz | 0.50 m |
| Radio mid-span | 1.00 m |
| Radio tip | 1.50 m |

### Por qué Δβ_mech >> Δα_aero

El ángulo de entrada φ cambia drásticamente entre condiciones (crucero M = 0.85 vs despegue M = 0.25), lo que provoca Δφ del orden de −20° a −30°. El ajuste mecánico real de la pala es por tanto mucho mayor que el ajuste aerodinámico, lo que justifica físicamente la necesidad del sistema VPF.

## Salidas

```
results/stage_7/
├── figures/
│   ├── kinematics_delta_comparison.png   # Δα_aero vs Δβ_mech
│   └── velocity_triangles_*.png
└── tables/
    └── kinematics_analysis.csv           # Triángulos completos por caso
```

## Código relevante

- `src/vfp_analysis/kinematics_analysis/core/services/kinematics_service.py`
- `src/vfp_analysis/kinematics_analysis/application/run_kinematics_stage.py`
- `config/engine_parameters.yaml` — RPM, radios, Mach por condición
