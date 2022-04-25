from distutils.core import setup
from glob import glob
from pkg_resources import parse_requirements

setup(
    name='function',
    packages=['function'],
    package_dir={'function': '.'},
    package_data={'function': glob('**', recursive=True)},
)
