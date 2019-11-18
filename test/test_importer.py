import COPASI
import pytest


def test_copasi_version():
    assert int(COPASI.CVersion.VERSION.getVersionDevel()) >= 214, "Need newer COPASI version"
