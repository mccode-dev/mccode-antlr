# Instr API

`Instr` is the intermediate representation of a complete instrument. Build one
via [`Assembler`](assembler.md) or parse one from a `.instr` file.

## Reading instruments

```python
from mccode_antlr.reader import read_mcstas_instr, read_mcxtrace_instr

instr = read_mcstas_instr("my_instrument.instr")
```

## Writing instruments

```python
instr.to_file("output.instr")
text = instr.to_string()
```

## Jupyter display

In a Jupyter notebook, placing `instr` on the last line of a cell renders an
interactive collapsible HTML view of the instrument.

## Reference

::: mccode_antlr.instr.Instr

### Instance

::: mccode_antlr.instr.instance.Instance
