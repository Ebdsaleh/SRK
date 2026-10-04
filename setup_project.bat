@echo off
echo [*] Initializing SRK (Rikai Kotoba) directory structure...

:: Create core package and module directories
mkdir src\rikai_kotoba\core 2>nul
mkdir src\rikai_kotoba\formats\saturn 2>nul
mkdir tests 2>nul

:: Create __init__.py files to make it a valid Python package
type nul > src\rikai_kotoba\__init__.py
type nul > src\rikai_kotoba\core\__init__.py
type nul > src\rikai_kotoba\formats\__init__.py
type nul > src\rikai_kotoba\formats\saturn\__init__.py
type nul > tests\__init__.py

:: Create core and system-specific code files
type nul > src\rikai_kotoba\core\cue_parser.py
type nul > src\rikai_kotoba\core\sector_io.py
type nul > src\rikai_kotoba\formats\saturn\ip_bin.py
type nul > src\rikai_kotoba\cli.py

:: Create root files
type nul > README.md
type nul > requirements.txt
type nul > .gitignore

echo [+] Directory structure created successfully under src\rikai_kotoba\!
pause