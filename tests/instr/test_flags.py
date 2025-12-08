from dataclasses import dataclass

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
    Inside mccode_antlr.instr.instr the parsing of special @XXX@ flags raises an error
    for some Windows paths if their backslashes are not properly escaped.
    This test replicates `_replace_keywords` to use a fake configuration object with
    a path that previously caused an error in re.
    """
    from re import sub, findall, error
    from mccode_antlr.config.fallback import regex_sanitized_config_fallback
    config = FakeConfig(FakeConfigItem(" /IC:\\hosted\\NCrystal.lib\n"))

    flag = "@NCRYSTALFLAGS@"

    general_re = r'@(\w+)@'
    assert findall(general_re, flag)

    for replace in findall(general_re, flag):
        if replace.lower().endswith('flags'):
            replacement = regex_sanitized_config_fallback(config, replace.lower()[:-5])
            # This should not raise an error after the fix
            flag = sub(f'@{replace}@', replacement, flag)
        else:
            raise ValueError('Only *flags should be found')

    def no_backslashes(s):
        return s.replace(r'\\', '')

    assert no_backslashes(flag) == no_backslashes(config['ncrystal'].get())

