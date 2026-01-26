#!/usr/bin/env python3
"""
Script de instalación y configuración inicial.
"""
import os
import sys
import subprocess
from pathlib import Path


def main():
    """Ejecuta la instalación y configuración."""
    print("=" * 60)
    print("INSTALACIÓN DEL SISTEMA DE SUBASTAS BOE")
    print("=" * 60)

    base_dir = Path(__file__).parent

    # 1. Verificar Python
    print("\n1. Verificando versión de Python...")
    python_version = sys.version_info
    if python_version < (3, 9):
        print(f"   ❌ Se requiere Python 3.9+, tienes {python_version.major}.{python_version.minor}")
        sys.exit(1)
    print(f"   ✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")

    # 2. Crear entorno virtual (opcional)
    venv_dir = base_dir / "venv"
    if not venv_dir.exists():
        print("\n2. ¿Deseas crear un entorno virtual? [s/N]: ", end="")
        response = input().strip().lower()
        if response in ('s', 'si', 'y', 'yes'):
            print("   Creando entorno virtual...")
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            print("   ✅ Entorno virtual creado en ./venv")
            print("\n   Para activarlo ejecuta:")
            print("   source venv/bin/activate  (Linux/Mac)")
            print("   venv\\Scripts\\activate    (Windows)")

    # 3. Instalar dependencias
    print("\n3. Instalando dependencias...")
    requirements_file = base_dir / "requirements.txt"
    if requirements_file.exists():
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ], check=True)
        print("   ✅ Dependencias instaladas")
    else:
        print("   ⚠️  No se encontró requirements.txt")

    # 4. Crear directorios necesarios
    print("\n4. Creando directorios...")
    directories = [
        base_dir / "data",
        base_dir / "data" / "logs",
        base_dir / "data" / "cache",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"   ✅ {directory.relative_to(base_dir)}")

    # 5. Verificar archivo .env
    print("\n5. Verificando configuración...")
    env_file = base_dir / ".env"
    env_example = base_dir / ".env.example"

    if not env_file.exists():
        if env_example.exists():
            import shutil
            shutil.copy(env_example, env_file)
            print("   ✅ Creado .env desde .env.example")
        else:
            print("   ⚠️  No existe .env - asegúrate de configurarlo")
    else:
        print("   ✅ Archivo .env existe")

    # 6. Inicializar base de datos
    print("\n6. Inicializando base de datos...")
    try:
        sys.path.insert(0, str(base_dir))
        from src.models.database import Database
        from config import settings

        db = Database(settings.DB_PATH)
        stats = db.get_estadisticas()
        db.close()
        print(f"   ✅ Base de datos lista ({stats['total_subastas']} subastas)")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # 7. Verificar ChromeDriver
    print("\n7. Verificando ChromeDriver...")
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        driver_path = ChromeDriverManager().install()
        print(f"   ✅ ChromeDriver disponible")
    except Exception as e:
        print(f"   ⚠️  ChromeDriver se instalará en el primer uso")

    # Resumen
    print("\n" + "=" * 60)
    print("INSTALACIÓN COMPLETADA")
    print("=" * 60)
    print("""
Próximos pasos:

1. Edita el archivo .env con tus credenciales de WordPress
   (ya está configurado con los datos proporcionados)

2. Prueba las conexiones:
   python cli.py test

3. Ejecuta una sincronización de prueba:
   python cli.py sync --dry-run --limit 2

4. Ejecuta la sincronización real:
   python cli.py sync

5. Para automatizar, añade a crontab:
   0 */6 * * * cd ~/subastas-boe-automation && python cli.py sync

Comandos disponibles:
   python cli.py --help     Ver todos los comandos
   python cli.py sync       Sincronizar subastas
   python cli.py status     Ver estado del sistema
   python cli.py test       Probar conexiones
   python cli.py report     Ver reporte de actividad
""")


if __name__ == "__main__":
    main()
