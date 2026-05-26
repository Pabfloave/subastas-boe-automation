# Setup del entorno de staging (WordPress en Docker)

Decisión D2 del plan: validamos cambios SEO en un WordPress local antes de tocar producción.

## Prerrequisitos
- Docker Desktop (o equivalente) instalado y corriendo.
- Puertos `8080` y `3306` libres en `127.0.0.1`.

## Pasos (una sola vez)

### 1. Levantar el stack
```bash
docker compose up -d
```

Espera ~30 s al primer arranque (descarga de imágenes + setup de MariaDB).

Verifica que los contenedores están sanos:
```bash
docker compose ps
```

### 2. Completar el wizard de WordPress
1. Abre `http://localhost:8080` en el navegador.
2. Idioma: **Español**.
3. Site title: `Subastas BOE (staging)`.
4. Admin: usuario `admin`, contraseña fuerte que recuerdes, email cualquiera.

### 3. Activar el plugin `subastas-meta-api`
Está bind-mounted desde `wordpress/subastas-meta-api.php`. Vé a:
- WP Admin → Plugins → Activa **Subastas Meta API**.

### 4. Instalar Rank Math (decisión D3)
- WP Admin → Plugins → Añadir nuevo → buscar "Rank Math SEO".
- Instalar y activar.
- Saltar el wizard inicial (no es necesario para validar campos meta).

> **No instales Yoast.** El plan elimina los campos `_yoast_wpseo_*` del payload.

### 5. Crear Application Password
1. WP Admin → Usuarios → Tu perfil → bajar hasta "Application Passwords".
2. Name: `subastas-cli`.
3. Click "Add New Application Password".
4. Copia la contraseña generada (con espacios) — la usaremos en `.env.staging`.

> Si el bloque "Application Passwords" no aparece, ejecuta:
> ```bash
> docker compose exec wp wp config set WP_APPLICATION_PASSWORDS_ENABLED true --raw --allow-root
> ```

### 6. Configurar `.env.staging`
Copia el ejemplo y rellena:
```bash
cp .env.staging.example .env.staging
```

Edita con los valores reales:
```
WP_URL=http://localhost:8080
WP_USER=admin
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
WP_POST_STATUS=publish
WP_CONTACT_FORM_URL=http://localhost:8080/#analisis
DB_PATH=./data/subastas-staging.db
```

### 7. Validar conexión
```bash
ENV_FILE=.env.staging python -c "from src.wordpress.client import WordPressClient; print(WordPressClient().test_connection())"
```
Esperado: `True` y log "Conectado a WordPress como: admin".

### 8. Sembrar datos de prueba
Si tienes una BD SQLite con subastas, copia `data/subastas.db` a `data/subastas-staging.db` y publica:
```bash
ENV_FILE=.env.staging python cli.py crear-paginas-provincias
ENV_FILE=.env.staging python cli.py publish-pending --limit 20
```

> **Nota:** el repo todavía no honra `ENV_FILE` automáticamente. De momento, exporta las variables a mano o renombra `.env.staging` → `.env` cuando trabajes en staging. Esto se resolverá en un futuro PR.

## Apagar el stack

```bash
docker compose down       # mantiene los datos
docker compose down -v    # ⚠️ borra MariaDB y wp-content (volúmenes locales en .docker/)
```

## Resetear desde cero

```bash
docker compose down -v
rm -rf .docker/
docker compose up -d
```

Y repite los pasos 2-7.

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Los tests no requieren WordPress activo: usan mocks. El stack Docker solo es necesario para validación end-to-end manual.
