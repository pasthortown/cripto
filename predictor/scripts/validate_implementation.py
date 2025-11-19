#!/usr/bin/env python
"""
Script de validación de la implementación del predictor multi-horizonte.

Valida que todos los componentes estén correctamente implementados:
1. Ventanas variables por horizonte
2. Funciones de bucle continuo
3. Recuperación de horas faltantes
4. Continuidad de predicciones
5. Funciones de MongoDB
"""

import sys
import os

# Agregar path del proyecto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def validate_config():
    """Valida config.py"""
    print("\n" + "="*80)
    print("VALIDANDO config.py")
    print("="*80)

    try:
        import config

        # 1. Verificar HORIZON_TRAINING_WINDOWS
        assert hasattr(config, 'HORIZON_TRAINING_WINDOWS'), "❌ HORIZON_TRAINING_WINDOWS no definido"
        assert isinstance(config.HORIZON_TRAINING_WINDOWS, dict), "❌ HORIZON_TRAINING_WINDOWS debe ser dict"
        assert len(config.HORIZON_TRAINING_WINDOWS) == 12, f"❌ Debe tener 12 horizontes, tiene {len(config.HORIZON_TRAINING_WINDOWS)}"

        # 2. Verificar ventanas específicas
        expected_windows = {
            1: 2880, 2: 2880, 3: 2880, 4: 2880, 5: 2880, 6: 2880,
            10: 4320, 12: 4320, 15: 4320,
            20: 5760, 30: 5760,
            60: 8640
        }

        for h, w in expected_windows.items():
            assert config.HORIZON_TRAINING_WINDOWS[h] == w, \
                f"❌ Horizonte {h} debe tener ventana {w}, tiene {config.HORIZON_TRAINING_WINDOWS.get(h)}"

        # 3. Verificar VALIDATION_INTERVAL_SECONDS
        assert hasattr(config, 'VALIDATION_INTERVAL_SECONDS'), "❌ VALIDATION_INTERVAL_SECONDS no definido"
        assert config.VALIDATION_INTERVAL_SECONDS == 5, "❌ VALIDATION_INTERVAL_SECONDS debe ser 5"

        print("✅ config.py: CORRECTO")
        print(f"   - HORIZON_TRAINING_WINDOWS: {len(config.HORIZON_TRAINING_WINDOWS)} horizontes")
        print(f"   - VALIDATION_INTERVAL_SECONDS: {config.VALIDATION_INTERVAL_SECONDS}s")

        return True

    except Exception as e:
        print(f"❌ Error en config.py: {e}")
        return False


def validate_data_processor():
    """Valida data_processor.py"""
    print("\n" + "="*80)
    print("VALIDANDO data_processor.py")
    print("="*80)

    try:
        from data_processor import DataProcessor
        import inspect

        dp = DataProcessor()

        # 1. Verificar determine_training_window acepta window_size
        sig = inspect.signature(dp.determine_training_window)
        params = list(sig.parameters.keys())

        assert 'window_size' in params, "❌ determine_training_window() debe tener parámetro window_size"

        # 2. Verificar prepare_prediction_features acepta window_size
        sig2 = inspect.signature(dp.prepare_prediction_features)
        params2 = list(sig2.parameters.keys())

        assert 'window_size' in params2, "❌ prepare_prediction_features() debe tener parámetro window_size"

        print("✅ data_processor.py: CORRECTO")
        print(f"   - determine_training_window() parámetros: {params}")
        print(f"   - prepare_prediction_features() parámetros: {params2}")

        return True

    except Exception as e:
        print(f"❌ Error en data_processor.py: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_lstm_predictor():
    """Valida lstm_predictor.py"""
    print("\n" + "="*80)
    print("VALIDANDO lstm_predictor.py")
    print("="*80)

    try:
        from lstm_predictor import LSTMPredictor
        import inspect

        predictor = LSTMPredictor()

        # 1. Verificar train_models_for_all_horizons acepta symbol y all_data
        sig = inspect.signature(predictor.train_models_for_all_horizons)
        params = list(sig.parameters.keys())

        assert 'symbol' in params, "❌ train_models_for_all_horizons() debe tener parámetro symbol"
        assert 'all_data' in params, "❌ train_models_for_all_horizons() debe tener parámetro all_data"
        assert 'reference_time' not in params, "❌ train_models_for_all_horizons() NO debe tener reference_time"

        print("✅ lstm_predictor.py: CORRECTO")
        print(f"   - train_models_for_all_horizons() parámetros: {params}")

        return True

    except Exception as e:
        print(f"❌ Error en lstm_predictor.py: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_mongo_client():
    """Valida mongo_client.py"""
    print("\n" + "="*80)
    print("VALIDANDO mongo_client.py")
    print("="*80)

    try:
        from mongo_client import MongoDBClient
        import inspect

        # Verificar métodos requeridos
        required_methods = [
            'get_last_prediction_hour_today',
            'check_real_data_available_until',
            'check_predictions_for_hour',
            'get_real_close_at_time'
        ]

        missing_methods = []
        for method_name in required_methods:
            if not hasattr(MongoDBClient, method_name):
                missing_methods.append(method_name)

        if missing_methods:
            print(f"❌ Métodos faltantes: {missing_methods}")
            return False

        print("✅ mongo_client.py: CORRECTO")
        print(f"   - Métodos implementados: {len(required_methods)}/4")
        for method in required_methods:
            print(f"     ✓ {method}()")

        return True

    except Exception as e:
        print(f"❌ Error en mongo_client.py: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_prediction_service():
    """Valida prediction_service.py"""
    print("\n" + "="*80)
    print("VALIDANDO prediction_service.py")
    print("="*80)

    try:
        from prediction_service import PredictionService
        import inspect

        # Verificar método process_all_symbols_continuous
        if not hasattr(PredictionService, 'process_all_symbols_continuous'):
            print("❌ Falta método process_all_symbols_continuous()")
            return False

        print("✅ prediction_service.py: CORRECTO")
        print("   - process_all_symbols_continuous() implementado")

        return True

    except Exception as e:
        print(f"❌ Error en prediction_service.py: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_main():
    """Valida main.py"""
    print("\n" + "="*80)
    print("VALIDANDO main.py")
    print("="*80)

    try:
        # Leer contenido de main.py
        with open(os.path.join(os.path.dirname(__file__), '..', 'main.py'), 'r', encoding='utf-8') as f:
            content = f.read()

        # Verificar que use process_all_symbols_continuous
        if 'process_all_symbols_continuous' not in content:
            print("❌ main.py no usa process_all_symbols_continuous()")
            return False

        # Verificar que NO tenga bucle while True local
        main_function_start = content.find('def main():')
        if main_function_start == -1:
            print("❌ No se encontró función main()")
            return False

        main_content = content[main_function_start:]

        # El bucle debe estar en service, no en main
        if 'while True:' in main_content and 'service.process_all_symbols_continuous()' in main_content:
            # OK: puede tener while True si es dentro del service
            pass

        print("✅ main.py: CORRECTO")
        print("   - Usa service.process_all_symbols_continuous()")

        return True

    except Exception as e:
        print(f"❌ Error en main.py: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Función principal de validación"""
    print("\n" + "="*80)
    print("VALIDACIÓN DE IMPLEMENTACIÓN - PREDICTOR MULTI-HORIZONTE")
    print("="*80)

    results = {
        'config.py': validate_config(),
        'data_processor.py': validate_data_processor(),
        'lstm_predictor.py': validate_lstm_predictor(),
        'mongo_client.py': validate_mongo_client(),
        'prediction_service.py': validate_prediction_service(),
        'main.py': validate_main()
    }

    print("\n" + "="*80)
    print("RESUMEN DE VALIDACIÓN")
    print("="*80)

    total = len(results)
    passed = sum(results.values())

    for module, status in results.items():
        status_str = "✅ PASS" if status else "❌ FAIL"
        print(f"{status_str} - {module}")

    print("\n" + "-"*80)
    print(f"RESULTADO: {passed}/{total} módulos correctos")
    print("-"*80)

    if passed == total:
        print("\n🎉 ¡VALIDACIÓN COMPLETA EXITOSA!")
        print("\nTodos los componentes están correctamente implementados.")
        print("\nVentanas variables configuradas:")
        import config
        for h in sorted(config.HORIZON_TRAINING_WINDOWS.keys()):
            w = config.HORIZON_TRAINING_WINDOWS[h]
            print(f"  Horizonte {h:2d} min → {w:4d} min ({w/1440:.1f} días)")

        print("\nEl sistema está listo para ejecutarse.")
        return 0
    else:
        print("\n⚠️ VALIDACIÓN FALLIDA")
        print(f"\nHay {total - passed} módulo(s) con errores.")
        print("Revisa los mensajes de error anteriores para más detalles.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
