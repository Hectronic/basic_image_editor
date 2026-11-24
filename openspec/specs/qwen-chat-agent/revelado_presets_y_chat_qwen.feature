# language: es
Característica: Estudio de Revelado RAW 16-bit, Galería de Presets HD, Asistente Inteligente y Chat IA Qwen 100% Integrado
  Como fotógrafo y usuario de Basic Image Editor
  Quiero revelar archivos RAW de 16 bits, aplicar o crear presets fotográficos y conversar con un modelo Qwen integrado 100% en proceso (0.5B / 1.5B GGUF sin servicios externos)
  Para editar fotografías con precisión cromática, rapidez en tiempo real y control en lenguaje natural

  Antecedentes:
    Dado que la aplicación Basic Image Editor está inicializada con el motor RAW de 16 bits, la galería de presets y los modelos GGUF integrados en "models/"
    Y el modelo de imagen tiene cargada una fotografía activa en una pestaña de edición

  Escenario: Decodificación RAW de 16 bits y ajuste paramétrico no destructivo por LUT
    Cuando el usuario ajusta la exposición EV a "+0.35", las sombras a "+0.40" y la nitidez estructural HD a "0.40"
    Entonces el motor de revelado aplica la curva LUT combinada de 256 entradas con protección soft-knee de altas luces
    Y la luminancia media de la imagen revelada aumenta preservando el rango dinámico en "[0.0, 1.0]"

  Escenario: Aplicación de preset fotográfico con mezcla continua de intensidad y deshacer
    Cuando el usuario selecciona el preset "electric_chroma_hd" con una intensidad del "80%"
    Entonces el modelo establece el preset activo en "electric_chroma_hd" con intensidad "0.80"
    Y se registra el estado "Preset: Electric Chroma HD" en el historial de deshacer
    Y al ejecutar la acción de deshacer el preset activo vuelve a "none"

  Escenario: Diagnóstico automático de escena, Auto-Revelado 1-clic y Recorte Inteligente 1:1
    Cuando el asistente analiza la escena de la imagen activa y el usuario solicita el Auto-Revelado óptimo
    Entonces el sistema calcula y aplica automáticamente EV, sombras, altas luces, denoise, nitidez y el preset recomendado
    Y cuando el usuario solicita el encuadre inteligente 1:1 para Instagram la imagen se recorta al cuadrado de máxima saliencia visual

  Escenario: Aplicación y modificación de presets mediante el Chat IA con Qwen GGUF integrado (0.5B / 1.5B en proceso)
    Cuando el usuario escribe en el chat de Qwen "Pon cinestill al 80%, abre sombras y guárdalo como Nocturno Custom"
    Entonces el modelo Qwen GGUF en proceso interpreta la instrucción y devuelve el comando estructurado JSON sin llamar a servidores externos
    Y el motor registra el nuevo preset personalizado "custom_nocturno_custom" en la galería de presets
    Y la imagen activa aplica el preset "custom_nocturno_custom" actualizando los controles e historial de la interfaz

  Escenario: Respaldo NLU autónomo integrado
    Cuando el usuario envía el mensaje "pon cinestill al 75% y sube las sombras" en el chat
    Entonces el motor híbrido valida los rangos y aplica el preset "cinestill_800t" con intensidad "0.75" y apertura de sombras
