from dataclasses import dataclass, field

@dataclass
class FakeConfigItem:
    value: str

    def get(self):
        return self.value


@dataclass
class FakeConfig:
    ncrystal: FakeConfigItem

    def __iter__(self):
        from dataclasses import fields
        fieldnames = [f.name for f in fields(self)]
        return iter(fieldnames)

    def __setitem__(self, key, value):
        setattr(getattr(self, key), 'value', value)

    def __getitem__(self, item):
        return getattr(self, item)


def test_ncrystal_windows_flags():
    """
    Inside mccode.instr.instr the parsing of special @XXX@ flags raises an error
    for some Windows paths if their backslashes are not properly escaped.
    This test replicates `_replace_keywords` to use a fake configuration object with
    a path that previously caused an error in re.
    """
    from re import sub, findall
    from mccode_antlr.config.fallback import config_fallback
    config = FakeConfig(FakeConfigItem(" /IC:\\hosted\\NCrystal.lib\n"))

    flag = "@NCRYSTALFLAGS@"

    general_re = r'@(\w+)@'
    assert findall(general_re, flag)

    for replace in findall(general_re, flag):
        if replace.lower().endswith('flags'):
            print(f'{replace} in {flag}')
            replacement = config_fallback(config, replace.lower()[:-5])
            flag = sub(f'@{replace}@', replacement, flag)
        else:
            raise ValueError('Only *flags should be found')

    assert flag == config['ncrystal'].get()

