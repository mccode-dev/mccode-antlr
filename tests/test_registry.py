def test_mccode_pooch_tags():
    from mccode_antlr import Flavor
    from mccode_antlr.reader import default_registries
    for flavor in (Flavor.BASE, Flavor.MCSTAS, Flavor.MCXTRACE,):
        for reg in default_registries(flavor):
            assert reg.version != "main"

