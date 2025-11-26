import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    MessageHandler, 
    CommandHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)

# SDK de Google Gemini AI
from google.ai.generativelanguage_v1beta import GenerativeServiceClient
from google.ai.generativelanguage_v1beta.types import (
    GenerateContentRequest, 
    Content
)
from google.api_core.client_options import ClientOptions


# ============================================================
# CONFIGURACIÓN DE CLAVES API
# ============================================================
# Nota: En producción, estas claves deben almacenarse como 
# variables de entorno por seguridad

OPENWEATHER_API = "ddd40326a89a5d85a04aac3dd8811047"
BOT_TOKEN = "8459560874:AAEmevDuABXe3Vhvy2gXw-3vw7XTDLg9cp4"
GEMINI_API_KEY = "AIzaSyCyaj6JBySNqQqMgXODB5doYQc3t1elYtU"


# ============================================================
# INICIALIZACIÓN DEL CLIENTE GEMINI
# ============================================================
client = GenerativeServiceClient(
    client_options=ClientOptions(api_key=GEMINI_API_KEY)
)


# ============================================================
# CONSTANTES DE RECONOCIMIENTO DE INTENCIONES
# ============================================================
SALUDOS = [
    "hola", 
    "buenos días", 
    "buenas tardes", 
    "buenas noches", 
    "hey", 
    "ola"
]

AGRADECIMIENTOS = [
    "gracias", 
    "muchas gracias", 
    "thanks"
]


# ============================================================
# MÓDULO DE IA GENERATIVA - GEMINI
# ============================================================
async def recomendar_ropa(temp: float, estado: str, humedad: int) -> str:
    """
    Genera recomendaciones de vestimenta usando Gemini AI.
    
    Args:
        temp: Temperatura en grados Celsius
        estado: Descripción del estado del clima
        humedad: Porcentaje de humedad relativa
        
    Returns:
        Recomendación de vestimenta personalizada
    """
    prompt = f"""
    Eres un asistente profesional de viajes.
    Basado en este clima:

    Temperatura: {temp} °C
    Estado: {estado}
    Humedad: {humedad}%

    Recomienda vestimenta ideal para viajar hoy.
    Máximo 5 líneas, usa emojis.
    """

    request = GenerateContentRequest(
        model="models/gemini-flash-latest",
        contents=[Content(parts=[{"text": prompt}])]
    )

    response = client.generate_content(request)
    return response.candidates[0].content.parts[0].text


# ============================================================
# MÓDULO DE CONSULTA CLIMÁTICA - OPENWEATHER API
# ============================================================
async def obtener_clima(ciudad: str) -> tuple:
    """
    Consulta datos meteorológicos de una ciudad específica.
    
    Args:
        ciudad: Nombre de la ciudad a consultar
        
    Returns:
        Tupla con (temperatura, descripción, humedad, mensaje_formateado)
    """
    url = (
        f"https://api.openweathermap.org/data/2.5/weather?"
        f"q={ciudad}&appid={OPENWEATHER_API}&units=metric&lang=es"
    )
    
    data = requests.get(url).json()

    # Validar respuesta de la API
    if data.get("cod") != 200:
        mensaje_error = (
            "⚠️ *No encontré esa ciudad.* "
            "Intenta con: Loja, Quito, Guayaquil, Cuenca…"
        )
        return None, None, None, mensaje_error

    # Extraer datos meteorológicos
    temp = data["main"]["temp"]
    desc = data["weather"][0]["description"].capitalize()
    humedad = data["main"]["humidity"]

    # Formatear mensaje de respuesta
    info = (
        f"🌍 *Clima en {ciudad.title()}*\n\n"
        f"🌡 Temperatura: *{temp}°C*\n"
        f"📌 Estado: *{desc}*\n"
        f"💧 Humedad: *{humedad}%*"
    )

    return temp, desc, humedad, info


# ============================================================
# MANEJADORES DE COMANDOS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador del comando /start.
    Muestra mensaje de bienvenida y botones de ciudades principales.
    """
    botones = [
        [
            InlineKeyboardButton("Quito", callback_data="Quito"),
            InlineKeyboardButton("Guayaquil", callback_data="Guayaquil")
        ],
        [
            InlineKeyboardButton("Cuenca", callback_data="Cuenca"),
            InlineKeyboardButton("Loja", callback_data="Loja")
        ]
    ]

    await update.message.reply_text(
        "👋 ¡Hola! Bienvenido a *ClimaBot Ecuador*.\n\n"
        "Elige una ciudad o escribe una:",
        reply_markup=InlineKeyboardMarkup(botones),
        parse_mode="Markdown"
    )


# ============================================================
# MANEJADORES DE CALLBACKS (BOTONES)
# ============================================================
async def manejar_boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Procesa la selección de ciudades mediante botones inline.
    """
    query = update.callback_query
    await query.answer()

    ciudad = query.data
    temp, estado, humedad, info = await obtener_clima(ciudad)

    # Almacenar datos en el contexto del usuario
    context.user_data.update({
        "temp": temp, 
        "estado": estado, 
        "humedad": humedad
    })

    await query.edit_message_text(
        info + "\n\n👕 ¿Quieres recomendación de vestimenta? (sí/no)",
        parse_mode="Markdown"
    )


# ============================================================
# MANEJADOR PRINCIPAL DE MENSAJES - MÁQUINA DE ESTADOS
# ============================================================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manejador principal del flujo conversacional.
    Implementa una máquina de estados para gestionar la conversación.
    """
    mensaje = update.message.text.strip().lower()

    # Inicializar estados si no existen
    if "esperando_ciudad" not in context.user_data:
        context.user_data["esperando_ciudad"] = True
    if "esperando_confirmacion" not in context.user_data:
        context.user_data["esperando_confirmacion"] = False

    # -------------------- ESTADO: SALUDOS --------------------
    if mensaje in SALUDOS:
        context.user_data["esperando_ciudad"] = True
        context.user_data["esperando_confirmacion"] = False
        
        await update.message.reply_text(
            "👋 ¡Hola! Soy *ClimaBot Ecuador*, tu asistente del clima "
            "en tiempo real. Estoy aquí para ayudarte a consultar el estado "
            "del tiempo en cualquier ciudad del país. 🌍✨ "
            "¿Cuál ciudad deseas revisar hoy?",
            parse_mode="Markdown"
        )
        return

    # -------------------- ESTADO: AGRADECIMIENTOS --------------------
    if mensaje in AGRADECIMIENTOS:
        context.user_data["esperando_confirmacion"] = True
        await update.message.reply_text(
            "😊 ¡Con gusto! ¿Quieres consultar otra ciudad? (sí/no)"
        )
        return

    # -------------------- ESTADO: NEGACIÓN (terminar) --------------------
    if mensaje == "no" and context.user_data.get("esperando_confirmacion"):
        context.user_data["esperando_confirmacion"] = False
        context.user_data["esperando_ciudad"] = True

        await update.message.reply_text(
            "😊 ¡Perfecto! Si necesitas consultar otro clima, "
            "solo escribe una ciudad 🌍."
        )
        return

    # -------------------- ESTADO: NEGACIÓN (sin vestimenta) --------------------
    if mensaje == "no" and not context.user_data.get("esperando_confirmacion"):
        context.user_data["esperando_confirmacion"] = True
        await update.message.reply_text(
            "Perfecto 😊 ¿Quieres consultar otra ciudad? (sí/no)"
        )
        return

    # -------------------- ESTADO: AFIRMACIÓN (nueva consulta) --------------------
    if mensaje in ["si", "sí"] and context.user_data.get("esperando_confirmacion"):
        context.user_data["esperando_confirmacion"] = False
        context.user_data["esperando_ciudad"] = True

        await update.message.reply_text(
            "Perfecto 😊, dime la nueva ciudad que deseas consultar 🌍"
        )
        return

    # -------------------- ESTADO: AFIRMACIÓN (vestimenta) --------------------
    if (mensaje in ["si", "sí"] and 
        "temp" in context.user_data and 
        not context.user_data["esperando_ciudad"]):
        
        # Generar recomendación con Gemini AI
        rec = await recomendar_ropa(
            context.user_data["temp"],
            context.user_data["estado"],
            context.user_data["humedad"]
        )

        await update.message.reply_text(
            f"👚 *Recomendación de vestimenta:*\n\n{rec}",
            parse_mode="Markdown"
        )

        context.user_data["esperando_confirmacion"] = True
        await update.message.reply_text(
            "¿Quieres consultar otra ciudad? (sí/no)"
        )
        return

    # -------------------- ESTADO: ESPERANDO CIUDAD --------------------
    if context.user_data["esperando_ciudad"]:
        ciudad = mensaje

        # Validación de entrada
        if ciudad.isnumeric():
            await update.message.reply_text("⚠️ Escribe solo letras.")
            return

        # Consultar clima
        temp, estado, humedad, info = await obtener_clima(ciudad)

        if temp is None:
            await update.message.reply_text(info, parse_mode="Markdown")
            return

        # Guardar datos del clima actual
        context.user_data["temp"] = temp
        context.user_data["estado"] = estado
        context.user_data["humedad"] = humedad
        context.user_data["esperando_ciudad"] = False

        await update.message.reply_text(
            info + "\n\n👕 ¿Quieres recomendación de vestimenta? (sí/no)",
            parse_mode="Markdown"
        )
        return

    # -------------------- ESTADO: MENSAJE DESCONOCIDO --------------------
    await update.message.reply_text(
        "🤔 No entendí eso. ¿Quieres consultar otra ciudad? (sí/no)"
    )


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def main():
    """
    Inicializa y ejecuta el bot de Telegram.
    Registra todos los manejadores necesarios.
    """
    # Construir aplicación
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Registrar manejadores
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(manejar_boton))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, responder)
    )

    # Iniciar bot
    print("🤖 ClimaBot Ecuador listo...")
    app.run_polling()


# ============================================================
# PUNTO DE ENTRADA
# ============================================================
if __name__ == "__main__":
    main()