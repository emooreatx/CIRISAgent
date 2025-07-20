"""
Setup script for CIRISManager.
"""
from setuptools import setup, find_packages

setup(
    name="ciris-manager",
    version="0.1.0",
    description="CIRIS Agent Lifecycle Management Service",
    author="CIRIS Team",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=2.0.0",
        "PyYAML>=6.0",
        "aiofiles>=23.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ciris-manager=ciris_manager.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)