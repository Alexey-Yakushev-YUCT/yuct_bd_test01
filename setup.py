from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize("yuct_speed_core.pyx", language="c++")
)
