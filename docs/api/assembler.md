# Assembler API

The `Assembler` is the primary entry point for building McCode instruments
programmatically in Python.

## Usage

```python
from mccode_antlr import Flavor
from mccode_antlr.assembler import Assembler

a = Assembler("MyInstrument", flavor=Flavor.MCSTAS)
a.parameter("double E_i = 5.0")

src = a.component("Source", "Source_simple")
src.set_parameter("E0", "E_i")
src.AT([0, 0, 0], "ABSOLUTE")

instr = a.instrument()
```

## Reference

::: mccode_antlr.assembler.Assembler
