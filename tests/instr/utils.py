from mccode_antlr import Flavor

def make_assembler(name: str, flavor: Flavor = Flavor.MCSTAS):
    from mccode_antlr.assembler import Assembler
    from mccode_antlr.reader.registry import default_registries
    return Assembler(name, registries=default_registries(flavor))


def parse_instr_string(instr_source: str):
    from mccode_antlr.loader import parse_mcstas_instr
    return parse_mcstas_instr(instr_source)