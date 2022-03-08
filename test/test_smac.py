# !/usr/bin/env python3
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import pcsparser


def test_SMACparse():
    parser = pcsparser.PCSParser()
    parser.load("files/smacpcs.pcs")
    assert parser.check_validity() is True
