from msgspec import Struct, field
from .instance import Instance

# @dataclass
class Group(Struct):
    name: str
    index: int
    ids: list[int] = field(default_factory=list)
    members: list[Instance] = field(default_factory=list)

    def add(self, id: int, inst: Instance):
        self.ids.append(id)
        self.members.append(inst)

    def is_leader(self, index: int):
        return len(self.ids) and self.ids[0] == index

    @property
    def first_id(self):
        return min(self.ids)

    @property
    def last_id(self):
        return max(self.ids)

    @property
    def first(self):
        fid = self.first_id
        return [m for i, m in zip(self.ids, self.members) if i == fid][0]

    @property
    def last(self):
        lid = self.last_id
        return [m for i, m in zip(self.ids, self.members) if i == lid][0]

    def copy(self):
        return Group(self.name, self.index, self.ids.copy(), self.members.copy())


class DependentGroup(Group):
    members: list[str] = field(default_factory=list)

    @classmethod
    def from_independent(cls, independent: Group):
        name = independent.name
        index = independent.index
        ids = [x for x in independent.ids]
        members = [x.name for x in independent.members]
        return cls(name, index, ids, members)

    @classmethod
    def from_dict(cls, args: dict):
        args['ids'] = [x for x in args['ids']]
        args['members'] = [x for x in args['members']]
        return cls(**args)

    def make_independent(self, instances: tuple[Instance, ...]):
        members = [next(i for i in instances if i.name == m) for m in self.members]
        return Group(name=self.name, index=self.index, ids=self.ids, members=members)