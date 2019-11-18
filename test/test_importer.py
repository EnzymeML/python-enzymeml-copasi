import COPASI
import sys
import os
_PATH = os.path.abspath("../")
sys.path.append(_PATH)
sys.path.append(os.path.join(_PATH, 'python-enzymeml'))

try:
    import enzymeml_importer
except ImportError:
    from .. import enzymeml_importer


def test_copasi_version():
    assert int(COPASI.CVersion.VERSION.getVersionDevel()) >= 214, \
        "Need newer COPASI version"


def test_import():
    test_file = os.path.join(
        os.path.join(_PATH, 'example'), 'model_example.omex')
    assert os.path.exists(test_file)
    out_dir = os.path.join(_PATH, 'out')
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
    importer = enzymeml_importer.EnzymeMLImporter(test_file, out_dir)
    importer.convert()

    assert os.path.exists(importer.copasi_file)
