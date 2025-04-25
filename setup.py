from setuptools import setup, find_packages

setup(
    name="jarvis",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in open("requirements.txt")
        if line.strip() and not line.startswith("#")
    ],
    python_requires=">=3.8",
    author="RH-IT",
    description="JARVIS - Ein KI-Assistent mit Spracherkennung",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
) 