import os
from setuptools import setup, find_packages
from setuptools_rust import Binding, RustExtension

# Читаем README.md для длинного описания в пакете
this_directory = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(this_directory, "README.md")
if os.path.exists(readme_path):
    with open(readme_path, encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = ""

setup(
    name="magnus",
    version="0.1.0",
    author="Maksim Khotinsky",
    description="A Python/Rust framework for non-commutative structural analysis of discrete sequences via fr-codes.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Assistentus/magnus",
    # Автоматически ищет папку magnus/
    packages=find_packages(),
    
    # Инструкция по сборке Rust-движка
    rust_extensions=[
        RustExtension(
            target="fr_rank_rs",  # Имя модуля, которое импортируется в Python (from fr_rank_rs import...)
            path="Cargo.toml",    # Путь к манифесту Rust
            binding=Binding.PyO3
        )
    ],
    
    # Минимальные зависимости для работы Python-кода
    install_requires=[
        "numpy>=1.20.0",
        "scipy>=1.8.0",
    ],
    
    # Требования к версии Python
    python_requires=">=3.12",
    
    # Обязательный флаг False для библиотек, содержащих бинарные расширения (Rust/C++)
    zip_safe=False,
)
