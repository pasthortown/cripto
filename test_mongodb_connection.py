"""
Script simple para verificar la conexion a MongoDB.
"""

from pymongo import MongoClient
import sys

def test_connection():
    """Prueba la conexion a MongoDB."""
    try:
        print("Intentando conectar a MongoDB...")

        # Configuracion de conexion
        host = 'localhost'
        port = 21018  # Puerto expuesto en el host (mapeado desde 27017 en el contenedor)
        database = 'binance_data'
        username = 'admin'
        password = 'SecurePass123!'

        # Crear cliente MongoDB
        client = MongoClient(
            host=host,
            port=port,
            username=username,
            password=password,
            authSource='admin',
            serverSelectionTimeoutMS=5000
        )

        # Verificar conexion
        client.admin.command('ping')
        print("[OK] Conexion exitosa a MongoDB")

        # Listar bases de datos
        databases = client.list_database_names()
        print(f"\nBases de datos disponibles: {databases}")

        # Verificar base de datos binance_data
        if database in databases:
            print(f"[OK] Base de datos '{database}' encontrada")

            db = client[database]
            collections = db.list_collection_names()
            print(f"\nColecciones en '{database}':")
            for coll in collections:
                count = db[coll].count_documents({})
                print(f"  - {coll}: {count} documentos")

                # Mostrar un documento de ejemplo si hay colecciones tipo klines_*
                if coll.startswith('klines_'):
                    sample = db[coll].find_one()
                    if sample:
                        print(f"    Ejemplo de documento:")
                        for key, value in list(sample.items())[:8]:  # Mostrar primeros 8 campos
                            print(f"      {key}: {value} (tipo: {type(value).__name__})")
        else:
            print(f"[ERROR] Base de datos '{database}' no encontrada")

        client.close()
        return True

    except Exception as e:
        print(f"[ERROR] Error al conectar a MongoDB: {e}")
        print("\nAsegurate de que:")
        print("1. El contenedor de MongoDB esta corriendo (docker ps)")
        print("2. El puerto 21018 esta expuesto y accesible")
        print("3. Las credenciales son correctas")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
