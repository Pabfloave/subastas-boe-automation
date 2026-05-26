# Lead Magnets — Setup técnico

Implementación de los dos lead magnets del plan SEO 2026:

1. **PDF "Checklist 47 puntos antes de pujar"** — gated por email, 24 h de TTL en el enlace de descarga.
2. **Newsletter "Subastas BOE de la semana"** — doble opt-in, envío semanal, unsubscribe en un clic.

> ⚠️ **Antes de pasar a producción debes completar el [RGPD-checklist.md](RGPD-checklist.md)**: política de privacidad, aviso legal y consentimiento explícito.

---

## Arquitectura

```
WP (cafave-lead-magnets plugin)         Python (subastas-boe-automation)
─────────────────────────────────       ─────────────────────────────────
[cafave_checklist_form]    ─────┐
[cafave_newsletter_form]   ─────┤
[cafave_checklist_banner]  ─────┤
                                │
POST /cafave/v1/leads/checklist ──→ wp_cafave_leads (MySQL WP)
GET  /cafave/v1/checklist/download    └── envía email con link de 24h + PDF
POST /cafave/v1/newsletter/subscribe   → wp_cafave_subscribers (MySQL WP)
GET  /cafave/v1/newsletter/confirm       └── doble opt-in
GET  /cafave/v1/newsletter/unsubscribe
GET  /cafave/v1/newsletter/subscribers ←── scripts/send_weekly_newsletter.py
                                            (X-API-Key)
                                            └── lee subastas SQLite local
                                            └── render Jinja2 template
                                            └── SMTP Hostinger → cada subscriber
```

---

## 1. Instalación del plugin WordPress

### 1.1. Subir el plugin

```
wordpress/cafave-lead-magnets.php  →  wp-content/plugins/cafave-lead-magnets/cafave-lead-magnets.php
```

### 1.2. Configurar la API key en `wp-config.php`

Antes de activar el plugin, añade en `wp-config.php` (encima de la línea `/* That's all, stop editing! */`):

```php
// API key compartida con Python (newsletter sender)
define('CAFAVE_LM_API_KEY', 'GENERA_AQUI_UNA_CADENA_LARGA_ALEATORIA');
```

Genera una clave segura, por ejemplo con:

```
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 1.3. Activar el plugin

En el panel WP → **Plugins → Plugins instalados → CAFAVE Lead Magnets → Activar**.

Al activarse, crea automáticamente:

- Tabla `{prefix}cafave_leads` (leads del checklist)
- Tabla `{prefix}cafave_subscribers` (newsletter)
- Directorio `wp-content/uploads/cafave-lead-magnets/` con `.htaccess` que bloquea listado/acceso directo

### 1.4. Subir el PDF

Subir manualmente (vía FTP / cPanel / WP File Manager):

```
content/lead-magnets/checklist-47-puntos.pdf
   →
wp-content/uploads/cafave-lead-magnets/checklist-47-puntos.pdf
```

Permisos: `644`. El `.htaccess` que crea el plugin bloquea el acceso directo; el plugin lo sirve vía endpoint REST con token.

### 1.5. Verificar permalinks

Tras activar el plugin, **vé a Ajustes → Enlaces permanentes → Guardar cambios** (sin cambiar nada). Esto re-registra las rutas REST.

Comprueba que los endpoints existen:

```bash
curl -sS https://comprarensubasta.com/wp-json/cafave/v1/newsletter/subscribers -H "X-API-Key: TU_API_KEY"
# → {"subscribers":[],"count":0}
```

---

## 2. Crear las páginas WP

### 2.1. Página de descarga del checklist

**URL**: `/recursos/checklist-47-puntos`

**Contenido sugerido** (modo "página", no post):

```
<h1>Checklist 47 puntos antes de pujar en una subasta del BOE</h1>

<p>Esta guía recoge las verificaciones jurídicas que nuestro equipo de
abogados realiza antes de autorizar una puja en el Portal de Subastas.</p>

<p>Bloques cubiertos:</p>
<ul>
  <li>Documentación legal (10 puntos)</li>
  <li>Análisis del inmueble (10 puntos)</li>
  <li>Cargas y deudas (8 puntos)</li>
  <li>Aspectos económicos (10 puntos)</li>
  <li>Proceso de puja (9 puntos)</li>
</ul>

[cafave_checklist_form]
```

Configuración Rank Math:
- Title: `Checklist 47 puntos antes de pujar en una subasta BOE (PDF gratis)`
- Meta description: `Descarga gratis el checklist jurídico de 47 puntos que verificamos antes de autorizar una puja en el Portal de Subastas del BOE. PDF de 8 páginas.`
- Focus KW: `checklist subasta judicial`
- **Index**: sí, follow.

### 2.2. Página de la newsletter

**URL**: `/newsletter` (o widget en home)

```
<h1>Subastas BOE de la semana — gratis cada lunes</h1>
<p>Cada lunes a las 9:00 recibirás las 10 subastas judiciales más relevantes
del BOE, con comentario jurídico de nuestro equipo. Sin spam, baja con un clic.</p>

[cafave_newsletter_form]
```

### 2.3. Inyección del banner en posts existentes

El método `_generate_content()` en `src/wordpress/publisher.py` ya inyecta el shortcode `[cafave_checklist_banner]` en cada ficha de subasta. Las **fichas ya publicadas** no se actualizan automáticamente; se actualizarán cuando vuelvan a sincronizarse o ejecutes manualmente:

```bash
python3 cli.py sync --update-content   # si tienes ese flag
```

Para el primer pillar post ("Cargas ocultas"), inserta manualmente al final:

```
[cafave_checklist_banner url="/recursos/checklist-47-puntos"]
```

---

## 3. Build del PDF

```bash
# Una sola vez: instalar deps del sistema
brew install pango libffi gdk-pixbuf       # macOS
# apt install libpango-1.0-0 libpangoft2-1.0-0   # Debian

# Crear venv y deps Python
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Build del PDF (cuando cambies el markdown)
.venv/bin/python3 scripts/build_checklist_pdf.py
```

Output: `content/lead-magnets/checklist-47-puntos.pdf` (≈100 KB, 8 pp). Súbelo a `wp-content/uploads/cafave-lead-magnets/` cada vez que lo regeneres.

---

## 4. Newsletter semanal

### 4.1. Configurar `.env`

Añade a `.env` (en la raíz del proyecto):

```env
# WordPress (ya configurado)
WP_URL=https://comprarensubasta.com

# Plugin API key (debe coincidir con wp-config.php)
CAFAVE_LM_API_KEY=la-misma-clave-larga-aleatoria

# SMTP Hostinger (revisa hPanel → Emails → SMTP)
SMTP_HOST=smtp.hostinger.com
SMTP_PORT=587
SMTP_USER=noreply@comprarensubasta.com
SMTP_PASS=tu-contraseña-smtp
SMTP_FROM=CAFAVE Investment <noreply@comprarensubasta.com>

# Filtros newsletter (opcional)
NEWSLETTER_PRICE_MIN=50000
NEWSLETTER_PRICE_MAX=500000
```

### 4.2. Pruebas

```bash
# Dry-run: renderiza HTML pero NO envía (revisa output en data/newsletters/)
.venv/bin/python3 scripts/send_weekly_newsletter.py --dry-run --test-email tu@email.com

# Envío de test a una sola dirección
.venv/bin/python3 scripts/send_weekly_newsletter.py --test-email tu@email.com

# Envío real (todos los subscribers activos)
.venv/bin/python3 scripts/send_weekly_newsletter.py
```

### 4.3. Cron semanal

Editar crontab del servidor (o local si lo lanzas desde ahí):

```bash
crontab -e
```

Añadir:

```cron
# Newsletter semanal: lunes 9:00
0 9 * * 1 cd /ruta/al/proyecto && /ruta/al/proyecto/.venv/bin/python3 scripts/send_weekly_newsletter.py >> data/logs/newsletter.log 2>&1
```

### 4.4. Verificación

```bash
tail -f data/logs/newsletter.log
```

---

## 5. Promoción del checklist

Después de activar el plugin, las fichas BOE inyectadas por `page_generator` mostrarán el banner. Además:

- **Sidebar global** (recomendado vía widget en `Apariencia → Widgets`):
  Añade un widget de texto con el shortcode `[cafave_checklist_banner]`.

- **Post pillar "Cargas ocultas"** (post-001): cierra con el shortcode antes del aviso final.

- **Pop-up exit-intent** (Sprint posterior — no incluido aquí, requiere plugin como OptinMonster o código JS personalizado).

---

## 6. Mantenimiento

- **Limpiar leads antiguos**: añadir a cron mensual (RGPD: limitación de almacenamiento). Por ejemplo:

  ```sql
  DELETE FROM wp_cafave_leads
   WHERE consentimiento_rgpd = 1
     AND downloaded_at IS NULL
     AND fecha_alta < DATE_SUB(NOW(), INTERVAL 6 MONTH);
  ```

  No bórralos automáticamente sin validar con asesoría legal — algunas obligaciones (prueba de consentimiento) requieren retención.

- **Limpiar subscribers `unsubscribed`** después de 2 años (revisar con asesor de privacidad).

- **Logs**: `data/logs/newsletter.log` se rota manualmente; añadir `logrotate` si crece mucho.

---

## 7. Troubleshooting

### "PDF no disponible. Contacta con soporte."
El plugin no encuentra el archivo en `wp-content/uploads/cafave-lead-magnets/checklist-47-puntos.pdf`. Verifica permisos y existencia.

### "Demasiadas peticiones" (HTTP 429)
Rate limit: 5 submits por IP por hora. Es deliberado anti-spam. Si necesitas otro valor, modifica `CAFAVE_LM_RATE_LIMIT_MAX` en el plugin.

### Emails no llegan
1. Verifica que WP envía emails: `Ajustes → Site Health → Test email`.
2. Confirma SPF/DKIM/DMARC de `comprarensubasta.com` (Hostinger DNS).
3. Para newsletter: revisa logs de Python (`data/logs/newsletter.log`).
4. Considera usar el plugin **WP Mail SMTP** si los envíos transaccionales del checklist no llegan.

### Endpoints 404
Re-guarda permalinks (`Ajustes → Enlaces permanentes → Guardar`).
