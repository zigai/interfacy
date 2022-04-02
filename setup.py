from setuptools import setup, find_packages
with open('./requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="cliera",
    version="0.0.1",
    description="",
    author="Ziga Ivansek",
    install_requires=requirements,
    #packages=find_packages(),
    py_modules=["cliera"],
    package_dir={'': 'cliera'},
)
