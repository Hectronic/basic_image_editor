# 🏛️ Constitución del Repositorio (Leyes Inmutables)

Este documento define las directrices inmutables y no negociables para el desarrollo
y la generación de código asistida por IA en este repositorio.

## 🔒 1. Principios de Arquitectura
- Separación estricta de capas según el estándar de DIA.
- Ninguna regla de negocio debe acoplarse directamente a drivers de infraestructura o transporte.
- Toda funcionalidad se respalda previamente en contratos ejecutables en `openspec/`.

## 🧪 2. Calidad y Pruebas
- Cobertura mínima obligatoria: **80%**.
- Ningún commit sin pasar la suite completa de pruebas locales.
- Todo bugfix debe incluir previamente un test que reproduzca el fallo.

## 🛑 3. Git y Seguridad
- Prohibido commitear directamente en `master`, `main` o `develop`.
- Prohibido hardcodear secretos, tokens o credenciales.
