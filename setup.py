from setuptools import setup, find_packages

setup(
    name="erp-shared",
    version="1.0.0",
    packages=find_packages(),
    package_dir={"": "."},
    install_requires=[
        "sqlalchemy>=2.0",
        "asyncpg",
    ],
)
