# Sistema de Automatización de Subastas BOE

Sistema automatizado para extraer subastas de inmuebles del portal del BOE (Boletín Oficial del Estado) y publicarlas en WordPress.

## Características

- **Scraping automático** del portal subastas.boe.es
- **Filtrado por provincias** de Andalucía (Sevilla, Cádiz, Huelva, Córdoba, Málaga, Granada, Jaén, Almería)
- **Almacenamiento local** en SQLite
- **Publicación automática** en WordPress via REST API
- **Detección de duplicados** y actualizaciones
- **CLI completo** para gestión y monitoreo

## Requisitos

- Python 3.9+
- Google Chrome (para Selenium)
- Cuenta WordPress con Application Password

## Instalación

```bash
# Clonar o copiar el proyecto
cd ~/subastas-boe-automation

# Ejecutar instalación
python setup.py

# O manualmente:
pip install -r requirements.txt
```

## Configuración

Edita el archivo `.env` con tus credenciales:

```env
WP_URL=https://tu-sitio-wordpress.com
WP_USER=tu_usuario
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

## Uso

### Comandos principales

```bash
# Probar conexiones
python cli.py test

# Ver estado del sistema
python cli.py status

# Sincronizar todas las provincias
python cli.py sync

# Sincronizar solo una provincia (ej: Sevilla = 41)
python cli.py sync -p 41

# Modo simulación (no guarda ni publica)
python cli.py sync --dry-run

# Limitar número de subastas
python cli.py sync --limit 5

# Generar reporte
python cli.py report
```

### Códigos de provincia

| Código | Provincia |
|--------|-----------|
| 04 | Almería |
| 11 | Cádiz |
| 14 | Córdoba |
| 18 | Granada |
| 21 | Huelva |
| 23 | Jaén |
| 29 | Málaga |
| 41 | Sevilla |

## Automatización con Cron

Para ejecutar automáticamente cada 6 horas:

```bash
# Editar crontab
crontab -e

# Añadir línea:
0 */6 * * * cd ~/subastas-boe-automation && /usr/bin/python3 cli.py sync >> data/logs/cron.log 2>&1
```

## Estructura del proyecto

```
subastas-boe-automation/
├── config/
│   ├── settings.py      # Configuración general
│   └── provinces.py     # Códigos de provincias
├── src/
│   ├── scraper/         # Scraping del BOE
│   ├── models/          # Modelos de datos y BD
│   ├── wordpress/       # Cliente WordPress
│   └── utils/           # Utilidades
├── data/
│   ├── subastas.db      # Base de datos SQLite
│   └── logs/            # Archivos de log
├── cli.py               # Interfaz de línea de comandos
├── main.py              # Entry point principal
├── requirements.txt     # Dependencias
└── .env                 # Configuración (no compartir)
```

## Logs

Los logs se guardan en `data/logs/` con rotación automática:

- `scraper_YYYYMM.log` - Logs del scraper
- `wordpress_YYYYMM.log` - Logs de publicación
- `sync_YYYYMM.log` - Logs de sincronización

## Solución de problemas

### Error de conexión al BOE

```bash
# Verificar que Chrome está instalado
google-chrome --version

# Probar conexión
python cli.py test --boe
```

### Error de autenticación WordPress

```bash
# Verificar credenciales en .env
# Asegúrate de usar Application Password, no la contraseña normal

# Probar conexión
python cli.py test --wordpress
```

### Base de datos corrupta

```bash
# Reinicializar base de datos (⚠️ borra todos los datos)
python cli.py init-db --reset
```

## Licencia

Proyecto privado - Todos los derechos reservados.
