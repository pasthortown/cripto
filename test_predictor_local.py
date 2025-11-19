"""
Script de prueba local para el predictor LSTM.
Este script se ejecuta fuera de Docker pero se conecta a MongoDB en el contenedor.
"""

import sys
import os

# Agregar el directorio predictor al path
predictor_path = os.path.join(os.path.dirname(__file__), 'predictor')
sys.path.insert(0, predictor_path)

# Configurar variables de entorno para conexión a MongoDB local
os.environ['MONGODB_HOST'] = 'localhost'  # MongoDB está en el contenedor pero expuesto en localhost
os.environ['MONGODB_PORT'] = '21018'  # Puerto expuesto en el host (mapeado desde 27017 en el contenedor)
os.environ['MONGODB_DATABASE'] = 'binance_data'
os.environ['MONGODB_USERNAME'] = 'admin'
os.environ['MONGODB_PASSWORD'] = 'SecurePass123!'
os.environ['LOG_DIR'] = './logs'
os.environ['MODELS_DIR'] = './models'

# Crear directorios si no existen
os.makedirs('./logs', exist_ok=True)
os.makedirs('./models', exist_ok=True)

# Importar después de configurar variables de entorno
from prediction_service import PredictionService
from logger_config import setup_logger
import config

logger = setup_logger(__name__, config.LOG_DIR, config.LOG_LEVEL)


def main():
    """Función principal de prueba."""
    try:
        logger.info("="*60)
        logger.info("Iniciando prueba local del predictor")
        logger.info("="*60)

        # Inicializar el servicio de predicción
        service = PredictionService()

        # Lista de símbolos a probar (puedes cambiarla)
        test_symbols = ['btcusdt']  # Empezar con uno solo para prueba

        logger.info(f"Símbolos a procesar: {test_symbols}")

        # Procesar cada símbolo
        for symbol in test_symbols:
            logger.info(f"\n{'='*60}")
            logger.info(f"Probando predicción para {symbol.upper()}")
            logger.info(f"{'='*60}")

            success = service.process_symbol(symbol)

            if success:
                logger.info(f"✓ Predicción exitosa para {symbol}")
            else:
                logger.error(f"✗ Error en predicción para {symbol}")

        # Cerrar conexiones
        service.close()

        logger.info("\n" + "="*60)
        logger.info("Prueba completada")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"Error en la prueba: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
