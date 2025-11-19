"""
Punto de entrada del servicio de predicción multi-horizonte.

ARQUITECTURA CON BUCLE CONTINUO:
- Bucle infinito que valida cada 5 segundos
- Detecta última predicción del día
- Completa horas faltantes secuencialmente
- Espera datos reales antes de predecir cada hora
- Garantiza continuidad: open(n) = close(n-1) REAL

Referencia: consideraciones_adicionales.txt
"""

import time
from datetime import datetime, timedelta
import pytz
from logger_config import setup_logger
import config
from prediction_service import PredictionService

logger = setup_logger(__name__, config.LOG_DIR, config.LOG_LEVEL)


def main():
    """
    Función principal del servicio con BUCLE CONTINUO.

    ALGORITMO:
    1. Bucle infinito que valida cada 5 segundos
    2. Para cada símbolo:
       a. Detectar última predicción del día
       b. Determinar próxima hora a predecir
       c. Validar datos reales disponibles
       d. Predecir si es posible
    3. Continuar hasta completar todas las horas del día
    """
    logger.info("="*80)
    logger.info("PREDICTOR MULTI-HORIZONTE - EJECUCIÓN CONTINUA")
    logger.info("="*80)
    logger.info("Arquitectura:")
    logger.info("  - 12 modelos independientes por símbolo")
    logger.info("  - Ventanas de datos VARIABLES por horizonte")
    logger.info("  - Predicciones con VARIACIONES (deltas)")
    logger.info("  - Continuidad: open(n) = close(n-1) REAL")
    logger.info("  - Bucle continuo validando cada 5 segundos")
    logger.info("")
    logger.info("Ventanas de datos variables:")
    for h, w in config.HORIZON_TRAINING_WINDOWS.items():
        logger.info(f"  Horizonte {h:2d} min → {w:4d} min ({w/1440:.1f} días)")
    logger.info("")
    logger.info("Configuración:")
    logger.info(f"  - Horizontes: {config.PREDICTION_HORIZONS}")
    logger.info(f"  - Ventanas de resampling: {config.RESAMPLE_WINDOWS}")
    logger.info(f"  - LSTM: {config.LSTM_LAYERS} capas x {config.LSTM_UNITS} unidades")
    logger.info(f"  - Epochs: {config.EPOCHS}, Batch size: {config.BATCH_SIZE}")
    logger.info(f"  - Intervalo de validación: {config.VALIDATION_INTERVAL_SECONDS} segundos")
    logger.info(f"  - Edad máxima de modelos: {config.MODEL_MAX_AGE_HOURS} horas")
    logger.info("="*80)

    # Crear servicio de predicción
    service = PredictionService()

    try:
        # Ejecutar bucle continuo (implementado en service)
        service.process_all_symbols_continuous()

    except KeyboardInterrupt:
        logger.info("\n" + "="*80)
        logger.info("INTERRUPCIÓN DE USUARIO DETECTADA")
        logger.info("="*80)
        logger.info("Deteniendo servicio de predicción...")
    except Exception as e:
        logger.error("\n" + "="*80)
        logger.error("ERROR FATAL EN EL SERVICIO")
        logger.error("="*80)
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        logger.info("\nCerrando servicio...")
        try:
            service.close()
        except Exception as e:
            logger.error(f"Error cerrando servicio: {e}")
        logger.info("="*80)
        logger.info("Servicio finalizado")
        logger.info("="*80)


if __name__ == "__main__":
    main()
