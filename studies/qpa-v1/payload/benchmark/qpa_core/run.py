#!/usr/bin/env python3
"""Q1-Q7 use the same resource, reservation and compilation guards as Q8-Q10."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('core_driver',HERE.parent/'qpa_derived/run.py')
R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
R.HERE=HERE
R.DEPENDENCIES+=('benchmark/qpa_derived/run.py','benchmark/qpa_derived/worker.jl','benchmark/qpa_derived/worker.g',
 'benchmark/qpa_derived/verify.py','benchmark/qpa_suite/fixtures.py','benchmark/qpa_suite/integrate.py')
if __name__=='__main__':R.main()
