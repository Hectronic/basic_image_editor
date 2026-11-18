# 🌐 Reglas Globales y Convenciones de Arquitectura (DIA)

Este documento define las reglas transversales de negocio e interoperabilidad
que aplican a todos los contratos y especificaciones del repositorio.

---

## 🔒 1. Seguridad y Autenticación
- Todos los endpoints protegidos requieren header: `Authorization: Bearer <JWT>`.
- Si el token falta o expira, responder HTTP 401:
  ```json
  {
    "error": "Token de autenticación inválido o expirado",
    "code": "UNAUTHORIZED"
  }
  ```
- Si el rol carece de privilegios, responder HTTP 403:
  ```json
  {
    "error": "Acceso denegado para el recurso solicitado",
    "code": "FORBIDDEN"
  }
  ```

---

## 🏷️ 2. Trazabilidad y Headers Corporativos
- Toda petición debe propagar el header `X-Trace-Id` (UUID v4) para trazabilidad en Cloud Logging.
- Toda especificación o cambio debe vincularse 1 a 1 con su ticket Jira correspondiente (`MANTEC-XXXXX`).

---

## ⏱️ 3. Formato de Fechas y Números
- Formato de fechas y marcas de tiempo: **ISO-8601 UTC** estricto (`YYYY-MM-DDTHH:mm:ss.sssZ`).
- Monedas e importes monetarios: Siempre representados como enteros en céntimos o con dos decimales exactos, especificando moneda (`EUR`).

---

## ⚠️ 4. Formato Homogéneo de Errores (RFC 7807)
```json
{
  "error": "Descripción clara del error en español",
  "code": "CODIGO_ERROR_SEMANTICO",
  "details": []
}
```

---

## 🥒 5. Contratos BDD en Español
- Todo contrato ejecutable debe incluir `# language: es` y emplear la terminología canónica (`Característica:`, `Escenario:`, `Dado/Cuando/Entonces`).
