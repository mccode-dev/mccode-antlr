# from dataclasses import dataclass
from msgspec import Struct
from ..common import Expr


# @dataclass
class Jump(Struct):
    target: str
    relative_target: int
    iterate: bool
    condition: Expr
    absolute_target: int = -1

    @classmethod
    def from_dict(cls, args: dict):
        args['condition'] = Expr.from_dict(args['condition'])
        return cls(**args)

    def to_file(self, output, wrapper):
        # self.target is one of "PREVIOUS", "PREVIOUS_{i}, "MYSELF", "MYSELF_{i}, "NEXT",
        # or "{component instance identifier}"
        jump_name = self.target
        if '_' in jump_name and (jump_name.startswith('PREVIOUS') or jump_name.startswith('NEXT')):
            jump_name = jump_name.split('_')[0]
        if abs(self.relative_target) > 1:
            jump_name += f' ({abs(self.relative_target)})'
        when_iter = 'ITERATE' if self.iterate else 'WHEN'
        print(wrapper.line('JUMP', [jump_name, when_iter, str(self.condition)]), file=output)

    def __contains__(self, value):
        return value in self.condition
