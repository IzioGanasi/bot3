from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="myiq",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="An unofficial Python library for interacting with the IQ Option trading platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/IzioGanasi/bot3",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=[
        "websockets>=10.0",
        "httpx>=0.23.0",
        "pydantic>=2.0.0",
        "structlog>=21.0.0",
    ],
    extras_require={
        "examples": [
            "scikit-learn>=1.0.0",
            "numpy>=1.21.0",
            "pandas>=1.3.0",
        ],
    },
)