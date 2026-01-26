"""
Cliente para la API REST de WordPress.
"""
import base64
import logging
from typing import Dict, List, Optional, Any
import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings


logger = logging.getLogger(__name__)


class WordPressClient:
    """Cliente para interactuar con la API REST de WordPress."""

    def __init__(
        self,
        url: str = None,
        username: str = None,
        app_password: str = None
    ):
        """
        Inicializa el cliente de WordPress.

        Args:
            url: URL base del sitio WordPress
            username: Nombre de usuario
            app_password: Contraseña de aplicación
        """
        self.base_url = (url or settings.WP_URL).rstrip("/")
        self.api_url = f"{self.base_url}/wp-json/wp/v2"
        self.username = username or settings.WP_USER
        self.app_password = app_password or settings.WP_APP_PASSWORD

        # Crear header de autenticación
        credentials = f"{self.username}:{self.app_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        }

        # Cache de categorías y tags
        self._categories_cache: Dict[str, int] = {}
        self._tags_cache: Dict[str, int] = {}

    def test_connection(self) -> bool:
        """
        Prueba la conexión a WordPress.

        Returns:
            True si la conexión es exitosa
        """
        try:
            # Probar primero /users/me, si falla probar /posts
            response = requests.get(
                f"{self.api_url}/users/me",
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"Conectado a WordPress como: {user_data.get('name', 'Usuario')}")
                return True
            elif response.status_code == 403:
                # El endpoint /users/me puede estar bloqueado por seguridad
                # Probar con el endpoint de posts
                response = requests.get(
                    f"{self.api_url}/posts",
                    headers=self.headers,
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info("Conectado a WordPress (endpoint /users/me bloqueado, pero API funcional)")
                    return True
                else:
                    logger.error(f"Error de autenticación: {response.status_code}")
                    return False
            else:
                logger.error(f"Error de autenticación: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Error de conexión a WordPress: {e}")
            return False

    def create_post(
        self,
        title: str,
        content: str,
        status: str = "publish",
        categories: List[int] = None,
        tags: List[int] = None,
        meta: Dict[str, Any] = None,
        featured_media: int = None
    ) -> Dict:
        """
        Crea un nuevo post en WordPress.

        Args:
            title: Título del post
            content: Contenido HTML del post
            status: Estado (publish, draft, pending)
            categories: Lista de IDs de categorías
            tags: Lista de IDs de tags
            meta: Campos meta personalizados
            featured_media: ID de imagen destacada

        Returns:
            Datos del post creado
        """
        data = {
            "title": title,
            "content": content,
            "status": status,
        }

        if categories:
            data["categories"] = categories
        if tags:
            data["tags"] = tags
        if meta:
            data["meta"] = meta
        if featured_media:
            data["featured_media"] = featured_media

        response = requests.post(
            f"{self.api_url}/posts",
            headers=self.headers,
            json=data,
            timeout=30
        )

        if response.status_code in (200, 201):
            post_data = response.json()
            logger.info(f"Post creado: ID {post_data['id']} - {title}")
            return post_data
        else:
            logger.error(f"Error creando post: {response.status_code} - {response.text}")
            response.raise_for_status()

    def update_post(self, post_id: int, data: Dict) -> Dict:
        """
        Actualiza un post existente.

        Args:
            post_id: ID del post
            data: Datos a actualizar

        Returns:
            Datos del post actualizado
        """
        response = requests.put(
            f"{self.api_url}/posts/{post_id}",
            headers=self.headers,
            json=data,
            timeout=30
        )

        if response.status_code == 200:
            post_data = response.json()
            logger.info(f"Post actualizado: ID {post_id}")
            return post_data
        else:
            logger.error(f"Error actualizando post: {response.status_code}")
            response.raise_for_status()

    def get_post_by_meta(self, meta_key: str, meta_value: str) -> Optional[Dict]:
        """
        Busca un post por un campo meta.

        Args:
            meta_key: Nombre del campo meta
            meta_value: Valor a buscar

        Returns:
            Datos del post o None si no existe
        """
        # WordPress REST API no soporta búsqueda por meta directamente
        # Necesitamos buscar y filtrar
        response = requests.get(
            f"{self.api_url}/posts",
            headers=self.headers,
            params={
                "per_page": 100,
                "status": "any",
            },
            timeout=30
        )

        if response.status_code == 200:
            posts = response.json()
            for post in posts:
                meta = post.get("meta", {})
                if meta.get(meta_key) == meta_value:
                    return post

        return None

    def get_or_create_category(self, name: str, slug: str = None, parent: int = None) -> int:
        """
        Obtiene o crea una categoría.

        Args:
            name: Nombre de la categoría
            slug: Slug (opcional)
            parent: ID de categoría padre (opcional)

        Returns:
            ID de la categoría
        """
        # Verificar cache
        cache_key = f"{name}_{parent}"
        if cache_key in self._categories_cache:
            return self._categories_cache[cache_key]

        # Buscar categoría existente
        params = {"search": name, "per_page": 100}
        if parent:
            params["parent"] = parent

        response = requests.get(
            f"{self.api_url}/categories",
            headers=self.headers,
            params=params,
            timeout=15
        )

        if response.status_code == 200:
            categories = response.json()
            for cat in categories:
                if cat["name"].lower() == name.lower():
                    self._categories_cache[cache_key] = cat["id"]
                    return cat["id"]

        # Crear nueva categoría
        data = {"name": name}
        if slug:
            data["slug"] = slug
        if parent:
            data["parent"] = parent

        response = requests.post(
            f"{self.api_url}/categories",
            headers=self.headers,
            json=data,
            timeout=15
        )

        if response.status_code in (200, 201):
            cat_id = response.json()["id"]
            self._categories_cache[cache_key] = cat_id
            logger.info(f"Categoría creada: {name} (ID: {cat_id})")
            return cat_id
        else:
            logger.error(f"Error creando categoría {name}: {response.status_code}")
            return 0

    def get_or_create_tag(self, name: str, slug: str = None) -> int:
        """
        Obtiene o crea un tag.

        Args:
            name: Nombre del tag
            slug: Slug (opcional)

        Returns:
            ID del tag
        """
        # Verificar cache
        if name in self._tags_cache:
            return self._tags_cache[name]

        # Buscar tag existente
        response = requests.get(
            f"{self.api_url}/tags",
            headers=self.headers,
            params={"search": name, "per_page": 100},
            timeout=15
        )

        if response.status_code == 200:
            tags = response.json()
            for tag in tags:
                if tag["name"].lower() == name.lower():
                    self._tags_cache[name] = tag["id"]
                    return tag["id"]

        # Crear nuevo tag
        data = {"name": name}
        if slug:
            data["slug"] = slug

        response = requests.post(
            f"{self.api_url}/tags",
            headers=self.headers,
            json=data,
            timeout=15
        )

        if response.status_code in (200, 201):
            tag_id = response.json()["id"]
            self._tags_cache[name] = tag_id
            logger.info(f"Tag creado: {name} (ID: {tag_id})")
            return tag_id
        else:
            logger.error(f"Error creando tag {name}: {response.status_code}")
            return 0

    def upload_media(self, file_path: str, title: str = None) -> Optional[int]:
        """
        Sube un archivo a la biblioteca de medios.

        Args:
            file_path: Ruta al archivo
            title: Título del archivo (opcional)

        Returns:
            ID del archivo subido o None
        """
        import os
        import mimetypes

        if not os.path.exists(file_path):
            logger.error(f"Archivo no encontrado: {file_path}")
            return None

        filename = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)

        headers = self.headers.copy()
        headers["Content-Type"] = mime_type or "application/octet-stream"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        with open(file_path, "rb") as f:
            response = requests.post(
                f"{self.api_url}/media",
                headers=headers,
                data=f,
                timeout=60
            )

        if response.status_code in (200, 201):
            media_id = response.json()["id"]
            logger.info(f"Archivo subido: {filename} (ID: {media_id})")
            return media_id
        else:
            logger.error(f"Error subiendo archivo: {response.status_code}")
            return None

    def get_categories(self) -> List[Dict]:
        """Obtiene todas las categorías."""
        response = requests.get(
            f"{self.api_url}/categories",
            headers=self.headers,
            params={"per_page": 100},
            timeout=15
        )

        if response.status_code == 200:
            return response.json()
        return []

    def get_tags(self) -> List[Dict]:
        """Obtiene todos los tags."""
        response = requests.get(
            f"{self.api_url}/tags",
            headers=self.headers,
            params={"per_page": 100},
            timeout=15
        )

        if response.status_code == 200:
            return response.json()
        return []

    def unpublish_post(self, post_id: int) -> bool:
        """
        Despublica un post (lo pasa a borrador).

        Args:
            post_id: ID del post

        Returns:
            True si se despublicó correctamente
        """
        try:
            response = requests.put(
                f"{self.api_url}/posts/{post_id}",
                headers=self.headers,
                json={"status": "draft"},
                timeout=30
            )

            if response.status_code == 200:
                logger.info(f"Post despublicado: ID {post_id}")
                return True
            else:
                logger.error(f"Error despublicando post {post_id}: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Error de conexión despublicando post {post_id}: {e}")
            return False

    def get_post(self, post_id: int) -> Optional[Dict]:
        """
        Obtiene un post por su ID.

        Args:
            post_id: ID del post

        Returns:
            Datos del post o None si no existe
        """
        try:
            response = requests.get(
                f"{self.api_url}/posts/{post_id}",
                headers=self.headers,
                params={"status": "any"},
                timeout=15
            )

            if response.status_code == 200:
                return response.json()
            return None

        except requests.RequestException as e:
            logger.error(f"Error obteniendo post {post_id}: {e}")
            return None
