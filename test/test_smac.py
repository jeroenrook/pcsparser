# !/usr/bin/env python3
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import pcsparser


def test_parse():
    parser = pcsparser.PCSParser()
    parser.load("files/smacpcs.pcs")
    assert parser.check_validity() is True

    parser.export("paramils", "/dev/null")