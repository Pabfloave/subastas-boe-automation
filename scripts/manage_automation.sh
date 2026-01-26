#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Gestión de la automatización de subastas BOE
# Uso: ./manage_automation.sh [comando]
# ═══════════════════════════════════════════════════════════════

PLIST_PATH="$HOME/Library/LaunchAgents/com.cafave.subastas-boe.plist"
SERVICE_NAME="com.cafave.subastas-boe"
PROJECT_DIR="$HOME/subastas-boe-automation"

show_help() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  GESTIÓN DE AUTOMATIZACIÓN - SUBASTAS BOE"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "Uso: $0 [comando]"
    echo ""
    echo "Comandos disponibles:"
    echo "  status    - Ver estado del servicio"
    echo "  start     - Iniciar/reactivar el servicio"
    echo "  stop      - Pausar el servicio"
    echo "  restart   - Reiniciar el servicio"
    echo "  run       - Ejecutar sincronización manualmente AHORA"
    echo "  logs      - Ver logs de las últimas ejecuciones"
    echo "  logs-live - Ver logs en tiempo real"
    echo "  help      - Mostrar esta ayuda"
    echo ""
}

case "$1" in
    status)
        echo "═══════════════════════════════════════════════════════════════"
        echo "  ESTADO DEL SERVICIO"
        echo "═══════════════════════════════════════════════════════════════"
        if launchctl list | grep -q "$SERVICE_NAME"; then
            echo "✅ Servicio ACTIVO"
            launchctl list | grep "$SERVICE_NAME"
            echo ""
            echo "Próximas ejecuciones programadas: 0:00, 6:00, 12:00, 18:00"
        else
            echo "❌ Servicio INACTIVO"
        fi
        echo ""
        echo "Últimos logs:"
        echo "─────────────────────────────────────────────────────────────────"
        tail -20 "$PROJECT_DIR/logs/sync_$(date +%Y%m%d).log" 2>/dev/null || echo "No hay logs de hoy"
        ;;

    start)
        echo "Iniciando servicio..."
        launchctl load "$PLIST_PATH" 2>/dev/null
        if launchctl list | grep -q "$SERVICE_NAME"; then
            echo "✅ Servicio iniciado correctamente"
        else
            echo "❌ Error al iniciar el servicio"
        fi
        ;;

    stop)
        echo "Pausando servicio..."
        launchctl unload "$PLIST_PATH" 2>/dev/null
        if ! launchctl list | grep -q "$SERVICE_NAME"; then
            echo "✅ Servicio pausado correctamente"
        else
            echo "❌ Error al pausar el servicio"
        fi
        ;;

    restart)
        echo "Reiniciando servicio..."
        launchctl unload "$PLIST_PATH" 2>/dev/null
        sleep 1
        launchctl load "$PLIST_PATH" 2>/dev/null
        if launchctl list | grep -q "$SERVICE_NAME"; then
            echo "✅ Servicio reiniciado correctamente"
        else
            echo "❌ Error al reiniciar el servicio"
        fi
        ;;

    run)
        echo "═══════════════════════════════════════════════════════════════"
        echo "  EJECUTANDO SINCRONIZACIÓN MANUAL"
        echo "═══════════════════════════════════════════════════════════════"
        "$PROJECT_DIR/scripts/sync_subastas.sh"
        ;;

    logs)
        echo "═══════════════════════════════════════════════════════════════"
        echo "  ÚLTIMOS LOGS DE SINCRONIZACIÓN"
        echo "═══════════════════════════════════════════════════════════════"
        # Mostrar logs de los últimos 3 días
        for i in 0 1 2; do
            LOG_DATE=$(date -v-${i}d +%Y%m%d)
            LOG_FILE="$PROJECT_DIR/logs/sync_${LOG_DATE}.log"
            if [ -f "$LOG_FILE" ]; then
                echo ""
                echo "─── $(date -v-${i}d '+%d de %B de %Y') ───"
                cat "$LOG_FILE"
            fi
        done
        ;;

    logs-live)
        echo "═══════════════════════════════════════════════════════════════"
        echo "  LOGS EN TIEMPO REAL (Ctrl+C para salir)"
        echo "═══════════════════════════════════════════════════════════════"
        tail -f "$PROJECT_DIR/logs/sync_$(date +%Y%m%d).log" "$PROJECT_DIR/logs/launchd_stdout.log" 2>/dev/null
        ;;

    help|--help|-h|"")
        show_help
        ;;

    *)
        echo "Comando no reconocido: $1"
        show_help
        exit 1
        ;;
esac
