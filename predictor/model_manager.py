"""
Gestor de modelos LSTM multi-horizonte por símbolo.

NUEVA ARQUITECTURA:
- Maneja MÚLTIPLES modelos por símbolo (12 modelos + 12 scalers)
- Formato: model_{symbol}_horizon{N}_{date}.keras
- Valida que TODOS los horizontes estén presentes
- Limpia modelos obsoletos (más de 24 horas)
"""

import os
import pickle
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from tensorflow import keras
from sklearn.preprocessing import MinMaxScaler
from logger_config import setup_logger
import config

logger = setup_logger(__name__, config.LOG_DIR, config.LOG_LEVEL)


class ModelManager:
    """
    Gestor para crear, cargar y administrar modelos LSTM multi-horizonte por símbolo.

    Cada símbolo tiene 12 modelos (uno por horizonte) + 12 scalers.
    """

    def __init__(self, models_dir: str = None):
        """
        Inicializa el gestor de modelos.

        Args:
            models_dir: Directorio donde se guardan los modelos
        """
        self.models_dir = models_dir or config.MODELS_DIR
        os.makedirs(self.models_dir, exist_ok=True)
        logger.info(f"ModelManager inicializado. Directorio: {self.models_dir}")

    def _get_model_path(self, symbol: str) -> str:
        """
        Obtiene la ruta de la carpeta del modelo para un símbolo.

        Args:
            symbol: Símbolo de la moneda

        Returns:
            Ruta de la carpeta del modelo
        """
        return os.path.join(self.models_dir, symbol.lower())

    def _get_model_file_paths(
        self,
        symbol: str,
        horizon: int,
        date: datetime
    ) -> Tuple[str, str]:
        """
        Obtiene las rutas de los archivos del modelo para un horizonte específico.

        Args:
            symbol: Símbolo de la moneda
            horizon: Horizonte temporal (ej: 1, 2, 5, etc.)
            date: Fecha de creación del modelo

        Returns:
            Tupla con (ruta_modelo, ruta_scaler)
        """
        model_dir = self._get_model_path(symbol)

        # FORMATO NUEVO (Sección 8): Solo fecha, SIN hora
        # Formato: model_{symbol}_horizon{N}_{YYYYMMDD}.keras
        date_str = date.strftime('%Y%m%d')  # Solo fecha del día

        model_file = os.path.join(model_dir, f"model_{symbol.lower()}_horizon{horizon}_{date_str}.keras")
        scaler_file = os.path.join(model_dir, f"scaler_{symbol.lower()}_horizon{horizon}_{date_str}.pkl")

        return model_file, scaler_file

    def check_models_validity(self, symbol: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Verifica si existen modelos válidos para TODOS los horizontes.

        VALIDEZ (Sección 8): Los modelos son válidos SOLO si fueron creados el día ACTUAL.
        No importa la hora, sino que sea el mismo día.

        Un conjunto de modelos es válido si:
        1. Existen modelos para TODOS los horizontes configurados
        2. Fueron creados el DÍA ACTUAL (model_date.date() == today)
        3. Todos los archivos existen (modelo + scaler)

        Args:
            symbol: Símbolo de la moneda

        Returns:
            Tupla (es_válido, paths_dict, date_str)
            - es_válido: True si todos los modelos están presentes y son del día actual
            - paths_dict: Diccionario {horizon: (model_path, scaler_path)}
            - date_str: String con la fecha de los modelos (formato YYYYMMDD)
        """
        model_dir = self._get_model_path(symbol)

        if not os.path.exists(model_dir):
            logger.info(f"[{symbol}] No existe directorio de modelos")
            return False, None, None

        # Obtener fecha ACTUAL (sin hora)
        today = datetime.now().date()

        # Buscar archivos de modelo en el directorio
        model_files = [
            f for f in os.listdir(model_dir)
            if f.startswith(f"model_{symbol.lower()}_horizon") and f.endswith(".keras")
        ]

        if not model_files:
            logger.info(f"[{symbol}] No se encontraron modelos")
            return False, None, None

        # Agrupar modelos por fecha
        models_by_date = {}
        for model_file in model_files:
            try:
                # Extraer horizonte y fecha del nombre
                # Formato NUEVO: model_{symbol}_horizon{N}_{YYYYMMDD}.keras
                parts = model_file.replace(".keras", "").split("_")

                # Encontrar el índice donde está "horizon"
                horizon_idx = None
                for i, part in enumerate(parts):
                    if part.startswith("horizon"):
                        horizon_idx = i
                        break

                if horizon_idx is None:
                    logger.warning(f"No se pudo parsear horizonte de {model_file}")
                    continue

                horizon_str = parts[horizon_idx].replace("horizon", "")
                horizon = int(horizon_str)

                # La fecha está después del horizonte (YYYYMMDD sin hora)
                date_str = parts[horizon_idx + 1]

                if date_str not in models_by_date:
                    models_by_date[date_str] = {}

                models_by_date[date_str][horizon] = model_file

            except (ValueError, IndexError) as e:
                logger.error(f"Error al parsear nombre de modelo {model_file}: {e}")
                continue

        if not models_by_date:
            logger.info(f"[{symbol}] No se pudieron parsear modelos")
            return False, None, None

        # Buscar el conjunto de modelos del DÍA ACTUAL
        for date_str in sorted(models_by_date.keys(), reverse=True):
            models_for_date = models_by_date[date_str]

            # Parsear fecha del modelo
            try:
                # Formato: YYYYMMDD
                model_date = datetime.strptime(date_str, '%Y%m%d').date()

            except ValueError as e:
                logger.error(f"Error parseando fecha {date_str}: {e}")
                continue

            # VALIDACIÓN DIARIA: ¿Es del día ACTUAL?
            if model_date != today:
                # Modelo obsoleto (día anterior)
                logger.debug(
                    f"[{symbol}] Modelos obsoletos ({date_str}). "
                    f"Esperado: {today.strftime('%Y%m%d')}"
                )
                # Marcar para eliminación posterior
                continue

            # Verificar si tenemos TODOS los horizontes
            horizons_present = set(models_for_date.keys())
            horizons_required = set(config.PREDICTION_HORIZONS)

            if horizons_present != horizons_required:
                missing = horizons_required - horizons_present
                logger.warning(
                    f"[{symbol}] Conjunto de modelos incompleto para {date_str}. "
                    f"Faltan horizontes: {missing}"
                )
                continue

            # Verificar que todos los archivos existan
            paths_dict = {}
            all_files_exist = True

            for horizon in config.PREDICTION_HORIZONS:
                model_path = os.path.join(model_dir, models_for_date[horizon])
                scaler_path = model_path.replace(".keras", ".pkl").replace("model_", "scaler_")

                if not os.path.exists(model_path) or not os.path.exists(scaler_path):
                    logger.warning(
                        f"[{symbol}] Archivos faltantes para horizonte {horizon}: "
                        f"model={os.path.exists(model_path)}, scaler={os.path.exists(scaler_path)}"
                    )
                    all_files_exist = False
                    break

                paths_dict[horizon] = (model_path, scaler_path)

            if not all_files_exist:
                continue

            # ¡Conjunto válido encontrado! (del día actual)
            logger.info(f"[{symbol}] ✓ Modelos válidos encontrados (fecha: {date_str})")
            logger.info(f"[{symbol}]   └─ {len(horizons_present)} horizontes completos")

            return True, paths_dict, date_str

        # No se encontró ningún conjunto válido del día actual
        logger.info(f"[{symbol}] ⚠️  No hay modelos válidos para el día actual ({today.strftime('%Y%m%d')})")
        return False, None, None

    def _delete_models_by_date(self, symbol: str, date_str: str):
        """
        Elimina todos los modelos de un símbolo para una fecha específica.

        Args:
            symbol: Símbolo de la moneda
            date_str: Fecha en formato YYYYMMDD_HH
        """
        model_dir = self._get_model_path(symbol)

        if not os.path.exists(model_dir):
            return

        # Buscar todos los archivos con esta fecha
        files_to_delete = [
            f for f in os.listdir(model_dir)
            if date_str in f and (f.endswith(".keras") or f.endswith(".pkl"))
        ]

        for file_name in files_to_delete:
            file_path = os.path.join(model_dir, file_name)
            try:
                os.remove(file_path)
                logger.debug(f"Archivo eliminado: {file_path}")
            except Exception as e:
                logger.error(f"Error al eliminar {file_path}: {e}")

        if files_to_delete:
            logger.info(f"Modelos eliminados para {symbol} ({date_str}): {len(files_to_delete)} archivos")

    def save_models(
        self,
        symbol: str,
        models_dict: Dict[int, keras.Model],
        scalers_dict: Dict[int, MinMaxScaler],
        metadata: dict
    ) -> bool:
        """
        Guarda todos los modelos y scalers de un símbolo con timestamp del día actual.

        FORMATO NUEVO (Sección 8): model_{symbol}_horizon{N}_{YYYYMMDD}.keras
        (Sin hora, solo fecha del día)

        Args:
            symbol: Símbolo de la moneda
            models_dict: Diccionario {horizon: model}
            scalers_dict: Diccionario {horizon: scaler}
            metadata: Diccionario con información general (se guarda una sola vez)

        Returns:
            True si se guardaron todos correctamente, False en caso contrario
        """
        try:
            model_dir = self._get_model_path(symbol)
            os.makedirs(model_dir, exist_ok=True)

            # Crear timestamp SOLO con fecha (sin hora)
            now = datetime.now()
            date_str = now.strftime('%Y%m%d')  # Solo fecha del día

            logger.info(f"[{symbol}] Guardando modelos del día ({date_str})...")

            # Validar que tengamos todos los horizontes
            horizons_required = set(config.PREDICTION_HORIZONS)
            horizons_models = set(models_dict.keys())
            horizons_scalers = set(scalers_dict.keys())

            if horizons_models != horizons_required:
                missing = horizons_required - horizons_models
                logger.error(f"Faltan modelos para horizontes: {missing}")
                return False

            if horizons_scalers != horizons_required:
                missing = horizons_required - horizons_scalers
                logger.error(f"Faltan scalers para horizontes: {missing}")
                return False

            # Guardar cada modelo y scaler
            saved_count = 0
            for horizon in config.PREDICTION_HORIZONS:
                model_file, scaler_file = self._get_model_file_paths(symbol, horizon, now)

                try:
                    # Guardar modelo
                    model = models_dict[horizon]
                    model.save(model_file)
                    logger.debug(f"Modelo guardado: {os.path.basename(model_file)}")

                    # Guardar scaler
                    scaler = scalers_dict[horizon]
                    with open(scaler_file, 'wb') as f:
                        pickle.dump(scaler, f)
                    logger.debug(f"Scaler guardado: {os.path.basename(scaler_file)}")

                    saved_count += 1

                except Exception as e:
                    logger.error(f"Error guardando modelo/scaler para horizonte {horizon}: {e}")
                    return False

            # Guardar metadata una sola vez
            metadata_file = os.path.join(model_dir, f"metadata_{symbol.lower()}_{date_str}.pkl")
            metadata['created_at'] = now.isoformat()
            metadata['symbol'] = symbol
            metadata['date_str'] = date_str
            metadata['horizons'] = list(config.PREDICTION_HORIZONS)

            with open(metadata_file, 'wb') as f:
                pickle.dump(metadata, f)
            logger.debug(f"Metadata guardada: {os.path.basename(metadata_file)}")

            logger.info(f"[{symbol}] ✓ Modelos guardados exitosamente")
            logger.info(f"[{symbol}]   └─ {saved_count}/{len(config.PREDICTION_HORIZONS)} horizontes")
            logger.info(f"[{symbol}]   └─ Fecha: {date_str}")

            return True

        except Exception as e:
            logger.error(f"Error al guardar modelos para {symbol}: {e}", exc_info=True)
            return False

    def load_models(self, paths_dict: Dict[int, Tuple[str, str]]) -> Tuple[Dict, Dict, Dict]:
        """
        Carga todos los modelos y scalers desde las rutas especificadas.

        Args:
            paths_dict: Diccionario {horizon: (model_path, scaler_path)}

        Returns:
            Tupla (models_dict, scalers_dict, metadata)
            - models_dict: {horizon: model}
            - scalers_dict: {horizon: scaler}
            - metadata: Diccionario con información general
        """
        try:
            models_dict = {}
            scalers_dict = {}

            logger.info(f"Cargando {len(paths_dict)} modelos...")

            for horizon, (model_path, scaler_path) in paths_dict.items():
                try:
                    # Cargar modelo
                    model = keras.models.load_model(model_path)
                    models_dict[horizon] = model
                    logger.debug(f"Modelo cargado: horizonte {horizon}")

                    # Cargar scaler
                    with open(scaler_path, 'rb') as f:
                        scaler = pickle.load(f)
                    scalers_dict[horizon] = scaler
                    logger.debug(f"Scaler cargado: horizonte {horizon}")

                except Exception as e:
                    logger.error(f"Error cargando modelo/scaler para horizonte {horizon}: {e}")
                    return {}, {}, {}

            # Cargar metadata (buscar archivo metadata en el mismo directorio)
            metadata = {}
            if paths_dict:
                # Obtener directorio del primer modelo
                first_model_path = list(paths_dict.values())[0][0]
                model_dir = os.path.dirname(first_model_path)

                # Buscar archivo metadata
                metadata_files = [
                    f for f in os.listdir(model_dir)
                    if f.startswith("metadata_") and f.endswith(".pkl")
                ]

                if metadata_files:
                    # Tomar el más reciente
                    metadata_files.sort(reverse=True)
                    metadata_file = os.path.join(model_dir, metadata_files[0])

                    try:
                        with open(metadata_file, 'rb') as f:
                            metadata = pickle.load(f)
                        logger.debug(f"Metadata cargada: {metadata_file}")
                    except Exception as e:
                        logger.error(f"Error cargando metadata: {e}")

            logger.info(f"✓ Modelos cargados exitosamente")
            logger.info(f"  Modelos: {list(models_dict.keys())}")
            logger.info(f"  Scalers: {list(scalers_dict.keys())}")

            return models_dict, scalers_dict, metadata

        except Exception as e:
            logger.error(f"Error al cargar modelos: {e}", exc_info=True)
            return {}, {}, {}

    def cleanup_old_models(self, symbol: str):
        """
        Elimina modelos que NO sean del día actual.

        Se ejecuta automáticamente antes de entrenar nuevos modelos.
        (Sección 8: condiciones.txt)

        Args:
            symbol: Símbolo de la moneda
        """
        model_dir = self._get_model_path(symbol)

        if not os.path.exists(model_dir):
            return

        # Obtener fecha ACTUAL (sin hora)
        today = datetime.now().date()

        # Buscar todos los archivos de modelo
        model_files = [
            f for f in os.listdir(model_dir)
            if f.startswith(f"model_{symbol.lower()}_horizon") and f.endswith(".keras")
        ]

        # Agrupar por fecha
        dates_found = set()
        for model_file in model_files:
            try:
                # Extraer fecha del nombre
                # Formato: model_{symbol}_horizon{N}_{YYYYMMDD}.keras
                parts = model_file.replace(".keras", "").split("_")

                # Encontrar el índice donde está "horizon"
                horizon_idx = None
                for i, part in enumerate(parts):
                    if part.startswith("horizon"):
                        horizon_idx = i
                        break

                if horizon_idx is None:
                    continue

                # La fecha está después del horizonte (YYYYMMDD)
                date_str = parts[horizon_idx + 1]
                dates_found.add(date_str)

            except (ValueError, IndexError) as e:
                logger.error(f"Error parseando archivo {model_file}: {e}")
                continue

        # Eliminar modelos que NO sean del día actual
        deleted_count = 0
        for date_str in dates_found:
            try:
                # Parsear fecha del modelo
                model_date = datetime.strptime(date_str, '%Y%m%d').date()

                # ¿Es del día actual?
                if model_date != today:
                    logger.info(
                        f"[{symbol}] Eliminando modelos obsoletos ({date_str}). "
                        f"Día actual: {today.strftime('%Y%m%d')}"
                    )
                    self._delete_models_by_date(symbol, date_str)
                    deleted_count += 1

            except ValueError as e:
                logger.error(f"Error parseando fecha {date_str}: {e}")
                continue

        if deleted_count > 0:
            logger.info(f"[{symbol}] ✓ Limpieza completada: {deleted_count} conjunto(s) eliminado(s)")
