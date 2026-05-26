# RGPD — Checklist a validar antes de lanzar los lead magnets

> Esta lista identifica **qué debe estar cubierto en el aviso legal y la política de privacidad** del sitio antes de capturar emails con estos lead magnets. **No es asesoramiento legal vinculante**; valídalo con un asesor de privacidad o el DPD (si lo hay).

Marco normativo aplicable:

- **RGPD** (Reglamento UE 2016/679)
- **LOPDGDD** (Ley Orgánica 3/2018 de Protección de Datos Personales y Garantía de Derechos Digitales)
- **LSSI-CE** (Ley 34/2002 de Servicios de la Sociedad de la Información)

---

## 1. Identificación del responsable del tratamiento

- [ ] Razón social completa de **CAFAVE Investment** (o entidad jurídica titular del sitio).
- [ ] CIF.
- [ ] Domicilio fiscal.
- [ ] Email de contacto del responsable (`info@cafave.com` o el oficial).
- [ ] Si aplica: **DPD** (Delegado de Protección de Datos) y vía de contacto.
- [ ] Inscripción del Colegio de Abogados aplicable (ICAS / ICAM / ICAB…) y nº colegiado del firmante.

---

## 2. Base legal del tratamiento

Por lead magnet, declarar la base legal en la política de privacidad:

### 2.1. Checklist PDF gated

- **Finalidad**: enviar al usuario el PDF solicitado.
- **Base legal**: **ejecución de medidas precontractuales / consentimiento explícito** (art. 6.1.a y/o 6.1.b RGPD).
- **Datos recogidos**: nombre, email, IP, user-agent, checkbox "interesado en informes" (perfilado básico), checkbox de consentimiento.
- **Plazo de conservación**:
  - Si no abre el email ni descarga en 30 días → borrar pasados 6 meses.
  - Si descarga → conservar mientras el usuario no solicite supresión, máximo 2 años desde la última interacción.

### 2.2. Newsletter "Subastas BOE de la semana"

- **Finalidad**: envío de comunicaciones comerciales semanales.
- **Base legal**: **consentimiento explícito** (art. 6.1.a RGPD + art. 21 LSSI-CE).
- **Datos recogidos**: email, provincia preferida (opcional), IP de alta, IP/fecha de confirmación (prueba de consentimiento).
- **Plazo de conservación**: mientras el usuario esté suscrito. Tras unsubscribe, mantener email + token de baja **2 años** como prueba de baja efectiva (recomendado por AEPD), luego borrar.

---

## 3. Información obligatoria a mostrar en el formulario

Cada formulario **debe mostrar antes del checkbox de consentimiento** (o vinculado a él):

- [ ] **Responsable**: CAFAVE Investment SL (o razón social).
- [ ] **Finalidad** clara (envío del checklist / newsletter semanal).
- [ ] **Base legal** (consentimiento).
- [ ] **Destinatarios** (no se cederán datos a terceros salvo obligación legal; mencionar SMTP provider Hostinger como **encargado del tratamiento** si procede).
- [ ] **Derechos**: acceso, rectificación, supresión, oposición, portabilidad y limitación. Email donde ejercerlos.
- [ ] **Plazo de conservación**.
- [ ] **Enlace a política de privacidad completa**.

> Ambos shortcodes (`[cafave_checklist_form]` y `[cafave_newsletter_form]`) ya incluyen un checkbox de consentimiento con enlace a `/aviso-legal`. **Esa página debe existir y contener todo lo anterior antes de lanzar.**

---

## 4. Doble opt-in (newsletter)

- [x] **Implementado**: el plugin envía email de confirmación con token único; solo tras clic se marca `status = 'active'`.
- [x] **Token de confirmación** con TTL de 7 días.
- [x] **Prueba de consentimiento**: guarda IP de alta + IP/fecha de confirmación.
- [ ] **Documentar** en política de privacidad que existe doble opt-in y por qué.

---

## 5. Derecho de baja efectivo

- [x] **Link de unsubscribe** en cada newsletter, con token único y sin requerir login.
- [x] **Endpoint `/cafave/v1/newsletter/unsubscribe`** funcional.
- [x] **Header `List-Unsubscribe`** en cada email (RFC 8058 / mailto fallback).
- [ ] **Confirmación visual** post-baja: la página HTML que devuelve el plugin ya lo hace.
- [ ] **Verificar** que ningún cron pueda re-añadir un email dado de baja sin nuevo opt-in.

---

## 6. Cookies y trackers

- [ ] El sitio debe tener **banner de cookies** que cumpla con las **Guías AEPD 2024** (rechazo tan fácil como aceptación).
- [ ] **No cargar** scripts de tracking de terceros (Analytics, FB Pixel, etc.) en el formulario antes del consentimiento.
- [ ] Las **UTMs** que el script añade a los enlaces de la newsletter **no son cookies** y no requieren consentimiento adicional, pero Analytics sí.

---

## 7. Seguridad y minimización

- [x] **HTTPS obligatorio** en todos los formularios (verificar certificado).
- [x] **Honeypot** (campo `website` oculto) — anti-spam mínimo.
- [x] **Rate limiting** por IP en endpoints REST (5 submits/hora).
- [x] **Sanitización**: `sanitize_email`, `sanitize_text_field`, `is_email`.
- [x] **Tokens criptográficos** (`random_bytes(24)`) — no usar IDs predecibles.
- [x] **Minimización**: solo se piden los datos estrictamente necesarios.
- [ ] **Acceso a la tabla de leads**: limitar a roles `administrator` y `editor`. Revisar quién tiene acceso al panel WP.
- [ ] **Backups cifrados** y plan de borrado de backups antiguos.

---

## 8. Encargados del tratamiento

Identificar y documentar (con cláusula contractual o referencia):

- [ ] **Hostinger** (hosting + SMTP) — verificar que tienen DPA firmado.
- [ ] **WordPress.com Jetpack** si está activo — DPA disponible en sus términos.
- [ ] Cualquier otro plugin que procese emails (WP Mail SMTP, etc.).

---

## 9. Comunicaciones comerciales (LSSI-CE)

Para la newsletter (es comunicación comercial):

- [ ] **Identificar como comunicación comercial** en el asunto o cuerpo (la palabra "newsletter" o "boletín" es suficiente para AEPD).
- [ ] **Identificar al emisor** (CAFAVE Investment) en el cuerpo del email.
- [ ] **Link de baja en cada email** (ya implementado).
- [ ] **Solo a quienes hayan dado consentimiento expreso** (ya garantizado por doble opt-in).

---

## 10. Deontología profesional (Estatuto General Abogacía)

Como CAFAVE está integrado por abogados colegiados:

- [ ] **Verificar normativa de publicidad** del Colegio de Abogados aplicable (ICAS / ICAM / ICAB).
- [ ] **No prometer resultados** ("garantizamos rentabilidad" = no permitido).
- [ ] **Firma identificable** del autor responsable en contenidos jurídicos.
- [ ] **Aviso legal** que indique claramente que el contenido es divulgativo, no asesoramiento individualizado.

> Los textos del checklist PDF y del email transaccional **ya incluyen** este aviso ("este documento tiene carácter divulgativo…"). Revisar que se mantiene en toda la línea editorial.

---

## 11. Antes de lanzar — comprobaciones finales

- [ ] La página `/aviso-legal` existe y contiene **todos los apartados** de los puntos 1-3.
- [ ] Política de privacidad incluye específicamente los lead magnets y sus bases legales.
- [ ] Test real: enviar lead desde IP propia, recibir email, descargar PDF, ejercer derecho de supresión por email.
- [ ] Test real: suscribirse a newsletter, confirmar, recibir test newsletter, dar de baja, comprobar que no se vuelve a recibir.
- [ ] **Validación con asesor jurídico/DPD** firmando el visto bueno.

---

**Cuando todos los checkboxes estén marcados, el sistema está listo para producción.**

Si quieres, puedo generar también:

1. Borrador de página `/aviso-legal` con los puntos 1-3 ya redactados.
2. Borrador de cláusulas para contratos con encargados del tratamiento.
3. Plantilla de respuesta a ejercicio de derechos RGPD.

Pídelo cuando lo necesites.
