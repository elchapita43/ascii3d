# ascii3d

Renderiza modelos 3D como ASCII art en la terminal, con cámara orbital interactiva y shading.

## Features

- **Formatos**: STL (binary + ASCII), OBJ
- **Point Splatting**: renderizado denso sin huecos
- **Lit Wireframe**: wireframe con shading por cara
- **Shading ASCII**: caracteres ` .:-=+*#%@` según iluminación
- **Cámara orbital**: objeto fijo, cámara gira alrededor
- **Controles WASD/flechas**: mover cámara
- **Auto-rotación horizontal**: cuando no hay input
- **Snap-back suave**: vuelve a horizontal después de 3 seg sin tocar
- **Decimación automática**: para modelos de alta densidad
- **Auto-centrado y escala**: el modelo se ajusta automáticamente
- **Sin dependencias**: Python puro + math

## Instalación

```bash
# Clonar
git clone https://github.com/elchapita43/ascii3d.git
cd ascii3d

# Symlink (opcional)
ln -sf $(pwd)/ascii3d ~/.local/bin/ascii3d
```

## Uso

```bash
# Modelos STL
ascii3d modelo.stl

# Modelos OBJ
ascii3d modelo.obj

# Formas built-in
ascii3d --shape sphere
ascii3d --shape cube
ascii3d --shape torus

# Opciones
ascii3d modelo.stl --speed 0.02        # Velocidad de rotación
ascii3d modelo.stl --wireframe         # Modo wireframe (OBJ)
ascii3d modelo.stl --solid             # Modo sólido (STL)
ascii3d modelo.stl --width 120         # Ancho fijo
ascii3d modelo.stl --height 50         # Alto fijo
ascii3d modelo.stl --fov 5.0           # Campo de visión
ascii3d modelo.stl --max-faces 3000    # Máximo de caras
```

## Controles

| Tecla | Acción |
|-------|--------|
| `W` / `↑` | Mover cámara arriba |
| `S` / `↓` | Mover cámara abajo |
| `A` / `←` | Mover cámara izquierda |
| `D` / `→` | Mover cámara derecha |
| `Q` / `ESC` | Salir |

**Comportamiento automático:**
- Al arrancar: auto-rotación horizontal
- Al tocar WASD: pausa auto-rotación, mueve cámara
- 3 seg sin tocar: snap-back suave a horizontal → reanuda rotación

## Estado en el HUD

El status bar muestra:
- `Yaw` / `Pitch`: ángulos de cámara
- `[ROTATING]`: auto-rotación activa
- `[CONTROL]`: usuario controlando cámara
- `[SNAP-BACK]`: corrigiendo a horizontal

## Ejemplos de modelos

Probá con modelos de [Thingiverse](https://thingiverse.com), [Printables](https://printables.com), o tu propia colección STL.

## Requisitos

- Python 3.10+
- Terminal con soporte ANSI (macOS Terminal, iTerm2, Ghostty, kitty, etc.)

## Licencia

MIT
