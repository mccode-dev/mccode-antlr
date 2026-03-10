# Display geometry

The `mccode_antlr.display` submodule parses a component's `MCDISPLAY` section
into a symbolic Python geometry model backed by [`Expr`](expression.md).  The
geometry can be evaluated at any parameter values and rendered in 3-D — without
compiling the instrument.

## Quick start

```python
from mccode_antlr.loader import load_mcstas_instr
from mccode_antlr.display import InstrumentDisplay
from mccode_antlr.display.render.matplotlib import plot_geometry
import matplotlib.pyplot as plt

instr = load_mcstas_instr('my_instrument.instr')
disp  = InstrumentDisplay(instr)
polys = disp.to_polylines({'E_i': 5.0})   # dict[name → list[np.ndarray]]

fig, ax = plot_geometry(polys)
plt.show()
```

Single-component use:

```python
from mccode_antlr.display import ComponentDisplay

cd   = ComponentDisplay(comp)
pls  = cd.to_polylines({'xwidth': 0.05, 'yheight': 0.1})
```

## Architecture

```
Comp.display (tuple[RawC])
      │
      ▼  parse_display_source()  ←  DisplayVisitor wraps C99 CParser
      │
  list[Primitive]   ← every argument is an Expr
      │
      ├──  ComponentDisplay.to_polylines(params) → list[np.ndarray]
      │
  InstrumentDisplay.to_polylines(params, global_frame=True)
  (applies Orient: Rotation × pts + translation, all Expr-backed)
      │
  dict[comp_name → list[np.ndarray (N,3)]]
      │
      ├──▶  render/matplotlib.py   (zero new hard deps)
      └──▶  render/threejs.py      (soft-import pythreejs / K3D)
```

The parsing is done by `DisplayVisitor`, a subclass of the existing C99
`CVisitor` ANTLR visitor.  It handles:

* **Simple calls** — `circle("xy", 0, 0, 0, r);`
* **Math in arguments** — `multiline(5, -xw/2, -yh/2, 0, ...);`
* **Local variable declarations** — `double t = height/2; line(0,0,-t, 0,0,t);`
* **Conditionals** — `if (show_guide) { rectangle(...); }` → `ConditionalBlock`
* **Loops** — `for (int i = ...) { ... }` → `LoopBlock` placeholder

## API reference

### `parse_display_source`

::: mccode_antlr.display.visitor.parse_display_source

### `ComponentDisplay`

::: mccode_antlr.display.component_display.ComponentDisplay

### `InstrumentDisplay`

::: mccode_antlr.display.instrument_display.InstrumentDisplay

## Geometry primitives

All non-string arguments are `Expr` objects and are resolved lazily at
`.to_polylines(params)` time.

| Primitive | C call | Polylines |
|-----------|--------|-----------|
| `Line` | `line(x1,y1,z1, x2,y2,z2)` | 1 segment |
| `DashedLine` | `dashed_line(x1,y1,z1, x2,y2,z2, n)` | n segments |
| `Multiline` | `multiline(count, x1,y1,z1,...)` | 1 open polyline |
| `Circle` | `circle(plane, cx,cy,cz, r)` | 1 closed polyline (24 pts) |
| `Rectangle` | `rectangle(plane, cx,cy,cz, w,h)` | 1 closed rect (5 pts) |
| `Box` | `box(cx,cy,cz, w,h,d)` | 12 edges |
| `Sphere` | `sphere(cx,cy,cz, r)` | 3 great circles |
| `Cylinder` | `cylinder(cx,cy,cz, r,h, nx,ny,nz)` | 2 end caps + 4 lines |
| `Cone` | `cone(cx,cy,cz, r,h, nx,ny,nz)` | tapered circles + 4 lines |
| `Magnify` | `magnify(scale)` | metadata only |
| `ConditionalBlock` | `if (cond) { ... }` | filtered at evaluate-time |
| `LoopBlock` | `for/while (...)` | unrolled at evaluate-time |

::: mccode_antlr.display.primitives

## Renderers

### matplotlib (zero new dependencies)

::: mccode_antlr.display.render.matplotlib.plot_geometry

### WebGL via pythreejs / K3D (optional)

::: mccode_antlr.display.render.threejs.show_geometry
