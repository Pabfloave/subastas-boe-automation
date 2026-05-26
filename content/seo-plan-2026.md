# Plan SEO & Contenidos comprarensubasta.com — 2026
**Objetivo**: 15-20 leads/día cualificados al formulario "Filtro Inversores CAFAVE" (informe jurídico 72,60€).
**Owner**: CAFAVE Investment · **Fecha**: mayo 2026

---

## 1. Diagnóstico rápido

### Activos actuales
- 982 posts BOE (uno por subasta) con JSON-LD completo (RealEstateListing + LegalService + FAQ + BreadcrumbList)
- 52 hubs provinciales estáticos (potencial muy alto, SEO local)
- Rank Math + WPForms (CTA único: "Solicitud de Perfil Inversor")
- Plugin custom REST API → permite generar widgets de subastas en cualquier landing

### Puntos débiles detectados
1. **Home muy corporativa / institucional** → poca señal E-E-A-T para Google, sin blog visible, sin testimonios, sin track record.
2. **Hubs provinciales = listas de fichas** sin contenido evergreen → no rankean por "subasta judicial [provincia]" frente a Auctia, AlertaSubastas, CristinaMoriones.
3. **Sin blog/guías** → no captura tráfico informacional alto (cargas, pujas, ROI, cesión de remate) que es el embudo natural del inversor.
4. **CTA único genérico** ("Solicitud de Perfil Inversor") — no segmenta intención. Falta lead-magnet (PDF) y CTA contextual por tipo de tráfico.
5. **Las 982 fichas no enlazan al hub provincial** ni a guías evergreen → linking pobre.

### Competencia (lo que están haciendo bien)
| Player | Fortaleza | Aprendible |
|---|---|---|
| **auctia.es** | Guías SEO largas + listados por ciudad con FAQ + IA scoring | Long-tail "[ciudad] subastas BOE" + filtros visuales |
| **cristinamoriones.com** | Marca personal + casos reales + nicho cesión de remate/NPLs | Branding humano, testimonios |
| **alertasubastas.com** | Blog técnico + alertas email = lead magnet | Newsletter como captura B2C |
| **subastasprocuradores.com** | Autoridad oficial | No es competencia, es referente para enlace saliente |
| **idealista.com/subastas** | Volumen + brand | No profundiza jurídicamente: hueco |
| **gomezgallardo.com / fundamentosjuridicos.com** | Contenido jurídico técnico | Refuerzo del informe jurídico como producto |

**Hueco de mercado claro**: nadie combina (a) listado masivo BOE actualizado + (b) contenido jurídico profundo + (c) servicio de informe pre-puja a precio fijo. CAFAVE tiene los 3 ingredientes — falta empaquetarlos en SEO.

---

## 2. Keyword research orientado a leads (38 KWs)

Clasificación: **TX** = Transaccional · **CO** = Comercial · **IN** = Informacional con intención de compra alta

### Cluster A — Informe jurídico / due diligence (intención más cercana al producto)
| # | Keyword | Intención | Vol estimado | Dificultad |
|---|---|---|---|---|
| 1 | informe jurídico subasta judicial | CO | bajo-medio | baja |
| 2 | abogado subastas judiciales | CO | medio | media |
| 3 | abogado subastas judiciales madrid | CO | bajo | baja |
| 4 | abogado subastas judiciales barcelona | CO | bajo | baja |
| 5 | abogado subastas judiciales valencia | CO | bajo | baja |
| 6 | cargas ocultas subasta judicial | IN | medio | baja |
| 7 | nota simple subasta judicial | IN | bajo | muy baja |
| 8 | certificación de cargas subasta BOE | IN | bajo | muy baja |
| 9 | cargas preferentes subasta | IN | bajo | baja |
| 10 | due diligence subasta judicial | CO | muy bajo | muy baja (oportunidad) |

### Cluster B — Cómo pujar / proceso (gran volumen informacional)
| # | Keyword | Intención | Vol | Dificultad |
|---|---|---|---|---|
| 11 | cómo pujar en subasta judicial | IN | alto | media |
| 12 | subasta BOE paso a paso | IN | alto | alta |
| 13 | depósito 5% subasta BOE | IN | medio | baja |
| 14 | cesión de remate qué es | IN | medio | baja |
| 15 | cesión de remate fiscalidad | IN | bajo | baja |
| 16 | quiebra postor subasta | IN | bajo | muy baja |
| 17 | plazo pagar subasta judicial 40 días | IN | bajo | muy baja |
| 18 | mejor postor vs adjudicación 70% | IN | bajo | muy baja |

### Cluster C — Comprar piso/inmueble en subasta (intención compra)
| # | Keyword | Intención | Vol | Dificultad |
|---|---|---|---|---|
| 19 | comprar piso subasta judicial | TX | alto | alta |
| 20 | comprar piso subasta madrid | TX | medio | media |
| 21 | comprar piso subasta barcelona | TX | medio | media |
| 22 | comprar piso subasta valencia | TX | medio | media |
| 23 | comprar piso subasta sevilla | TX | bajo | baja |
| 24 | comprar piso ocupado subasta | IN | medio | baja |
| 25 | comprar local subasta judicial | TX | bajo | baja |
| 26 | inversión piso subasta rentabilidad | CO | medio | media |

### Cluster D — Riesgos / problemas (alto intent post-research)
| # | Keyword | Intención | Vol | Dificultad |
|---|---|---|---|---|
| 27 | riesgos comprar subasta judicial | IN | medio | baja |
| 28 | piso ocupado subasta judicial qué hacer | IN | medio | baja |
| 29 | desahucio adjudicatario subasta | IN | bajo | baja |
| 30 | IBI atrasados subasta BOE | IN | bajo | muy baja |
| 31 | deudas comunidad subasta | IN | bajo | baja |

### Cluster E — Provincial / local (ya tenemos infraestructura)
| # | Keyword | Intención | Vol | Dificultad |
|---|---|---|---|---|
| 32 | subastas judiciales madrid | TX | alto | alta |
| 33 | subastas judiciales barcelona | TX | alto | alta |
| 34 | subastas judiciales valencia | TX | medio | media |
| 35 | subastas BOE [provincia] (×52) | TX | variable | media |
| 36 | calendario próximas subastas BOE | IN | bajo | baja (oportunidad) |

### Cluster F — Avanzado / fondos
| # | Keyword | Intención | Vol | Dificultad |
|---|---|---|---|---|
| 37 | NPL inmobiliario España inversor | CO | bajo | baja |
| 38 | proindiviso subasta inversor | CO | bajo | baja |

**Prioridad para 90 días**: A (producto), D (miedos = consultas), E (local masivo). B y C alimentan top-of-funnel.

---

## 3. Quick Wins SEO (esta semana, alto impacto)

1. **Interlinking masivo fichas → hub provincial**: añadir al final de cada uno de los 982 posts un bloque "Más subastas en [Provincia]" linkando al hub. Implementable en template del generador, una sola release.
2. **Interlinking hub provincial → guías evergreen**: cada hub debe enlazar a "Cómo pujar en subasta", "Cargas ocultas", "Informe jurídico" en sidebar o sección fija.
3. **Schema enhancement**: añadir `Service` schema + `FAQPage` a cada hub provincial con 5 preguntas específicas de esa provincia ("¿Cuántas subastas hay en X al mes?", "¿Qué juzgados de X publican más?"). Genera rich snippets.
4. **Optimizar `<title>` y meta de hubs**: pasar de "Subastas Madrid - Comprarensubasta" → "Subastas Judiciales Madrid 2026 | [N] activos BOE actualizados". Incluir conteo dinámico.
5. **Página /informe-juridico-subasta** (landing dedicada): hoy el servicio está enterrado en el form. Crear landing con precio (72,60€), proceso, ejemplo de informe (PDF de muestra), garantía, testimonios → captura keyword "informe jurídico subasta judicial".
6. **Sticky CTA contextual** en fichas: "¿Vas a pujar por este activo? Pide informe jurídico antes (72,60€)" con referencia al activo precargado en el form.
7. **Breadcrumbs visibles en HTML** (no solo schema): mejora CTR en SERP.
8. **`llms.txt` + `robots.txt` revisión**: asegurar que /informe-juridico-subasta y hubs no estén bloqueados; el `llms.txt` ya existe → añadir las nuevas URLs.
9. **Sitemap noticias / IndexNow**: dado que entran fichas nuevas diariamente, conectar IndexNow (Bing) y enviar pings a Google Search Console al publicar.
10. **Open Graph y Twitter Card** en fichas: muchas se comparten en grupos de Telegram/WhatsApp de inversores. Imagen OG con valor, ciudad y tipo de activo.

---

## 4. Content Gap Analysis vs competencia

| Gap | Por qué importa | Quién lo hace | Prioridad |
|---|---|---|---|
| Guía "Cómo pujar paso a paso 2026" actualizada | KW alto volumen, fundamento de autoridad | Auctia, AlertaSubastas | Alta |
| Listado "Cargas ocultas: las 12 que aniquilan tu ROI" | Producto-fit perfecto con informe jurídico | Gomezgallardo (técnico, poco SEO) | Alta |
| Calculadora ROI subasta interactiva | Lead magnet único, no la tiene nadie | Nadie | Alta |
| Glosario jurídico subastas (50+ términos) | SEO long-tail + autoridad | Parcial | Media |
| Calendario "Próximas subastas relevantes esta semana" | Recurrencia + email capture | Parcial | Alta |
| Casos de éxito (ROI real, anonimizados) | E-E-A-T + conversión | C. Moriones | Alta |
| FAQ por provincia (juzgados, frecuencia) | Local SEO | Nadie | Media |
| Comparativa: subasta vs banco vs particular | Tráfico decisión | Idealista (genérico) | Media |
| Guía cesión de remate fiscalidad | KW B2B, mandato inversor | Parcial | Media |
| Riesgo ocupación: protocolo legal post-adjudicación | Miedo nº1 inversor | Parcial | Alta |

---

## 5. Topic Authority Map (4 pilares)

### Pilar 1 — Informe jurídico y due diligence (CONVERSIÓN)
**Hub**: crear `/informe-juridico-subasta-judicial`
- Cargas ocultas: las 12 que pueden arruinar tu inversión [KW: cargas ocultas subasta]
- Nota simple, certificación de cargas y edicto: el trío legal [KW: nota simple subasta]
- Cargas preferentes vs posteriores explicado con casos [KW: cargas preferentes]
- Qué incluye un informe jurídico previo (con ejemplo) [KW: informe jurídico subasta]
- Cuándo merece la pena el informe (umbral de inversión) [KW: due diligence subasta]

### Pilar 2 — Cómo pujar (TRÁFICO TOP-FUNNEL)
**Hub**: `/guia-subastas-bo-paso-a-paso`
- Subastas BOE paso a paso 2026 [KW: subasta BOE paso a paso]
- Depósito 5%: cómo se constituye y qué pasa si pierdes [KW: depósito 5% subasta]
- Cesión de remate: qué es, cuándo conviene, fiscalidad [KW: cesión de remate]
- Plazo de 40 días: cómo financiarte sin perder el depósito [KW: plazo pago subasta]
- Mejor postor vs 70% del valor: cuándo se adjudica [KW: adjudicación 70%]

### Pilar 3 — Riesgos del inversor (MIEDO → CONVERSIÓN)
**Hub**: `/riesgos-subastas-judiciales`
- Piso ocupado en subasta: qué hacer paso a paso [KW: piso ocupado subasta]
- Desahucio del adjudicatario: plazos reales 2026 [KW: desahucio adjudicatario]
- IBI y deudas de comunidad atrasadas: cuáles heredas [KW: IBI atrasados subasta]
- Los 7 errores que arruinan a inversores novatos [KW: errores subasta judicial]

### Pilar 4 — Provincial / mercado (LOCAL SEO + RECURRENCIA)
**Hub por provincia** (ya existen 52) + contenido evergreen por provincia top-5
- Subastas judiciales Madrid: guía del inversor 2026 [KW: subastas judiciales madrid]
- Idem Barcelona, Valencia, Sevilla, Málaga
- Calendario próximas subastas relevantes (actualizado semanal) [KW: calendario subastas BOE]

---

## 6. Calendario editorial 90 días (22 artículos)

### Mes 1 — Foundation (autoridad + conversión)
| Sem | Título | KW principal | Intención | Tipo | Linka desde | Prioridad |
|---|---|---|---|---|---|---|
| 1 | Cargas ocultas en subastas judiciales: las 12 que aniquilan tu ROI | cargas ocultas subasta judicial | IN | Pillar | Home + todas las fichas BOE | **CRÍTICA** |
| 1 | Informe jurídico previo: qué incluye, cuánto cuesta, ejemplo real | informe jurídico subasta | CO | Landing | Sticky CTA fichas + menú | **CRÍTICA** |
| 2 | Cómo pujar en subasta BOE paso a paso 2026 | subasta BOE paso a paso | IN | Pillar | Home + hub provinciales | Alta |
| 2 | Piso ocupado en subasta: protocolo legal post-adjudicación | piso ocupado subasta judicial | IN | Cluster | Pilar 3 + fichas con ocupación | Alta |
| 3 | Cesión de remate: qué es, cuándo conviene y fiscalidad | cesión de remate | IN | Cluster | Pilar 2 | Alta |
| 3 | Nota simple, certificación de cargas y edicto explicados | nota simple subasta | IN | Cluster | Pilar 1 | Media |
| 4 | Subastas judiciales Madrid: guía del inversor 2026 | subastas judiciales madrid | TX | Hub-evergreen | Home, menú, hub Madrid | **CRÍTICA** |
| 4 | Calculadora ROI subasta judicial [+ tool] | calculadora subasta ROI | CO | Tool + post | Sidebar global | Alta |

### Mes 2 — Expansión (volumen + recurrencia)
| Sem | Título | KW | Intención | Tipo | Prioridad |
|---|---|---|---|---|---|
| 5 | Subastas judiciales Barcelona: guía 2026 | subastas judiciales barcelona | TX | Hub-evergreen | Alta |
| 5 | Cargas preferentes vs posteriores: casos reales | cargas preferentes subasta | IN | Cluster | Media |
| 6 | Depósito del 5%: cómo constituirlo y qué pasa si pierdes | depósito 5% subasta | IN | Cluster | Media |
| 6 | Glosario jurídico de subastas (60+ términos) | glosario subastas judiciales | IN | Pillar | Alta |
| 7 | Subastas judiciales Valencia: guía 2026 | subastas judiciales valencia | TX | Hub-evergreen | Alta |
| 7 | Los 7 errores que arruinan a inversores novatos en subastas | errores subasta judicial | IN | Cluster | Alta |
| 8 | Plazo 40 días: cómo financiarte sin perder el depósito | plazo pago subasta | IN | Cluster | Media |
| 8 | IBI, comunidad y suministros atrasados: lo que heredas | IBI atrasados subasta | IN | Cluster | Media |

### Mes 3 — Autoridad (E-E-A-T + B2B)
| Sem | Título | KW | Intención | Tipo | Prioridad |
|---|---|---|---|---|---|
| 9 | Caso real: cómo compré un piso en Móstoles con 38% ROI (anonimizado) | inversión piso subasta rentabilidad | CO | Caso | Alta |
| 9 | Subastas judiciales Sevilla: guía 2026 | subastas judiciales sevilla | TX | Hub-evergreen | Media |
| 10 | Comprar local en subasta: rentabilidad y riesgos | comprar local subasta judicial | TX | Cluster | Media |
| 10 | Proindiviso en subasta: cómo invertir y salir con beneficio | proindiviso subasta inversor | CO | Cluster B2B | Media |
| 11 | NPLs inmobiliarios en España: oportunidad para inversor cualificado | NPL inmobiliario España | CO | Cluster B2B | Media |
| 11 | Subastas judiciales Málaga: guía 2026 | subastas judiciales málaga | TX | Hub-evergreen | Media |
| 12 | Subasta vs banco vs particular: comparativa 2026 | comprar piso subasta judicial | TX | Decisión | Alta |
| 12 | Cómo elegir abogado de subastas: 8 criterios | abogado subastas judiciales | CO | Comercial | Alta |

---

## 7. Plan de conversión (de tráfico a leads)

### Lead magnets a crear
1. **PDF "Checklist 47 puntos antes de pujar"** (gating con email) — pop-up exit-intent + sidebar.
2. **Calculadora ROI subasta** (JS embebido, calcula precio máximo de puja según reforma, cargas, ROI objetivo) — captura email para enviar resultado detallado.
3. **Newsletter "Subastas BOE de la semana"** — top 10 oportunidades curadas + comentario jurídico. Recurrencia y branding.
4. **Muestra de informe jurídico real** (anonimizada, 8-10 pp) — descargable, máximo activador para la venta.

### Optimización de CTAs (granular por intención)
- **Tráfico informacional** ("cómo pujar"): CTA = lead magnet PDF + newsletter.
- **Tráfico comercial** ("informe jurídico"): CTA = formulario directo con precio visible.
- **Tráfico transaccional** ("subastas madrid"): CTA = "Pide informe jurídico de cualquier subasta de esta lista" + sticky.
- **En fichas BOE**: CTA contextual con la referencia precargada — "Informe jurídico de ESTE activo · 72,60€ · entrega en 48h".

### Señales de confianza (faltan)
- Testimonios con foto/nombre/perfil profesional (3-5 mínimo).
- Track record: "X informes entregados", "Y € en activos analizados", "Z provincias cubiertas".
- Sello "Abogados colegiados" + nº ICAM/colegio.
- Garantía explícita: "Si detectamos carga ocultadora no reportada → devolución íntegra".
- Logos de medios donde haya aparecido CAFAVE (si los hay) o partners.

### Urgencia/escasez (real, no manipuladora)
- En fichas: countdown "Cierra en X días Y horas" (ya pueden tener fecha BOE).
- En landing informe: "Plazo medio entrega: 48h. Próximas subastas con cierre <7 días".
- Cupos: "Aceptamos 5 informes nuevos/día — quedan 2 hoy".

### Métricas a trackear
- Leads/día al formulario CAFAVE (objetivo: 15-20).
- CR del formulario por fuente (orgánico vs directo vs referral).
- Descargas de lead magnets → MQL → SQL.
- Posiciones de KWs A (informe jurídico) y E (provinciales top-5).
- Tráfico orgánico mensual y % desde KWs comerciales.
- Tiempo en página y profundidad de scroll en pillar posts.

---

## 8. Internal linking — reglas fijas

1. Cada **ficha BOE** linka a: hub provincial + landing /informe-juridico-subasta + 1 cluster relevante (cargas u ocupación según tipo de activo).
2. Cada **hub provincial** linka a: 3 pillars (informe, cómo pujar, riesgos) + guía evergreen de esa provincia + las 5 fichas más recientes.
3. Cada **cluster post** linka a su **pillar** (breadcrumb temático) y a la **landing comercial** del informe.
4. **Home** muestra: 4 pillars + últimos 6 posts + 3 fichas destacadas + calculadora ROI + form perfil inversor.
5. Anchor text variado: evitar "haz clic aquí" — usar keyword o variante semántica.

---

## 9. Priorización y secuencia recomendada (próximas 4 semanas)

**Sprint 1 (semana 1)**:
- Crear landing /informe-juridico-subasta (alta conversión).
- Publicar post pillar "Cargas ocultas" (post-001 — borrador adjunto).
- Implementar interlinking automático fichas → hub.
- Activar sticky CTA en fichas.

**Sprint 2 (semana 2)**:
- Publicar pillar "Cómo pujar paso a paso".
- Publicar "Piso ocupado: protocolo legal".
- Lead magnet PDF "Checklist 47 puntos".

**Sprint 3 (semana 3)**:
- Publicar guía Madrid (hub-evergreen extendido).
- Lanzar calculadora ROI.
- Activar newsletter semanal "Subastas BOE de la semana".

**Sprint 4 (semana 4)**:
- Optimizar 52 hubs provinciales con FAQ schema.
- Publicar pillar glosario.
- Solicitar testimonios reales a 3 clientes y montar sección de confianza.

---

## 10. Riesgos del plan y mitigaciones

- **Cumplimiento jurídico**: el contenido debe ser revisado por abogado colegiado (firma autor visible) → refuerza E-E-A-T y evita problemas deontológicos del Colegio de Abogados.
- **Canibalización**: hubs provinciales vs guías evergreen por provincia → diferenciar intent (hub = listado dinámico, guía = evergreen narrativo) con `<title>` y H1 distintos.
- **Volumen contenido vs recursos**: 22 artículos en 90 días ≈ 1,7/semana. Si solo hay 1 redactor, priorizar Mes 1 completo y reescalar.
- **Actualización fichas BOE caducadas**: las 982 fichas caducan → riesgo de soft-404. Implementar redirect a hub provincial o noindex+sustitución por archivo histórico.

---

**Siguiente acción inmediata**: publicar post-001 (borrador en `content/post-001-borrador.md`) y crear landing /informe-juridico-subasta.
