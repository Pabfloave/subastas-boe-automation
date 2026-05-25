"""
Genera el PDF de muestra anonimizado del Informe Jurídico de Viabilidad de Subasta.

Basado en el informe real EJH 50/2022 (Ramón Poza Pobra) — datos personales
sustituidos por placeholders. Mantiene caso, normativa, metodología y cálculos
para demostrar profundidad analítica. Watermark "MUESTRA" + banner demostrativo
en cada página para evitar uso fraudulento o sustitución por IA.

Output: /tmp/muestra-informe-juridico-subasta.pdf
"""
import sys
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether,
)
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT

OUT_PATH = "/tmp/muestra-informe-juridico-subasta.pdf"

# ===================== PALETA Y ESTILOS =====================
NAVY     = colors.HexColor("#1e3a8a")
NAVY_DK  = colors.HexColor("#0f172a")
GOLD     = colors.HexColor("#c9a14a")
GREEN_BG = colors.HexColor("#d1fae5")
GREEN_BR = colors.HexColor("#10b981")
GREEN_TX = colors.HexColor("#065f46")
YEL_BG   = colors.HexColor("#fef3c7")
YEL_BR   = colors.HexColor("#f59e0b")
YEL_TX   = colors.HexColor("#78350f")
RED_BG   = colors.HexColor("#fee2e2")
RED_BR   = colors.HexColor("#dc2626")
RED_TX   = colors.HexColor("#7f1d1d")
GREY_HD  = colors.HexColor("#e5e7eb")
GREY_TX  = colors.HexColor("#64748b")
BODY     = colors.HexColor("#1f2937")

styles = getSampleStyleSheet()
# Sobreescritura limpia: usar nombres únicos
def style(name, **kw):
    base = dict(fontName="Helvetica", fontSize=10, leading=14, textColor=BODY, alignment=TA_JUSTIFY)
    base.update(kw)
    return ParagraphStyle(name=name, **base)

S_TITLE     = style("title",     fontName="Helvetica-Bold", fontSize=22, leading=26, alignment=TA_CENTER, textColor=NAVY)
S_SUBTITLE  = style("subtitle",  fontName="Helvetica",      fontSize=12, leading=16, alignment=TA_CENTER, textColor=GREY_TX)
S_BRAND     = style("brand",     fontName="Helvetica-Bold", fontSize=22, leading=26, alignment=TA_CENTER, textColor=NAVY)
S_BRAND_SUB = style("brandsub",  fontName="Helvetica-Oblique", fontSize=10, leading=14, alignment=TA_CENTER, textColor=GOLD)
S_H1        = style("h1",        fontName="Helvetica-Bold", fontSize=15, leading=20, textColor=NAVY,    spaceBefore=4, spaceAfter=10)
S_H2        = style("h2",        fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=NAVY_DK, spaceBefore=8, spaceAfter=6)
S_BODY      = style("body",      fontSize=10, leading=14)
S_BODY_C    = style("body_c",    fontSize=10, leading=14, alignment=TA_CENTER)
S_CALLOUT_G = style("callout_g", fontSize=9.5, leading=13, textColor=GREEN_TX)
S_CALLOUT_Y = style("callout_y", fontSize=9.5, leading=13, textColor=YEL_TX)
S_CALLOUT_R = style("callout_r", fontSize=9.5, leading=13, textColor=RED_TX)
S_NOTE      = style("note",      fontSize=9, leading=12, textColor=GREY_TX, fontName="Helvetica-Oblique")
S_CONFID    = style("confid",    fontSize=11, leading=14, alignment=TA_CENTER, textColor=RED_TX, fontName="Helvetica-Bold")
S_FIRMA     = style("firma",     fontSize=10, leading=14, alignment=TA_CENTER, fontName="Helvetica-Bold", textColor=NAVY_DK)

# ===================== HEADER / FOOTER / WATERMARK =====================
def on_page(canv: canvas.Canvas, doc):
    """Header, footer y watermark diagonal MUESTRA en cada página."""
    canv.saveState()
    w, h = A4

    # --- Header gris superior derecho con marca y referencia ---
    canv.setFont("Helvetica-Bold", 8.5)
    canv.setFillColor(NAVY_DK)
    canv.drawRightString(w - 2*cm, h - 1.4*cm, "CAFAVE INVESTMENT")
    canv.setFont("Helvetica", 8.5)
    canv.setFillColor(GREY_TX)
    canv.drawRightString(w - 2*cm + 0*cm, h - 1.4*cm, "")  # placeholder
    canv.drawRightString(w - 2*cm, h - 1.75*cm, "Informe Jurídico EJH [XX/AAAA] · MUESTRA DEMOSTRATIVA")
    # Línea dorada
    canv.setStrokeColor(GOLD)
    canv.setLineWidth(0.8)
    canv.line(2*cm, h - 2.05*cm, w - 2*cm, h - 2.05*cm)

    # --- Banner rojo bajo el header: DOCUMENTO DEMOSTRATIVO ---
    canv.setFillColor(RED_BG)
    canv.setStrokeColor(RED_BR)
    canv.setLineWidth(1)
    canv.rect(2*cm, h - 2.55*cm, w - 4*cm, 0.42*cm, fill=1, stroke=1)
    canv.setFillColor(RED_TX)
    canv.setFont("Helvetica-Bold", 8)
    canv.drawCentredString(
        w/2, h - 2.43*cm,
        "DOCUMENTO DEMOSTRATIVO  ·  No constituye informe jurídico contratado  ·  Datos anonimizados sobre caso real"
    )

    # --- Watermark diagonal "MUESTRA" ---
    canv.saveState()
    canv.translate(w/2, h/2)
    canv.rotate(35)
    canv.setFont("Helvetica-Bold", 90)
    canv.setFillColor(colors.HexColor("#dbeafe"))
    canv.setFillAlpha(0.30)
    canv.drawCentredString(0, 0, "MUESTRA")
    canv.setFont("Helvetica-Bold", 28)
    canv.drawCentredString(0, -50, "CAFAVE INVESTMENT")
    canv.restoreState()

    # --- Footer ---
    canv.setStrokeColor(GREY_HD)
    canv.setLineWidth(0.5)
    canv.line(2*cm, 1.5*cm, w - 2*cm, 1.5*cm)
    canv.setFillColor(GREY_TX)
    canv.setFont("Helvetica", 8)
    canv.drawString(2*cm, 1.15*cm, "MUESTRA DEMOSTRATIVA · CAFAVE INVESTMENT · D. ████████████████████████, ICAS nº ██████")
    canv.drawRightString(w - 2*cm, 1.15*cm, f"Página {doc.page}")
    canv.drawCentredString(w/2, 0.78*cm, "https://comprarensubasta.com/informe-juridico-subasta/")

    canv.restoreState()


# ===================== HELPERS DE COMPOSICIÓN =====================
def kv_table(rows, label_w=5.0*cm, value_w=10.5*cm, label_bg=NAVY, label_fg=colors.white):
    """Tabla de pares clave/valor (cabecera azul a la izquierda, valor a la derecha)."""
    data = [[Paragraph(f"<b>{k}</b>", style("kv_label", fontName="Helvetica-Bold", fontSize=9.5, leading=12, textColor=label_fg)),
             Paragraph(v, style("kv_val", fontSize=9.5, leading=12, textColor=BODY))] for k, v in rows]
    t = Table(data, colWidths=[label_w, value_w])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), label_bg),
        ("BACKGROUND", (1,0), (1,-1), colors.white),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LINEBELOW", (0,0), (-1,-2), 0.5, GREY_HD),
        ("BOX", (0,0), (-1,-1), 0.5, GREY_HD),
    ]))
    return t


def data_table(header, rows, col_widths=None, header_bg=NAVY_DK, header_fg=colors.white, highlight_last=False):
    """Tabla con cabecera oscura y filas de datos."""
    head_paras = [Paragraph(f"<b>{c}</b>", style("th", fontName="Helvetica-Bold", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=header_fg)) for c in header]
    body_rows = []
    for r in rows:
        body_rows.append([Paragraph(str(c), style("td", fontSize=9.5, leading=12, alignment=TA_CENTER)) for c in r])
    data = [head_paras] + body_rows
    t = Table(data, colWidths=col_widths)
    cmds = [
        ("BACKGROUND", (0,0), (-1,0), header_bg),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ("BOX", (0,0), (-1,-1), 0.5, GREY_HD),
        ("LINEBELOW", (0,0), (-1,0), 0.5, NAVY),
    ]
    if highlight_last:
        cmds.append(("BACKGROUND", (0,-1), (-1,-1), YEL_BG))
        cmds.append(("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"))
    t.setStyle(TableStyle(cmds))
    return t


def callout(text, kind="green"):
    """Recuadro coloreado tipo bandera."""
    bg, br, tx_style = {
        "green":  (GREEN_BG, GREEN_BR, S_CALLOUT_G),
        "yellow": (YEL_BG,   YEL_BR,   S_CALLOUT_Y),
        "red":    (RED_BG,   RED_BR,   S_CALLOUT_R),
    }[kind]
    para = Paragraph(text, tx_style)
    t = Table([[para]], colWidths=[16.5*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("LINEBEFORE", (0,0), (0,-1), 3, br),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    return t


def section_header(num, title):
    """H1 numerado tipo '1. OBJETO DEL INFORME' con línea dorada."""
    p = Paragraph(f"{num}. {title.upper()}", S_H1)
    line = Table([[""]], colWidths=[16.5*cm], rowHeights=[2])
    line.setStyle(TableStyle([("LINEBELOW", (0,0), (-1,-1), 1.2, GOLD)]))
    return KeepTogether([p, line, Spacer(1, 8)])


# ===================== CONTENIDO ANONIMIZADO =====================
def build_story():
    story = []

    # ============== PORTADA ==============
    story.append(Spacer(1, 3.5*cm))
    story.append(Paragraph("CAFAVE INVESTMENT", S_BRAND))
    story.append(Paragraph("Asesoramiento Jurídico en Inversiones Inmobiliarias", S_BRAND_SUB))
    story.append(Spacer(1, 0.4*cm))
    line = Table([[""]], colWidths=[16.5*cm], rowHeights=[2])
    line.setStyle(TableStyle([("LINEBELOW", (0,0), (-1,-1), 1.2, GOLD)]))
    story.append(line)
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("INFORME JURÍDICO", S_TITLE))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("ANÁLISIS DE VIABILIDAD DE PARTICIPACIÓN EN SUBASTA JUDICIAL", S_SUBTITLE))
    story.append(Spacer(1, 1.5*cm))

    portada_data = [
        ("Procedimiento:",     "Ejecución Hipotecaria n.º [XX/AAAA]"),
        ("Órgano Judicial:",   "Tribunal de Instancia, Plaza [X], [Localidad de la provincia] (A Coruña)"),
        ("Solicitante:",       "D. [Solicitante del informe]"),
        ("Fecha del Informe:", "[Fecha de emisión del informe contratado]"),
        ("Letrado:",           "D. ████████████████████████ — ICAS n.º ██████"),
    ]
    story.append(kv_table(portada_data, label_w=4.5*cm, value_w=11*cm))
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("DOCUMENTO CONFIDENCIAL", S_CONFID))
    story.append(Paragraph(
        "Este informe ha sido elaborado exclusivamente para uso del solicitante.",
        style("portada_note", fontSize=9.5, leading=13, alignment=TA_CENTER, textColor=GREY_TX, fontName="Helvetica-Oblique")
    ))
    story.append(PageBreak())

    # ============== 1. OBJETO ==============
    story.append(section_header("1", "Objeto del informe"))
    story.append(Paragraph(
        "El presente informe tiene por objeto el análisis jurídico integral de la viabilidad de participación "
        "de <b>D. [Solicitante]</b> como postor en la subasta judicial derivada del procedimiento de "
        "Ejecución Hipotecaria n.º [XX/AAAA], tramitado ante el Tribunal de Instancia, Plaza [X] de "
        "[Localidad] (A Coruña), con especial atención a las cargas registrales que pudieran subsistir "
        "tras la adjudicación, la situación urbanística del inmueble y la estimación de costes asociados "
        "a la adquisición.",
        S_BODY
    ))
    story.append(Spacer(1, 1*cm))

    # ============== 2. IDENTIFICACIÓN DE LA FINCA ==============
    story.append(section_header("2", "Identificación de la finca"))
    finca_data = [
        ("Ubicación:",                "C/ [Vía pública], n.º [X], planta [X.ª], puerta [X], Urbanización [Nombre]"),
        ("Localidad:",                "Pobra do Caramiñal (A Coruña)"),
        ("Registro:",                 "Registro de la Propiedad de Noia"),
        ("Finca Registral:",          "N.º [X.XXX]"),
        ("Tomo:",                     "[XXX]"),
        ("Libro:",                    "[XXX]"),
        ("Folio:",                    "[XX]"),
        ("Tipología:",                "Vivienda de Protección Oficial (VPO) – Promoción privada"),
        ("Calificación Definitiva:",  "20 de septiembre de 1999 (Expte. [XX-X-XXXX/XX])"),
        ("Sup. Construida (Registro):", "97,60 m²"),
        ("Sup. Útil:",                "85,85 m²"),
        ("Sup. Total (con elementos comunes):", "111 m² aproximadamente"),
        ("Año de Construcción:",      "1999"),
    ]
    story.append(kv_table(finca_data))
    story.append(Spacer(1, 0.6*cm))

    # ============== 3. TITULARIDAD ==============
    story.append(section_header("3", "Titularidad"))
    titularidad_data = [
        ("Titular Registral:",  "D. [Titular Registral]"),
        ("NIF:",                "[XXXXXXXXX]"),
        ("Porcentaje:",         "100% del pleno dominio con carácter privativo"),
        ("Régimen Económico:",  "Separación de bienes"),
        ("Título Adquisitivo:", "Compraventa"),
        ("Fecha Adquisición:",  "1 de octubre de 1999"),
    ]
    story.append(kv_table(titularidad_data))
    story.append(PageBreak())

    # ============== 4. CARGAS REGISTRALES ==============
    story.append(section_header("4", "Análisis de cargas registrales"))
    story.append(Paragraph(
        "A continuación, se detallan las inscripciones y anotaciones vigentes según la información "
        "registral disponible, con indicación de su rango, naturaleza y efectos sobre el posible adjudicatario.",
        S_BODY
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("4.1. Hipoteca · Inscripción 2.ª (29 de abril de 1999)", S_H2))
    hip_data = [
        ("Acreedor Original:",         "Caja de Ahorros y Monte de Piedad de Madrid (Caja Madrid)"),
        ("Acreedor Actual:",           "Caixabank, S.A. (sucesora por fusión vía Bankia, S.A.)"),
        ("Inscripción de Cesión:",     "Inscripción 5.ª, de 1 de septiembre de 2021"),
        ("Capital:",                   "Aproximadamente 43.793,00 €"),
        ("Tipo de Interés:",           "4,64962% nominal anual"),
        ("Cobertura Hipotecaria – Intereses:", "18 meses de intereses remuneratorios + 24 meses de intereses de demora (máx. 13%)"),
        ("Cobertura Hipotecaria – Costas:", "6.556,19 €"),
    ]
    story.append(kv_table(hip_data))
    story.append(Spacer(1, 0.3*cm))
    story.append(callout(
        "<b>ESTA ES LA HIPOTECA EJECUTADA.</b> Se cancelará de pleno derecho con la adjudicación "
        "conforme al artículo 674.2 de la Ley de Enjuiciamiento Civil, sin que el adjudicatario "
        "deba asumir cantidad alguna por este concepto.",
        kind="green"
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("4.2. Derecho de Uso y Disfrute · Inscripción 4.ª (4 de enero de 2016)", S_H2))
    uso_data = [
        ("Beneficiaria:", "D.ª [Beneficiaria de derecho de uso]"),
        ("Naturaleza:",   "Derecho de uso y disfrute de la vivienda familiar"),
        ("Origen:",       "Sentencia de divorcio – Juzgado de 1.ª Instancia de [Localidad], Procedimiento n.º [XXX/AAAA]"),
        ("Rango:",        "POSTERIOR a la hipoteca ejecutada"),
    ]
    story.append(kv_table(uso_data))
    story.append(Spacer(1, 0.3*cm))
    story.append(callout(
        "<b>EFECTO:</b> Al ser de rango POSTERIOR a la hipoteca ejecutada, se CANCELARÁ "
        "registralmente con la adjudicación (art. 674.2 LEC). Sin embargo, la posible ocupación "
        "física de la vivienda por la beneficiaria constituye un riesgo operativo relevante que "
        "puede requerir procedimiento de lanzamiento judicial.",
        kind="yellow"
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("4.3. Afección Fiscal · Anotación de 31 de agosto de 2021", S_H2))
    story.append(Paragraph(
        "Consta anotada la afección fiscal por el Impuesto sobre Transmisiones Patrimoniales y "
        "Actos Jurídicos Documentados (ITPAJD), con plazo de caducidad de cinco años. Se trata "
        "de una afección estándar de riesgo bajo, vinculada a la inscripción de la sucesión "
        "hipotecaria a favor de Caixabank, S.A.",
        S_BODY
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("4.4. Resumen de Cargas", S_H2))
    resumen_cargas = [
        ["Carga", "Rango", "Efecto", "Asume Postor"],
        ["Hipoteca (Caixabank)", "Es la ejecutada", "Se cancela", "NO"],
        ["Derecho de uso",       "Posterior",       "Se cancela", "NO"],
        ["Afección fiscal ITPAJD","Posterior",       "Caduca",     "NO"],
    ]
    t = data_table(resumen_cargas[0], resumen_cargas[1:], col_widths=[5*cm, 4*cm, 4*cm, 3.5*cm])
    # Colorear celda "NO" en verde
    t.setStyle(TableStyle([
        ("TEXTCOLOR", (3,1), (3,-1), GREEN_BR),
        ("FONTNAME", (3,1), (3,-1), "Helvetica-Bold"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*cm))
    story.append(callout(
        "<b>CONCLUSIÓN:</b> NO EXISTEN CARGAS ANTERIORES NI PREFERENTES a la hipoteca ejecutada. "
        "El adjudicatario NO asumirá carga registral alguna. Todas las inscripciones posteriores "
        "serán canceladas con la adjudicación.",
        kind="green"
    ))
    story.append(PageBreak())

    # ============== 5. RÉGIMEN VPO ==============
    story.append(section_header("5", "Régimen de Protección Oficial (VPO) — Análisis"))
    story.append(callout(
        "Tras investigación exhaustiva de la normativa estatal y autonómica aplicable, se concluye "
        "que el régimen de protección de la vivienda <b>NO HA EXPIRADO</b> y no lo hará hasta el "
        "20 de septiembre de 2029.",
        kind="red"
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("5.1. Datos de la Calificación", S_H2))
    vpo_data = [
        ("Tipo:",                  "Vivienda de Protección Oficial – Promoción Privada"),
        ("Calificación Definitiva:","20 de septiembre de 1999"),
        ("Expediente:",            "[XX-X-XXXX/XX]"),
        ("Normativa de Calificación:", "Plan de Vivienda 1996-1999 (RD 2190/1995) o Plan 1998-2001 (RD 1186/1998)"),
        ("Plazo de Protección:",   "30 años desde calificación definitiva"),
        ("Fecha de Extinción:",    "20 de septiembre de 2029"),
    ]
    story.append(kv_table(vpo_data))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("5.2. Fundamentación Jurídica", S_H2))
    story.append(Paragraph(
        "<b>A) Normativa estatal.</b> Las viviendas calificadas al amparo del Plan de Vivienda "
        "1996-1999 (Real Decreto 2190/1995, de 28 de diciembre) mantienen su régimen de protección "
        "durante <b>30 años</b> a contar desde la calificación definitiva. Idéntico plazo rige para "
        "las acogidas al Plan de Vivienda 1998-2001 (Real Decreto 1186/1998, de 12 de junio). Dado "
        "que el expediente de calificación data de 1998 y la calificación definitiva se otorga el "
        "20 de septiembre de 1999, el inmueble queda sujeto a uno de estos dos planes, siendo en "
        "ambos casos el plazo de 30 años.",
        S_BODY
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "<b>B) Normativa autonómica gallega.</b> La Ley 8/2012, de 29 de junio, de Vivienda de "
        "Galicia, establece en su artículo 60.4 que “para las viviendas que se acojan a financiación "
        "o a ayudas estatales, se estará, en cuanto a la duración del régimen de protección, a lo "
        "que disponga la correspondiente normativa reguladora de las citadas ayudas”. Por tanto, "
        "la Ley gallega remite al plazo estatal de 30 años.",
        S_BODY
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "<b>C) Cómputo del plazo.</b> Calificación definitiva: 20/09/1999 + 30 años = "
        "<b>20 de septiembre de 2029</b>. A la fecha del presente informe (febrero de 2026), restan "
        "aproximadamente tres años y siete meses para la extinción automática del régimen de protección.",
        S_BODY
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("5.3. Consecuencias Jurídicas para el Postor", S_H2))
    story.append(Paragraph(
        "La subsistencia del régimen VPO implica las siguientes restricciones y consideraciones:", S_BODY
    ))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "<b>1.ª) Precio máximo de venta.</b> Las viviendas de protección oficial están sujetas a un "
        "precio máximo de transmisión fijado administrativamente. En una subasta judicial, el valor "
        "de adjudicación opera con independencia del precio tasado VPO, pero la Administración "
        "podría cuestionar la transmisión si el precio excediera los módulos establecidos. No suele "
        "generar problemática en subastas judiciales.",
        S_BODY
    ))
    story.append(Paragraph(
        "<b>2.ª) Derechos de tanteo y retracto de la Administración.</b> La Ley 8/2012 reconoce a "
        "la Xunta de Galicia derechos de tanteo y retracto sobre las viviendas protegidas. La "
        "cuestión relevante es si estos derechos son operativos en el contexto de una ejecución "
        "hipotecaria. La doctrina mayoritaria entiende que la Administración debe ser notificada "
        "de la subasta para poder ejercitar, en su caso, el derecho de retracto, si bien su "
        "ejercicio efectivo en procedimientos judiciales es infrecuente en la práctica.",
        S_BODY
    ))
    story.append(Paragraph(
        "<b>3.ª) Requisitos del adquirente.</b> Con carácter general, los adquirentes de VPO deben "
        "cumplir los requisitos de acceso establecidos por la normativa (nivel de ingresos, no "
        "titularidad de otra vivienda, etc.). No obstante, en el marco de la ejecución hipotecaria "
        "judicial, la transmisión forzosa opera con matices respecto a estos requisitos, existiendo "
        "resoluciones de la DGRN (actual DGSJFP) que amparan la inscripción a favor del adjudicatario "
        "en subasta sin exigencia de dichos requisitos.",
        S_BODY
    ))
    story.append(Paragraph(
        "<b>4.ª) Destino de la vivienda.</b> Mientras subsista la calificación, la vivienda debe "
        "destinarse a domicilio habitual y permanente del adquirente, no pudiendo dedicarse a "
        "segunda residencia ni a otros usos no autorizados (art. 65 de la Ley 8/2012).",
        S_BODY
    ))
    story.append(PageBreak())

    # ============== 6. VIVIENDA HABITUAL DEL EJECUTADO ==============
    story.append(section_header("6", "Condición de vivienda habitual del ejecutado"))
    story.append(Paragraph(
        "Según consta en el edicto de la subasta, la vivienda <b>NO CONSTA</b> como domicilio "
        "habitual del ejecutado. Consecuencia directa: <b>no resultan de aplicación las protecciones "
        "reforzadas del artículo 670.4 de la LEC</b>, lo que permite la aprobación del remate por "
        "debajo del 50% del valor de tasación en determinadas circunstancias procesales.",
        S_BODY
    ))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "No obstante, la existencia de un derecho de uso y disfrute inscrito a favor de D.ª "
        "[Beneficiaria] (vid. apartado 4.2) sugiere la posible ocupación física del inmueble. "
        "Aunque dicho derecho será cancelado registralmente con la adjudicación al ser posterior "
        "a la hipoteca ejecutada (SSTS de 8 de octubre de 2010 y de 20 de noviembre de 2018), la "
        "eventual necesidad de lanzamiento debe ser considerada como un coste y un plazo adicional.",
        S_BODY
    ))
    story.append(Spacer(1, 0.6*cm))

    # ============== 7. CONDICIONES ECONÓMICAS ==============
    story.append(section_header("7", "Condiciones económicas de la subasta"))
    econ_rows = [
        ["Valor de tasación (tipo de subasta)",                "<b>54.634,92 €</b>"],
        ["Deuda reclamada (principal)",                        "17.638,44 €"],
        ["Intereses estimados + costas",                       "5.290,00 € (pendiente liquidación)"],
        ["Depósito obligatorio (5% del tipo)",                 "<b>2.731,75 €</b>"],
        ["Puja mínima aprobable – 70% del tipo (art. 670 LEC)","<b>38.244,44 €</b>"],
    ]
    econ_rows_md = [[Paragraph(r[0], style("td2", fontSize=9.5, leading=12, alignment=TA_LEFT)),
                     Paragraph(r[1], style("td2", fontSize=9.5, leading=12, alignment=TA_LEFT))]
                    for r in econ_rows]
    head = [Paragraph("<b>Concepto</b>", style("th2", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=colors.white)),
            Paragraph("<b>Importe</b>", style("th2", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=colors.white))]
    t_econ = Table([head] + econ_rows_md, colWidths=[10*cm, 6.5*cm])
    t_econ.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY_DK),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ("BACKGROUND", (0,-1), (-1,-1), YEL_BG),
        ("BOX", (0,0), (-1,-1), 0.5, GREY_HD),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t_econ)
    story.append(Spacer(1, 0.6*cm))

    story.append(Paragraph("7.1. Análisis Comparativo de Mercado", S_H2))
    story.append(Paragraph(
        "De acuerdo con herramientas de análisis de mercado inmobiliario consultadas, los datos "
        "orientativos para la zona son los siguientes:",
        S_BODY
    ))
    story.append(Spacer(1, 0.3*cm))
    mkt_head = ["Parámetro", "Valor Estimado"]
    mkt_rows = [
        ["Valor de mercado orientativo (oferta)",         "~ 155.756 €"],
        ["Valor de mercado orientativo (negociación)",    "~ 139.779 €"],
        ["Revalorización anual de la zona",               "~ +53% (últimos 12 meses)"],
        ["Viviendas en venta en la zona (ratio)",         "26 / 2.247 (1,16%)"],
        ["Comparables de la zona (50-115 m²)",            "137.500 € - 175.000 €"],
    ]
    story.append(data_table(mkt_head, mkt_rows, col_widths=[10*cm, 6.5*cm]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "<i><b>Nota:</b> Los valores de mercado indicados son orientativos, obtenidos mediante "
        "herramientas de análisis automatizado y comparables publicados. No constituyen tasación "
        "oficial y pueden diferir del valor real de la vivienda, especialmente considerando su "
        "condición de VPO vigente, que podría limitar el precio máximo de transmisión.</i>",
        S_NOTE
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("7.2. Escenarios de Puja", S_H2))
    esc_head = ["Escenario", "Puja", "% s/ tipo", "% s/ mercado"]
    esc_rows = [
        ["Puja mínima (70%)",    "38.244 €", "70,00%",  "24,55% del valor mercado"],
        ["Puja intermedia (80%)", "43.708 €", "80,00%",  "28,06%"],
        ["Puja al tipo (100%)",  "54.635 €", "100,00%", "35,08%"],
    ]
    story.append(data_table(esc_head, esc_rows, col_widths=[4.5*cm, 3*cm, 3*cm, 6*cm]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "En todos los escenarios, el tipo de la subasta (54.634,92 €) representa el <b>35,08%</b> "
        "del valor orientativo de mercado, lo que, con las salvedades derivadas de la condición VPO, "
        "ofrece un margen teórico de rentabilidad significativo, sujeto a los riesgos inherentes a "
        "toda adquisición en subasta judicial, siendo el más probable los dilatados lapsus temporales "
        "que conlleva la inversión.",
        S_BODY
    ))
    story.append(PageBreak())

    # ============== 8. ESTIMACIÓN DE DEUDAS ==============
    story.append(section_header("8", "Estimación de deudas pendientes vinculadas al inmueble"))
    story.append(callout(
        "<b>ADVERTENCIA:</b> Las cuantías contenidas en el presente apartado han sido calculadas "
        "de forma <b>ESTIMATORIA</b>, al no disponerse de acceso a registros públicos que permitan "
        "su determinación exacta. Los importes reales pueden diferir significativamente de las "
        "estimaciones aquí contenidas.",
        kind="red"
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("8.1. Deuda Comunitaria Estimada (Art. 9.1.e LPH)", S_H2))
    story.append(Paragraph(
        "Conforme al artículo 9.1.e) de la Ley 49/1960, de 21 de julio, de Propiedad Horizontal, "
        "el adquirente de una vivienda responde con el propio inmueble adquirido de las cantidades "
        "adeudadas a la comunidad de propietarios correspondientes a la <b>anualidad en curso y a "
        "los tres años naturales anteriores</b> a la transmisión.",
        S_BODY
    ))
    story.append(Paragraph(
        "Partiendo de la hipótesis de que el ejecutado ha dejado de abonar las cuotas comunitarias "
        "desde, al menos, el inicio de la ejecución hipotecaria (año 2022), y tomando como "
        "referencia las cuotas medias de comunidades de propietarios de características similares "
        "en la zona (urbanización residencial de tamaño medio, sin servicios extraordinarios como "
        "piscina o conserjería), se estima lo siguiente:",
        S_BODY
    ))
    story.append(Spacer(1, 0.3*cm))
    com_head = ["Concepto", "Estimación Mensual", "Estimación Anual"]
    com_rows = [
        ["Cuota comunitaria ordinaria estimada", "50 - 75 €/mes", "600 - 900 €/año"],
    ]
    story.append(data_table(com_head, com_rows, col_widths=[7*cm, 4.75*cm, 4.75*cm]))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("<b>Responsabilidad máxima del adjudicatario (art. 9.1.e LPH):</b>", S_BODY))
    story.append(Spacer(1, 0.2*cm))
    resp_head = ["Periodo (año en curso + 3 anteriores)", "Estimación"]
    resp_rows = [
        ["Año en curso (2026, estimación proporcional)", "100 - 150 €"],
        ["Año 2025",                                     "600 - 900 €"],
        ["Año 2024",                                     "600 - 900 €"],
        ["Año 2023",                                     "600 - 900 €"],
        ["<b>TOTAL, ESTIMADO</b>",                       "<b>1.900 - 2.850 €</b>"],
    ]
    resp_rows_md = [[Paragraph(r[0], style("td3", fontSize=9.5, leading=12, alignment=TA_LEFT)),
                     Paragraph(r[1], style("td3", fontSize=9.5, leading=12, alignment=TA_CENTER))]
                    for r in resp_rows]
    head_md = [Paragraph(f"<b>{c}</b>", style("th3", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=colors.white)) for c in resp_head]
    t_resp = Table([head_md] + resp_rows_md, colWidths=[10*cm, 6.5*cm])
    t_resp.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY_DK),
        ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f8fafc")]),
        ("BACKGROUND", (0,-1), (-1,-1), YEL_BG),
        ("BOX", (0,0), (-1,-1), 0.5, GREY_HD),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t_resp)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "La estimación anterior no incluye posibles derramas extraordinarias que pudieran haberse "
        "aprobado por la comunidad durante el periodo, cuyo importe resulta imposible de determinar "
        "sin consultar directamente a la administración de la Urbanización [Nombre].",
        S_BODY
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("8.2. Impuesto sobre Bienes Inmuebles (IBI) Estimado", S_H2))
    story.append(Paragraph(
        "El Impuesto sobre Bienes Inmuebles es una obligación tributaria de carácter municipal que "
        "recae sobre el titular registral del inmueble a 1 de enero de cada ejercicio. Conforme al "
        "artículo 64 del Texto Refundido de la Ley Reguladora de las Haciendas Locales (RDL 2/2004), "
        "el tipo impositivo para bienes urbanos oscila entre el 0,4% y el 1,3% del valor catastral.",
        S_BODY
    ))
    story.append(Paragraph(
        "Para el municipio de Pobra do Caramiñal, perteneciente a la provincia de A Coruña, se "
        "estima un tipo impositivo situado en la horquilla media-baja de los municipios gallegos "
        "de similar entidad. Considerando las características de la vivienda (VPO construida en "
        "1999, 97,60 m² construidos), se realiza la siguiente aproximación:",
        S_BODY
    ))
    story.append(Spacer(1, 0.3*cm))
    ibi_head = ["Concepto", "Estimación"]
    ibi_rows = [
        ["IBI anual estimado",                       "200 - 400 €/año"],
        ["Años estimados de impago (2022-2026)",     "4 - 5 ejercicios"],
        ["<b>Deuda total estimada de IBI (sin recargos)</b>", "<b>800 - 2.000 €</b>"],
    ]
    ibi_rows_md = [[Paragraph(r[0], style("td4", fontSize=9.5, leading=12, alignment=TA_LEFT)),
                    Paragraph(r[1], style("td4", fontSize=9.5, leading=12, alignment=TA_CENTER))]
                   for r in ibi_rows]
    head_md = [Paragraph(f"<b>{c}</b>", style("th4", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=colors.white)) for c in ibi_head]
    t_ibi = Table([head_md] + ibi_rows_md, colWidths=[10*cm, 6.5*cm])
    t_ibi.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY_DK),
        ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f8fafc")]),
        ("BACKGROUND", (0,-1), (-1,-1), YEL_BG),
        ("BOX", (0,0), (-1,-1), 0.5, GREY_HD),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t_ibi)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "<b>Nota importante:</b> El IBI impagado no se transmite directamente al adjudicatario como "
        "deuda personal, sino que el inmueble queda afecto al pago de los ejercicios no prescritos "
        "(art. 79 LGT). En la práctica, el Ayuntamiento podría exigir el pago de los recibos "
        "pendientes como condición para la expedición de certificados o la realización de trámites "
        "urbanísticos. Además, la falta de pago del IBI conlleva recargos de apremio (entre el 5% "
        "y el 20%) e intereses de demora que podrían incrementar las cuantías indicadas.",
        S_BODY
    ))
    story.append(PageBreak())

    # ============== 9. ESTIMACIÓN DE COSTES TOTALES ==============
    story.append(section_header("9", "Estimación de costes totales de adquisición"))
    story.append(Paragraph(
        "A continuación, se presenta una estimación consolidada de los costes asociados a la "
        "adquisición del inmueble en subasta, partiendo del escenario de puja mínima aprobable "
        "(70% del tipo):",
        S_BODY
    ))
    story.append(Spacer(1, 0.4*cm))
    costes_head = ["Concepto", "Estimación"]
    costes_rows = [
        ["Precio de adjudicación (escenario 70%)",                "38.244,44 €"],
        ["ITP – Impuesto Transmisiones Patrimoniales (10% Galicia)","3.824,44 €"],
        ["Gastos notariales",                                     "0 €"],
        ["Gastos registrales (estimación)",                       "200 - 400 €"],
        ["Deuda comunitaria estimada (art. 9.1.e LPH)",           "1.900 - 2.850 €"],
        ["IBI pendiente estimado (afección real)",                "800 - 2.000 €"],
        ["Costes de letrado para adjudicación y lanzamiento",     "1.500 - 3.000 €"],
        ["<b>TOTAL, ESTIMADO MÍNIMO (escenario optimista)</b>",   "<b>~ 45.269 €</b>"],
        ["<b>TOTAL ESTIMADO MÁXIMO (escenario conservador)</b>",  "<b>~ 50.919 €</b>"],
    ]
    costes_rows_md = [[Paragraph(r[0], style("td5", fontSize=9.5, leading=12, alignment=TA_LEFT)),
                       Paragraph(r[1], style("td5", fontSize=9.5, leading=12, alignment=TA_RIGHT))]
                      for r in costes_rows]
    head_md = [Paragraph(f"<b>{c}</b>", style("th5", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=colors.white)) for c in costes_head]
    t_cost = Table([head_md] + costes_rows_md, colWidths=[11*cm, 5.5*cm])
    t_cost.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NAVY_DK),
        ("ROWBACKGROUNDS", (0,1), (-1,-3), [colors.white, colors.HexColor("#f8fafc")]),
        ("BACKGROUND", (0,-2), (-1,-2), GREEN_BG),
        ("BACKGROUND", (0,-1), (-1,-1), YEL_BG),
        ("BOX", (0,0), (-1,-1), 0.5, GREY_HD),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t_cost)
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        "En cualquier escenario, el coste total estimado de adquisición se situaría entre el "
        "<b>29,07% y el 32,69%</b> del valor orientativo de mercado (~ 155.756 €), manteniendo "
        "un margen teórico favorable, si bien matizado por las restricciones derivadas de la "
        "vigencia del régimen VPO. <u>Ante un escenario más conservador, en el que la valoración "
        "del activo real ante la calificación de VPO sea de 90.000 €, en NET VALUE (o beneficio "
        "neto) por una inversión de unos 50.919 € sería unos 40.000 €</u>, lo que genera un "
        "resultado muy positivo y acorde a la inversión en subastas, generándose casi un 100%.",
        S_BODY
    ))
    story.append(Spacer(1, 0.4*cm))
    story.append(callout(
        "<b>La puja máxima recomendada se sitúa en torno a los 50.000 €</b>, con el objetivo de "
        "marcar un mínimo de rentabilidad del 30% por la operación.",
        kind="yellow"
    ))
    story.append(Spacer(1, 0.6*cm))

    # ============== 10. PROCEDIMIENTO ==============
    story.append(section_header("10", "Procedimiento de participación en la subasta"))
    proc_data = [
        ("Plataforma:",     "Portal de Subastas del BOE (https://subastas.boe.es)"),
        ("Apertura:",       "24 horas tras publicación en el BOE"),
        ("Duración:",       "20 días naturales (posible prórroga de 24 h desde última puja)"),
        ("Depósito:",       "5% del tipo (2.731,75 €) – mediante consignación electrónica AEAT"),
        ("Identificación:", "<b>Certificado electrónico</b> o sistema Cl@ve"),
        ("Cesión:",         "Solo el ejecutante o acreedores posteriores pueden reservar cesión a tercero"),
    ]
    story.append(kv_table(proc_data))
    story.append(PageBreak())

    # ============== 11. CONCLUSIONES ==============
    story.append(section_header("11", "Conclusiones y recomendaciones"))
    conclusiones = [
        ("PRIMERA. Cargas registrales.",
         "No existen cargas anteriores ni preferentes a la hipoteca ejecutada que deban ser asumidas "
         "por el adjudicatario. Tanto la hipoteca de Caixabank, S.A. (inscripción 2.ª), como el "
         "derecho de uso y disfrute a favor de D.ª [Beneficiaria] (inscripción 4.ª) y la afección "
         "fiscal (anotación de 31/08/2021) serán cancelados registralmente con la adjudicación "
         "conforme al artículo 674.2 de la Ley de Enjuiciamiento Civil."),
        ("SEGUNDA. Régimen VPO vigente.",
         "Tras investigación exhaustiva de la normativa estatal (Planes de Vivienda 1996-1999 y "
         "1998-2001) y autonómica (Ley 8/2012 de Vivienda de Galicia, art. 60.4), se concluye "
         "que el régimen de protección de la vivienda NO HA EXPIRADO. El plazo de 30 años desde "
         "la calificación definitiva (20/09/1999) no vencerá hasta el 20 de septiembre de 2029. "
         "Esta circunstancia puede implicar restricciones en la transmisión, derechos de tanteo "
         "y retracto de la Administración, y limitaciones de uso que deben ser verificadas con "
         "el IGVS antes de pujar."),
        ("TERCERA. Relación entre el tipo de subasta y el valor de mercado.",
         "El tipo de la subasta (54.634,92 €) representa aproximadamente el 35,08% del valor "
         "orientativo de mercado según herramientas de análisis consultadas que valoran la "
         "vivienda libre. La puja mínima aprobable (38.244,44 € – 70% del tipo) representaría "
         "el 24,55% de dicho valor. Sin embargo, la vigencia del régimen VPO condiciona la "
         "rentabilidad real de la operación al imponer limitaciones de precio y uso hasta 2029."),
        ("CUARTA. Ocupación física.",
         "Pese a que el edicto no identifica la vivienda como domicilio habitual del ejecutado, "
         "la existencia de un derecho de uso inscrito a favor de D.ª [Beneficiaria] hace presumir "
         "su posible ocupación. Aunque el derecho registral será cancelado, la efectiva toma de "
         "posesión podría requerir un procedimiento de lanzamiento con los costes y plazos "
         "inherentes."),
        ("QUINTA. Deudas comunitarias e impositivas.",
         "Se ha procedido a estimar las posibles deudas comunitarias (art. 9.1.e LPH) e IBI "
         "pendientes, partiendo de la hipótesis de impago desde el inicio de la ejecución. La "
         "deuda comunitaria imputable al adjudicatario se estima entre 1.900 y 2.850 euros, y "
         "el IBI pendiente entre 800 y 2.000 euros. Estas cantidades son orientativas y deben "
         "ser verificadas mediante la obtención de los correspondientes certificados de la "
         "comunidad de propietarios y del Ayuntamiento de Pobra do Caramiñal, a los que no se "
         "puede acceder hasta obtener la propiedad."),
        ("SEXTA. Vivienda habitual del deudor.",
         "Al no constar como vivienda habitual del ejecutado, no resultan de aplicación las "
         "protecciones reforzadas del artículo 670.4 de la LEC, lo que permite la aprobación "
         "de pujas inferiores al 50% del tipo en los términos legalmente previstos."),
    ]
    for tit, txt in conclusiones:
        story.append(Paragraph(f"<b>{tit}</b> {txt}", S_BODY))
        story.append(Spacer(1, 0.25*cm))
    story.append(Spacer(1, 0.5*cm))

    # ============== FIRMA (sin firma escaneada real) ==============
    line = Table([[""]], colWidths=[16.5*cm], rowHeights=[2])
    line.setStyle(TableStyle([("LINEBELOW", (0,0), (-1,-1), 0.5, GREY_HD)]))
    story.append(line)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Lo que se informa a los efectos oportunos.", S_BODY_C))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("En Sevilla, a [fecha de emisión del informe contratado]", S_BODY_C))
    story.append(Spacer(1, 0.8*cm))

    # Bloque ficticio de firma (sin firma real)
    firma_box = Table([[Paragraph(
        "<b>[Documento de muestra – sin firma electrónica]</b><br/><br/>"
        "El informe contratado se entrega firmado electrónicamente con<br/>"
        "<b>certificado profesional FNMT-CERES</b> y sello CSV verificable<br/>"
        "en <font color='#1e3a8a'>https://valide.redsara.es</font>",
        style("firma_box", fontSize=9, leading=13, alignment=TA_CENTER, textColor=GREY_TX, fontName="Helvetica-Oblique")
    )]], colWidths=[10*cm])
    firma_box.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ("BOX", (0,0), (-1,-1), 0.5, GREY_HD),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("LEFTPADDING", (0,0), (-1,-1), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
    ]))
    # Centrar la tabla en página
    centered = Table([[firma_box]], colWidths=[16.5*cm])
    centered.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")]))
    story.append(centered)
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("Fdo.: D. ████████████████████████", S_FIRMA))
    story.append(Paragraph("Letrado · ICAS n.º ██████",
        style("firma_l", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=GOLD, fontName="Helvetica-Bold")))
    story.append(Paragraph("CAFAVE INVESTMENT",
        style("firma_c", fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=GOLD, fontName="Helvetica-Bold")))

    return story


# ===================== EJECUCIÓN =====================
def main():
    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        OUT_PATH,
        pagesize=A4,
        leftMargin=2*cm,
        rightMargin=2*cm,
        topMargin=3*cm,      # deja espacio para header + banner
        bottomMargin=2*cm,   # deja espacio para footer
        title="Informe Jurídico de Viabilidad de Subasta · MUESTRA",
        author="CAFAVE INVESTMENT — Letrado colegiado ICAS (datos redactados en muestra)",
        subject="Muestra demostrativa de Informe Jurídico de Viabilidad de Subasta Judicial",
        keywords="subasta judicial, informe jurídico, BOE, muestra, CAFAVE",
    )
    story = build_story()
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    size = Path(OUT_PATH).stat().st_size
    print(f"[ok] PDF generado: {OUT_PATH} ({size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
