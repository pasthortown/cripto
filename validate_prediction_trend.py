"""
Script para validar la calidad de las predicciones en cuanto a la tendencia.
Compara predicciones vs datos reales y genera un reporte en Markdown.
"""

from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Tuple


def connect_to_mongodb() -> MongoClient:
    """Conecta a MongoDB."""
    connection_string = "mongodb://admin:SecurePass123!@localhost:21018/"
    client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
    return client["binance_data"]


def get_predictions_for_today(db, symbol: str) -> List[Dict]:
    """Obtiene las predicciones del día actual hasta el minuto actual."""
    # Calcular inicio y fin del período
    now = datetime.now(pytz.UTC)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    start_timestamp = int(start_of_today.timestamp() * 1000)
    current_timestamp = int(now.timestamp() * 1000)

    collection = db[f"prediccion_{symbol}"]

    query = {
        "open_time": {
            "$gte": start_timestamp,
            "$lte": current_timestamp
        }
    }

    predictions = list(collection.find(query).sort("open_time", 1))
    print(f"Predicciones obtenidas: {len(predictions)}")

    return predictions


def get_real_data_for_today(db, symbol: str) -> List[Dict]:
    """Obtiene los datos reales del día actual hasta el minuto actual."""
    # Calcular inicio y fin del período
    now = datetime.now(pytz.UTC)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    start_timestamp = int(start_of_today.timestamp() * 1000)
    current_timestamp = int(now.timestamp() * 1000)

    collection = db[symbol]

    query = {
        "open_time": {
            "$gte": start_timestamp,
            "$lte": current_timestamp
        }
    }

    real_data = list(collection.find(query).sort("open_time", 1))
    print(f"Datos reales obtenidos: {len(real_data)}")

    return real_data


def calculate_trend(previous_close: float, current_close: float) -> str:
    """Calcula la tendencia entre dos valores."""
    if current_close > previous_close:
        return "UP"
    elif current_close < previous_close:
        return "DOWN"
    else:
        return "FLAT"


def calculate_percentage_change(previous_close: float, current_close: float) -> float:
    """Calcula el cambio porcentual entre dos valores."""
    if previous_close == 0:
        return 0.0
    return ((current_close - previous_close) / previous_close) * 100


def validate_predictions(predictions: List[Dict], real_data: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Valida las predicciones contra los datos reales.

    Returns:
        Tupla con (lista de comparaciones por minuto, resumen general)
    """
    comparisons = []

    # Crear un diccionario de datos reales por timestamp
    real_data_dict = {data['open_time']: data for data in real_data}

    # Valores previos para calcular tendencias
    prev_pred_close = None
    prev_real_close = None

    trend_matches = 0
    total_comparisons = 0
    total_price_error = 0.0
    total_price_error_pct = 0.0

    for pred in predictions:
        open_time = pred['open_time']

        # Buscar datos reales correspondientes
        real = real_data_dict.get(open_time)

        if not real:
            continue

        pred_close = float(pred['close'])
        real_close = float(real['close'])

        # Calcular error de precio
        price_error = abs(pred_close - real_close)
        price_error_pct = abs((pred_close - real_close) / real_close * 100)

        total_price_error += price_error
        total_price_error_pct += price_error_pct

        # Calcular tendencias (solo si hay valores previos)
        trend_match = None
        pred_trend = None
        real_trend = None

        if prev_pred_close is not None and prev_real_close is not None:
            pred_trend = calculate_trend(prev_pred_close, pred_close)
            real_trend = calculate_trend(prev_real_close, real_close)
            trend_match = pred_trend == real_trend

            if trend_match:
                trend_matches += 1
            total_comparisons += 1

        # Calcular cambios porcentuales
        pred_change_pct = calculate_percentage_change(prev_pred_close, pred_close) if prev_pred_close else 0.0
        real_change_pct = calculate_percentage_change(prev_real_close, real_close) if prev_real_close else 0.0

        comparison = {
            'timestamp': datetime.fromtimestamp(open_time / 1000, tz=pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
            'predicted_close': pred_close,
            'real_close': real_close,
            'price_error': price_error,
            'price_error_pct': price_error_pct,
            'predicted_trend': pred_trend,
            'real_trend': real_trend,
            'trend_match': trend_match,
            'predicted_change_pct': pred_change_pct,
            'real_change_pct': real_change_pct
        }

        comparisons.append(comparison)

        # Actualizar valores previos
        prev_pred_close = pred_close
        prev_real_close = real_close

    # Calcular resumen
    summary = {
        'total_predictions': len(predictions),
        'total_real_data': len(real_data),
        'total_matches_found': len(comparisons),
        'total_trend_comparisons': total_comparisons,
        'trend_matches': trend_matches,
        'trend_accuracy_pct': (trend_matches / total_comparisons * 100) if total_comparisons > 0 else 0,
        'avg_price_error': total_price_error / len(comparisons) if comparisons else 0,
        'avg_price_error_pct': total_price_error_pct / len(comparisons) if comparisons else 0
    }

    return comparisons, summary


def generate_markdown_report(comparisons: List[Dict], summary: Dict, symbol: str) -> str:
    """Genera un reporte en formato Markdown."""

    report = f"""# Reporte de Validación de Predicciones - {symbol}

**Fecha de Generación:** {datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}

## Resumen General

- **Total de Predicciones:** {summary['total_predictions']}
- **Total de Datos Reales:** {summary['total_real_data']}
- **Total de Comparaciones Realizadas:** {summary['total_matches_found']}
- **Comparaciones de Tendencia:** {summary['total_trend_comparisons']}
- **Aciertos de Tendencia:** {summary['trend_matches']}
- **Precisión de Tendencia:** {summary['trend_accuracy_pct']:.2f}%
- **Error Promedio de Precio:** ${summary['avg_price_error']:.4f}
- **Error Promedio de Precio (%):** {summary['avg_price_error_pct']:.4f}%

## Detalle por Minuto

| Timestamp | Predicción | Real | Error ($) | Error (%) | Tendencia Pred | Tendencia Real | Match | Cambio Pred (%) | Cambio Real (%) |
|-----------|------------|------|-----------|-----------|----------------|----------------|-------|-----------------|-----------------|
"""

    for comp in comparisons:
        trend_match_icon = "✅" if comp['trend_match'] else ("❌" if comp['trend_match'] is not None else "-")
        pred_trend = comp['predicted_trend'] if comp['predicted_trend'] else "-"
        real_trend = comp['real_trend'] if comp['real_trend'] else "-"

        report += f"| {comp['timestamp']} | ${comp['predicted_close']:.4f} | ${comp['real_close']:.4f} | "
        report += f"${comp['price_error']:.4f} | {comp['price_error_pct']:.4f}% | "
        report += f"{pred_trend} | {real_trend} | {trend_match_icon} | "
        report += f"{comp['predicted_change_pct']:.4f}% | {comp['real_change_pct']:.4f}% |\n"

    # Agregar análisis adicional
    report += f"""
## Análisis de Tendencia

### Distribución de Tendencias Predichas

"""

    # Contar tendencias
    pred_up = sum(1 for c in comparisons if c['predicted_trend'] == 'UP')
    pred_down = sum(1 for c in comparisons if c['predicted_trend'] == 'DOWN')
    pred_flat = sum(1 for c in comparisons if c['predicted_trend'] == 'FLAT')

    real_up = sum(1 for c in comparisons if c['real_trend'] == 'UP')
    real_down = sum(1 for c in comparisons if c['real_trend'] == 'DOWN')
    real_flat = sum(1 for c in comparisons if c['real_trend'] == 'FLAT')

    report += f"""
| Tendencia | Predicciones | Datos Reales |
|-----------|--------------|--------------|
| UP        | {pred_up}    | {real_up}    |
| DOWN      | {pred_down}  | {real_down}  |
| FLAT      | {pred_flat}  | {real_flat}  |

### Conclusiones

"""

    if summary['trend_accuracy_pct'] >= 70:
        report += "✅ **Excelente:** El modelo tiene una precisión de tendencia superior al 70%.\n"
    elif summary['trend_accuracy_pct'] >= 50:
        report += "⚠️ **Bueno:** El modelo tiene una precisión de tendencia aceptable (50-70%).\n"
    else:
        report += "❌ **Mejorable:** El modelo tiene una precisión de tendencia inferior al 50%.\n"

    if summary['avg_price_error_pct'] <= 1:
        report += "✅ **Excelente:** El error promedio de precio es menor al 1%.\n"
    elif summary['avg_price_error_pct'] <= 3:
        report += "⚠️ **Aceptable:** El error promedio de precio está entre 1-3%.\n"
    else:
        report += "❌ **Alto:** El error promedio de precio es superior al 3%.\n"

    report += f"""
---
*Reporte generado automáticamente por el script de validación de predicciones.*
"""

    return report


def main():
    """Función principal."""
    symbol = "klines_bnbusdt"

    print("=" * 80)
    print(f"Validación de Predicciones - {symbol}")
    print("=" * 80)

    # Conectar a MongoDB
    print("\nConectando a MongoDB...")
    db = connect_to_mongodb()

    # Obtener predicciones
    print(f"\nObteniendo predicciones del día actual...")
    predictions = get_predictions_for_today(db, symbol)

    # Obtener datos reales
    print(f"\nObteniendo datos reales del día actual...")
    real_data = get_real_data_for_today(db, symbol)

    # Validar predicciones
    print(f"\nValidando predicciones contra datos reales...")
    comparisons, summary = validate_predictions(predictions, real_data)

    # Generar reporte
    print(f"\nGenerando reporte en Markdown...")
    report = generate_markdown_report(comparisons, summary, symbol)

    # Guardar reporte
    report_filename = f"prediction_trend_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n[OK] Reporte generado exitosamente: {report_filename}")

    # Mostrar resumen
    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)
    print(f"Precisión de Tendencia: {summary['trend_accuracy_pct']:.2f}%")
    print(f"Error Promedio de Precio: ${summary['avg_price_error']:.4f} ({summary['avg_price_error_pct']:.4f}%)")
    print(f"Aciertos de Tendencia: {summary['trend_matches']}/{summary['total_trend_comparisons']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
