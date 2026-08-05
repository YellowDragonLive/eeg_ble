from setuptools import setup, find_packages

setup(
    name="eeg-ble",
    version="0.1.0",
    description="Bluetooth Low Energy module for EEG neurofeedback devices",
    author="YellowDragonLive",
    author_email="",
    url="https://github.com/YellowDragonLive/eeg_ble",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "bleak>=0.19.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
