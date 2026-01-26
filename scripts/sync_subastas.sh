#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Script de sincronización automática de subastas BOE
# Ejecutado cada 6 horas via launchd
# ═══════════════════════════════════════════════════════════════

# Configuración
PROJECT_DIR="/Users/pablofloresavellaneda/subastas-boe-automation"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/sync_$(date +%Y%m%d).log"

# Crear directorio de logs si no existe
mkdir -p "$LOG_DIR"

# Función de logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "═══════════════════════════════════════════════════════════════"
log "INICIANDO SINCRONIZACIÓN AUTOMÁTICA"
log "═══════════════════════════════════════════════════════════════"

# Cambiar al directorio del proyecto
cd "$PROJECT_DIR"

# Verificar que existe el entorno virtual
if [ ! -d "venv" ]; then
    log "ERROR: No se encontró el entorno virtual en $PROJECT_DIR/venv"
    log "Intentando ejecutar sin entorno virtual..."
    PYTHON_CMD="python3"
else
    # Activar entorno virtual
    source venv/bin/activate
    PYTHON_CMD="python3"
    log "Entorno virtual activado"
fi

# Ejecutar sincronización
log "Ejecutando: $PYTHON_CMD cli.py sync --limit 20"
$PYTHON_CMD cli.py sync --limit 20 >> "$LOG_FILE" 2>&1
SYNC_STATUS=$?

if [ $SYNC_STATUS -eq 0 ]; then
    log "✅ Sincronización completada exitosamente"
else
    log "❌ Error en la sincronización (código: $SYNC_STATUS)"
fi

# Limpiar logs antiguos (más de 30 días)
find "$LOG_DIR" -name "sync_*.log" -mtime +30 -delete 2>/dev/null

log "═══════════════════════════════════════════════════════════════"
log "FIN DE SINCRONIZACIÓN"
log "═══════════════════════════════════════════════════════════════"
log ""

# Desactivar entorno virtual si se activó
if [ -d "venv" ]; then
    deactivate 2>/dev/null
fi

exit $SYNC_STATUS
