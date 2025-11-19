"""
Script de validación del ciclo de vida de modelos.

Valida la implementación de la Sección 8 (condiciones.txt):
- Modelos se entrenan UNA VEZ al día
- Modelos son válidos TODO el día
- Formato de archivo sin hora: model_{symbol}_horizon{N}_{YYYYMMDD}.keras
- Validación estricta por día (no por horas)
- Eliminación automática de modelos viejos

Uso:
    python validate_model_lifecycle.py [--symbol BTCUSDT] [--verbose]
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Agregar el directorio padre al path
sys.path.insert(0, str(Path(__file__).parent))

from model_manager import ModelManager
import config
from logger_config import setup_logger

logger = setup_logger(__name__, config.LOG_DIR, "INFO")


def validate_file_format(model_dir: Path, symbol: str):
    """
    Valida que los archivos de modelo sigan el formato correcto.

    Formato esperado: model_{symbol}_horizon{N}_{YYYYMMDD}.keras
    """
    print("\n" + "="*80)
    print("TEST 1: Validación de Formato de Archivos")
    print("="*80)

    if not model_dir.exists():
        print(f"⚠️  Directorio {model_dir} no existe. Creando...")
        model_dir.mkdir(parents=True, exist_ok=True)
        print("✓ No hay modelos para validar (directorio nuevo)")
        return True

    model_files = list(model_dir.glob(f"model_{symbol.lower()}_horizon*.keras"))

    if not model_files:
        print("✓ No hay modelos para validar (directorio vacío)")
        return True

    print(f"Archivos encontrados: {len(model_files)}")

    all_valid = True
    for model_file in model_files:
        filename = model_file.name

        # Parsear nombre del archivo
        try:
            # Esperado: model_btcusdt_horizon1_20251118.keras
            parts = filename.replace(".keras", "").split("_")

            # Encontrar índice de "horizon"
            horizon_idx = None
            for i, part in enumerate(parts):
                if part.startswith("horizon"):
                    horizon_idx = i
                    break

            if horizon_idx is None:
                print(f"✗ {filename}: No se encontró 'horizon' en el nombre")
                all_valid = False
                continue

            # Validar que la fecha tenga formato YYYYMMDD (8 caracteres)
            date_str = parts[horizon_idx + 1]

            if len(date_str) != 8:
                print(f"✗ {filename}: Fecha tiene formato incorrecto (debe ser YYYYMMDD)")
                all_valid = False
                continue

            # Intentar parsear la fecha
            try:
                datetime.strptime(date_str, '%Y%m%d')
                print(f"✓ {filename}: Formato correcto (fecha: {date_str})")
            except ValueError:
                print(f"✗ {filename}: Fecha inválida ({date_str})")
                all_valid = False

        except Exception as e:
            print(f"✗ {filename}: Error al parsear - {e}")
            all_valid = False

    if all_valid:
        print("\n✓ TODOS los archivos tienen formato correcto")
    else:
        print("\n✗ Algunos archivos tienen formato incorrecto")

    return all_valid


def validate_daily_validity(manager: ModelManager, symbol: str):
    """
    Valida que los modelos sean válidos solo si son del día actual.
    """
    print("\n" + "="*80)
    print("TEST 2: Validación de Vigencia Diaria")
    print("="*80)

    today = datetime.now().date()
    print(f"Fecha actual: {today.strftime('%Y%m%d')}")

    is_valid, paths_dict, date_str = manager.check_models_validity(symbol)

    if is_valid:
        print(f"✓ Modelos válidos encontrados: {date_str}")

        # Parsear fecha del modelo
        model_date = datetime.strptime(date_str, '%Y%m%d').date()

        if model_date == today:
            print(f"✓ Modelos son del día ACTUAL ({today.strftime('%Y%m%d')})")
            return True
        else:
            print(f"✗ Modelos NO son del día actual")
            print(f"  - Fecha modelos: {model_date.strftime('%Y%m%d')}")
            print(f"  - Fecha actual:  {today.strftime('%Y%m%d')}")
            return False
    else:
        print(f"⚠️  No hay modelos válidos para {symbol}")
        print("   (Esto es correcto si no hay modelos del día actual)")
        return True


def validate_complete_set(manager: ModelManager, symbol: str):
    """
    Valida que existan TODOS los 12 horizontes.
    """
    print("\n" + "="*80)
    print("TEST 3: Validación de Conjunto Completo")
    print("="*80)

    is_valid, paths_dict, date_str = manager.check_models_validity(symbol)

    if not is_valid:
        print(f"⚠️  No hay modelos válidos para {symbol}")
        return True

    horizons_required = set(config.PREDICTION_HORIZONS)
    horizons_present = set(paths_dict.keys())

    print(f"Horizontes requeridos: {sorted(horizons_required)}")
    print(f"Horizontes presentes:  {sorted(horizons_present)}")

    if horizons_required == horizons_present:
        print(f"✓ TODOS los horizontes están presentes ({len(horizons_present)}/12)")
        return True
    else:
        missing = horizons_required - horizons_present
        extra = horizons_present - horizons_required

        if missing:
            print(f"✗ Faltan horizontes: {sorted(missing)}")
        if extra:
            print(f"✗ Horizontes extra: {sorted(extra)}")

        return False


def simulate_day_cycle(manager: ModelManager, symbol: str):
    """
    Simula el ciclo de un día completo.
    """
    print("\n" + "="*80)
    print("TEST 4: Simulación de Ciclo Diario")
    print("="*80)

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    print(f"Fecha simulada: {today.strftime('%Y%m%d')}")
    print(f"Fecha anterior: {yesterday.strftime('%Y%m%d')}")

    # 1. Verificar modelos del día actual
    print("\n1. Verificando modelos del día actual...")
    is_valid_today, _, date_str_today = manager.check_models_validity(symbol)

    if is_valid_today:
        model_date = datetime.strptime(date_str_today, '%Y%m%d').date()
        if model_date == today:
            print(f"✓ Hay modelos del día actual ({date_str_today})")
        else:
            print(f"⚠️  Hay modelos pero son de {date_str_today} (no de hoy)")
    else:
        print(f"⚠️  No hay modelos del día actual")

    # 2. Limpiar modelos viejos
    print("\n2. Limpiando modelos viejos...")
    manager.cleanup_old_models(symbol)
    print("✓ Limpieza ejecutada")

    # 3. Verificar que solo queden modelos del día actual
    print("\n3. Verificando que solo queden modelos del día actual...")
    model_dir = manager._get_model_path(symbol)

    if os.path.exists(model_dir):
        model_files = [
            f for f in os.listdir(model_dir)
            if f.startswith(f"model_{symbol.lower()}_horizon") and f.endswith(".keras")
        ]

        if not model_files:
            print("✓ No hay archivos de modelo (esperado si no se han entrenado hoy)")
            return True

        dates_found = set()
        for model_file in model_files:
            parts = model_file.replace(".keras", "").split("_")
            for i, part in enumerate(parts):
                if part.startswith("horizon"):
                    date_str = parts[i + 1]
                    dates_found.add(date_str)
                    break

        print(f"Fechas encontradas en archivos: {sorted(dates_found)}")

        all_today = True
        for date_str in dates_found:
            model_date = datetime.strptime(date_str, '%Y%m%d').date()
            if model_date != today:
                print(f"✗ Archivo con fecha antigua: {date_str}")
                all_today = False

        if all_today:
            print("✓ Todos los archivos son del día actual")
            return True
        else:
            print("✗ Hay archivos de días anteriores")
            return False
    else:
        print("✓ No hay directorio de modelos")
        return True


def validate_load_performance(manager: ModelManager, symbol: str):
    """
    Valida el tiempo de carga de modelos.
    """
    print("\n" + "="*80)
    print("TEST 5: Validación de Rendimiento de Carga")
    print("="*80)

    is_valid, paths_dict, date_str = manager.check_models_validity(symbol)

    if not is_valid:
        print(f"⚠️  No hay modelos para cargar")
        return True

    print(f"Cargando {len(paths_dict)} modelos...")

    import time
    start_time = time.time()

    models_dict, scalers_dict, metadata = manager.load_models(paths_dict)

    load_time = time.time() - start_time

    if models_dict and scalers_dict:
        print(f"✓ Modelos cargados exitosamente")
        print(f"  Tiempo: {load_time:.2f} segundos")

        if load_time < 5:
            print(f"✓ Tiempo de carga excelente (<5s)")
            return True
        elif load_time < 10:
            print(f"⚠️  Tiempo de carga aceptable (5-10s)")
            return True
        else:
            print(f"✗ Tiempo de carga lento (>10s)")
            return False
    else:
        print("✗ Error al cargar modelos")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validar ciclo de vida de modelos")
    parser.add_argument(
        "--symbol",
        type=str,
        default="btcusdt",
        help="Símbolo a validar (default: btcusdt)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar logs detallados"
    )

    args = parser.parse_args()

    symbol = args.symbol.lower()

    print("\n" + "="*80)
    print("VALIDACIÓN DEL CICLO DE VIDA DE MODELOS")
    print("="*80)
    print(f"Símbolo: {symbol.upper()}")
    print(f"Directorio de modelos: {config.MODELS_DIR}")
    print(f"Fecha actual: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Inicializar ModelManager
    manager = ModelManager(config.MODELS_DIR)
    model_dir = Path(manager._get_model_path(symbol))

    # Ejecutar tests
    results = {}

    try:
        results["formato"] = validate_file_format(model_dir, symbol)
        results["vigencia"] = validate_daily_validity(manager, symbol)
        results["completo"] = validate_complete_set(manager, symbol)
        results["ciclo"] = simulate_day_cycle(manager, symbol)
        results["rendimiento"] = validate_load_performance(manager, symbol)

    except Exception as e:
        print(f"\n✗ Error durante validación: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Resumen
    print("\n" + "="*80)
    print("RESUMEN DE VALIDACIÓN")
    print("="*80)

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name.upper()}")

    print("="*80)
    print(f"Resultado: {passed_tests}/{total_tests} tests pasados")
    print("="*80)

    if passed_tests == total_tests:
        print("\n✓ VALIDACIÓN EXITOSA: Todos los tests pasaron")
        return 0
    else:
        print(f"\n✗ VALIDACIÓN FALLIDA: {total_tests - passed_tests} test(s) fallaron")
        return 1


if __name__ == "__main__":
    sys.exit(main())
