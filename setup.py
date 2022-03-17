from setuptools import setup, find_packages
with open('./requirements.txt') as f:
    requirements = f.read().splitlines()

setup(name="cliera",
      version="0.0.1",
      description="",
      author="Ziga Ivansek",
      packages=find_packages(),
      install_requires=requirements)