"""
Gestión de base de datos SQLite para almacenamiento de subastas.
"""
import sqlite3
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from pathlib import Path
import json

from .subasta import Subasta, Bien


class Database:
    """Gestiona la base de datos SQLite de subastas."""

    def __init__(self, db_path: str):
        """Inicializa la conexión a la base de datos."""
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """Establece conexión con la base de datos."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def _create_tables(self):
        """Crea las tablas necesarias si no existen."""
        cursor = self.conn.cursor()

        # Tabla de subastas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subastas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_subasta TEXT UNIQUE NOT NULL,
                tipo_subasta TEXT,
                estado TEXT,
                cuenta_expediente TEXT,
                fecha_inicio DATETIME,
                fecha_conclusion DATETIME,
                cantidad_reclamada REAL,
                valor_subasta REAL,
                tasacion REAL,
                puja_minima REAL,
                tramos_pujas REAL,
                importe_deposito REAL,
                anuncio_boe TEXT,
                lotes TEXT,
                url_detalle TEXT,
                url_edicto TEXT,
                url_certificacion_cargas TEXT,
                autoridad_gestora TEXT,
                localidad_juzgado TEXT,
                telefono_juzgado TEXT,
                fax_juzgado TEXT,
                email_juzgado TEXT,
                fecha_scraping DATETIME DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion DATETIME,
                publicado_wp INTEGER DEFAULT 0,
                wp_post_id INTEGER,
                hash_datos TEXT,
                activa INTEGER DEFAULT 1
            )
        """)

        # Tabla de bienes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bienes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_subasta TEXT NOT NULL,
                numero_bien INTEGER,
                tipo_bien TEXT,
                subtipo_bien TEXT,
                descripcion TEXT,
                direccion TEXT,
                codigo_postal TEXT,
                localidad TEXT,
                provincia TEXT,
                provincia_codigo TEXT,
                situacion_posesoria TEXT,
                visitable TEXT,
                cargas TEXT,
                valor_tasacion REAL,
                fotos_urls TEXT,
                FOREIGN KEY (id_subasta) REFERENCES subastas(id_subasta)
            )
        """)

        # Tabla de log de sincronización
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_ejecucion DATETIME DEFAULT CURRENT_TIMESTAMP,
                provincia_codigo TEXT,
                subastas_encontradas INTEGER DEFAULT 0,
                subastas_nuevas INTEGER DEFAULT 0,
                subastas_actualizadas INTEGER DEFAULT 0,
                subastas_publicadas INTEGER DEFAULT 0,
                errores INTEGER DEFAULT 0,
                duracion_segundos REAL,
                mensaje TEXT
            )
        """)

        # Índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_id_subasta ON subastas(id_subasta)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_estado ON subastas(estado)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_publicado ON subastas(publicado_wp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bien_subasta ON bienes(id_subasta)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bien_provincia ON bienes(provincia_codigo)")

        self.conn.commit()

    def close(self):
        """Cierra la conexión a la base de datos."""
        if self.conn:
            self.conn.close()

    def get_subasta(self, id_subasta: str) -> Optional[Subasta]:
        """Obtiene una subasta por su ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM subastas WHERE id_subasta = ?", (id_subasta,))
        row = cursor.fetchone()

        if not row:
            return None

        subasta = self._row_to_subasta(row)
        subasta.bienes = self._get_bienes(id_subasta)
        return subasta

    def _row_to_subasta(self, row: sqlite3.Row) -> Subasta:
        """Convierte una fila de BD a objeto Subasta."""
        return Subasta(
            id=row["id"],
            id_subasta=row["id_subasta"],
            tipo_subasta=row["tipo_subasta"] or "",
            estado=row["estado"] or "",
            cuenta_expediente=row["cuenta_expediente"] or "",
            fecha_inicio=datetime.fromisoformat(row["fecha_inicio"]) if row["fecha_inicio"] else None,
            fecha_conclusion=datetime.fromisoformat(row["fecha_conclusion"]) if row["fecha_conclusion"] else None,
            cantidad_reclamada=Decimal(str(row["cantidad_reclamada"] or 0)),
            valor_subasta=Decimal(str(row["valor_subasta"] or 0)),
            tasacion=Decimal(str(row["tasacion"] or 0)),
            puja_minima=Decimal(str(row["puja_minima"] or 0)),
            tramos_pujas=Decimal(str(row["tramos_pujas"] or 0)),
            importe_deposito=Decimal(str(row["importe_deposito"] or 0)),
            anuncio_boe=row["anuncio_boe"] or "",
            lotes=row["lotes"] or "",
            url_detalle=row["url_detalle"] or "",
            url_edicto=row["url_edicto"] or "",
            url_certificacion_cargas=row["url_certificacion_cargas"] or "",
            autoridad_gestora=row["autoridad_gestora"] or "",
            localidad_juzgado=row["localidad_juzgado"] or "",
            telefono_juzgado=row["telefono_juzgado"] or "",
            fax_juzgado=row["fax_juzgado"] or "",
            email_juzgado=row["email_juzgado"] or "",
            fecha_scraping=datetime.fromisoformat(row["fecha_scraping"]) if row["fecha_scraping"] else None,
            fecha_actualizacion=datetime.fromisoformat(row["fecha_actualizacion"]) if row["fecha_actualizacion"] else None,
            publicado_wp=bool(row["publicado_wp"]),
            wp_post_id=row["wp_post_id"],
            hash_datos=row["hash_datos"] or "",
            activa=bool(row["activa"]),
        )

    def _get_bienes(self, id_subasta: str) -> List[Bien]:
        """Obtiene los bienes de una subasta."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM bienes WHERE id_subasta = ?", (id_subasta,))
        rows = cursor.fetchall()

        bienes = []
        for row in rows:
            fotos = json.loads(row["fotos_urls"]) if row["fotos_urls"] else []
            bien = Bien(
                id=row["id"],
                id_subasta=row["id_subasta"],
                numero_bien=row["numero_bien"] or 1,
                tipo_bien=row["tipo_bien"] or "",
                subtipo_bien=row["subtipo_bien"] or "",
                descripcion=row["descripcion"] or "",
                direccion=row["direccion"] or "",
                codigo_postal=row["codigo_postal"] or "",
                localidad=row["localidad"] or "",
                provincia=row["provincia"] or "",
                provincia_codigo=row["provincia_codigo"] or "",
                situacion_posesoria=row["situacion_posesoria"] or "",
                visitable=row["visitable"] or "",
                cargas=row["cargas"] or "",
                valor_tasacion=Decimal(str(row["valor_tasacion"] or 0)),
                fotos_urls=fotos,
            )
            bienes.append(bien)
        return bienes

    def insert_subasta(self, subasta: Subasta) -> int:
        """Inserta una nueva subasta en la base de datos."""
        cursor = self.conn.cursor()

        subasta.hash_datos = subasta.calcular_hash()
        subasta.fecha_scraping = datetime.now()

        cursor.execute("""
            INSERT INTO subastas (
                id_subasta, tipo_subasta, estado, cuenta_expediente,
                fecha_inicio, fecha_conclusion, cantidad_reclamada,
                valor_subasta, tasacion, puja_minima, tramos_pujas,
                importe_deposito, anuncio_boe, lotes, url_detalle,
                url_edicto, url_certificacion_cargas, autoridad_gestora,
                localidad_juzgado, telefono_juzgado, fax_juzgado, email_juzgado,
                fecha_scraping, hash_datos, activa
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            subasta.id_subasta,
            subasta.tipo_subasta,
            subasta.estado,
            subasta.cuenta_expediente,
            subasta.fecha_inicio.isoformat() if subasta.fecha_inicio else None,
            subasta.fecha_conclusion.isoformat() if subasta.fecha_conclusion else None,
            float(subasta.cantidad_reclamada),
            float(subasta.valor_subasta),
            float(subasta.tasacion),
            float(subasta.puja_minima),
            float(subasta.tramos_pujas),
            float(subasta.importe_deposito),
            subasta.anuncio_boe,
            subasta.lotes,
            subasta.url_detalle,
            subasta.url_edicto,
            subasta.url_certificacion_cargas,
            subasta.autoridad_gestora,
            subasta.localidad_juzgado,
            subasta.telefono_juzgado,
            subasta.fax_juzgado,
            subasta.email_juzgado,
            subasta.fecha_scraping.isoformat(),
            subasta.hash_datos,
            1 if subasta.activa else 0,
        ))

        subasta_id = cursor.lastrowid

        # Insertar bienes
        for bien in subasta.bienes:
            bien.id_subasta = subasta.id_subasta
            self._insert_bien(bien)

        self.conn.commit()
        return subasta_id

    def _insert_bien(self, bien: Bien):
        """Inserta un bien en la base de datos."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO bienes (
                id_subasta, numero_bien, tipo_bien, subtipo_bien,
                descripcion, direccion, codigo_postal, localidad,
                provincia, provincia_codigo, situacion_posesoria,
                visitable, cargas, valor_tasacion, fotos_urls
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bien.id_subasta,
            bien.numero_bien,
            bien.tipo_bien,
            bien.subtipo_bien,
            bien.descripcion,
            bien.direccion,
            bien.codigo_postal,
            bien.localidad,
            bien.provincia,
            bien.provincia_codigo,
            bien.situacion_posesoria,
            bien.visitable,
            bien.cargas,
            float(bien.valor_tasacion),
            json.dumps(bien.fotos_urls),
        ))

    def update_subasta(self, subasta: Subasta):
        """Actualiza una subasta existente."""
        cursor = self.conn.cursor()

        subasta.hash_datos = subasta.calcular_hash()
        subasta.fecha_actualizacion = datetime.now()

        cursor.execute("""
            UPDATE subastas SET
                tipo_subasta = ?,
                estado = ?,
                cuenta_expediente = ?,
                fecha_inicio = ?,
                fecha_conclusion = ?,
                cantidad_reclamada = ?,
                valor_subasta = ?,
                tasacion = ?,
                puja_minima = ?,
                tramos_pujas = ?,
                importe_deposito = ?,
                anuncio_boe = ?,
                lotes = ?,
                url_detalle = ?,
                url_edicto = ?,
                url_certificacion_cargas = ?,
                autoridad_gestora = ?,
                localidad_juzgado = ?,
                telefono_juzgado = ?,
                fax_juzgado = ?,
                email_juzgado = ?,
                fecha_actualizacion = ?,
                hash_datos = ?,
                activa = ?
            WHERE id_subasta = ?
        """, (
            subasta.tipo_subasta,
            subasta.estado,
            subasta.cuenta_expediente,
            subasta.fecha_inicio.isoformat() if subasta.fecha_inicio else None,
            subasta.fecha_conclusion.isoformat() if subasta.fecha_conclusion else None,
            float(subasta.cantidad_reclamada),
            float(subasta.valor_subasta),
            float(subasta.tasacion),
            float(subasta.puja_minima),
            float(subasta.tramos_pujas),
            float(subasta.importe_deposito),
            subasta.anuncio_boe,
            subasta.lotes,
            subasta.url_detalle,
            subasta.url_edicto,
            subasta.url_certificacion_cargas,
            subasta.autoridad_gestora,
            subasta.localidad_juzgado,
            subasta.telefono_juzgado,
            subasta.fax_juzgado,
            subasta.email_juzgado,
            subasta.fecha_actualizacion.isoformat(),
            subasta.hash_datos,
            1 if subasta.activa else 0,
            subasta.id_subasta,
        ))

        # Actualizar bienes: eliminar existentes e insertar nuevos
        cursor.execute("DELETE FROM bienes WHERE id_subasta = ?", (subasta.id_subasta,))
        for bien in subasta.bienes:
            bien.id_subasta = subasta.id_subasta
            self._insert_bien(bien)

        self.conn.commit()

    def update_wp_post_id(self, id_subasta: str, wp_post_id: int):
        """Actualiza el ID del post de WordPress para una subasta."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE subastas SET
                publicado_wp = 1,
                wp_post_id = ?,
                fecha_actualizacion = ?
            WHERE id_subasta = ?
        """, (wp_post_id, datetime.now().isoformat(), id_subasta))
        self.conn.commit()

    def get_subastas_no_publicadas(self) -> List[Subasta]:
        """Obtiene subastas que no han sido publicadas en WordPress."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM subastas
            WHERE publicado_wp = 0 AND activa = 1
            ORDER BY fecha_scraping DESC
        """)

        subastas = []
        for row in cursor.fetchall():
            subasta = self._row_to_subasta(row)
            subasta.bienes = self._get_bienes(subasta.id_subasta)
            subastas.append(subasta)
        return subastas

    def get_subastas_activas(self) -> List[Subasta]:
        """Obtiene todas las subastas activas."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM subastas WHERE activa = 1
            ORDER BY fecha_conclusion DESC
        """)

        subastas = []
        for row in cursor.fetchall():
            subasta = self._row_to_subasta(row)
            subasta.bienes = self._get_bienes(subasta.id_subasta)
            subastas.append(subasta)
        return subastas

    def get_estadisticas(self) -> dict:
        """Obtiene estadísticas de la base de datos."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM subastas")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM subastas WHERE activa = 1")
        activas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM subastas WHERE publicado_wp = 1")
        publicadas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM bienes")
        total_bienes = cursor.fetchone()[0]

        cursor.execute("""
            SELECT provincia_codigo, COUNT(*) as count
            FROM bienes
            GROUP BY provincia_codigo
        """)
        por_provincia = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "total_subastas": total,
            "subastas_activas": activas,
            "subastas_publicadas": publicadas,
            "total_bienes": total_bienes,
            "por_provincia": por_provincia,
        }

    def log_sync(self, provincia_codigo: str, encontradas: int, nuevas: int,
                 actualizadas: int, publicadas: int, errores: int,
                 duracion: float, mensaje: str = ""):
        """Registra una sincronización en el log."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO sync_log (
                provincia_codigo, subastas_encontradas, subastas_nuevas,
                subastas_actualizadas, subastas_publicadas, errores,
                duracion_segundos, mensaje
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            provincia_codigo,
            encontradas,
            nuevas,
            actualizadas,
            publicadas,
            errores,
            duracion,
            mensaje,
        ))
        self.conn.commit()

    def subasta_existe(self, id_subasta: str) -> bool:
        """Verifica si una subasta existe en la base de datos."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM subastas WHERE id_subasta = ?", (id_subasta,))
        return cursor.fetchone() is not None

    def subasta_cambio(self, id_subasta: str, nuevo_hash: str) -> bool:
        """Verifica si una subasta ha cambiado comparando hashes."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT hash_datos FROM subastas WHERE id_subasta = ?", (id_subasta,))
        row = cursor.fetchone()
        if not row:
            return True  # No existe, es cambio
        return row[0] != nuevo_hash

    def get_subastas_publicadas(self) -> List[Subasta]:
        """Obtiene todas las subastas que han sido publicadas en WordPress."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM subastas
            WHERE publicado_wp = 1 AND wp_post_id IS NOT NULL
            ORDER BY fecha_conclusion DESC
        """)

        subastas = []
        for row in cursor.fetchall():
            subasta = self._row_to_subasta(row)
            subasta.bienes = self._get_bienes(subasta.id_subasta)
            subastas.append(subasta)
        return subastas

    def marcar_subasta_inactiva(self, id_subasta: str, nuevo_estado: str = "Finalizada"):
        """Marca una subasta como inactiva y actualiza su estado."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE subastas SET
                activa = 0,
                estado = ?,
                fecha_actualizacion = ?
            WHERE id_subasta = ?
        """, (nuevo_estado, datetime.now().isoformat(), id_subasta))
        self.conn.commit()

    def get_subastas_para_verificar(self) -> List[dict]:
        """
        Obtiene subastas publicadas que necesitan verificación de estado.
        Retorna solo los campos necesarios para la verificación.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id_subasta, wp_post_id, estado, fecha_conclusion
            FROM subastas
            WHERE publicado_wp = 1 AND wp_post_id IS NOT NULL AND activa = 1
        """)

        subastas = []
        for row in cursor.fetchall():
            subastas.append({
                "id_subasta": row["id_subasta"],
                "wp_post_id": row["wp_post_id"],
                "estado": row["estado"],
                "fecha_conclusion": datetime.fromisoformat(row["fecha_conclusion"]) if row["fecha_conclusion"] else None,
            })
        return subastas
