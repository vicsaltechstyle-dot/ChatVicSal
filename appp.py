import os
import json
import logging
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import gspread
from gspread.exceptions import APIError
from datetime import datetime

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Inicialización de Flask
app = Flask(__name__)

# Cargar Menús desde la lógica que me enviaste
MENUS_DATA = {
    "menu_principal": [
        "Curso Excel",
        "Chat bot para negocio",
        "Automatización de Procesos con Python",
        "Diseño de Dashboards y análisis de datos en Excel",
        "Consultoría en Tecnología"
    ]
}

# Estado del chat por usuario (Persistencia en memoria, se reinicia con el servidor)
usuarios = {}

# ---------------------------- CONEXIÓN CON GOOGLE SHEETS -----------------------------
# **CORRECCIÓN CRÍTICA PARA RENDER:** Lee las credenciales de la variable de entorno GCP_CREDENTIALS

sheet = None  # Inicializa la variable sheet como None
try:
    # ⚠️ LECTURA CRÍTICA DE LA VARIABLE DE ENTORNO GCP_CREDENTIALS
    credentials_json_text = os.environ.get('GCP_CREDENTIALS')
    if not credentials_json_text:
        # Esto ocurrirá si olvidamos agregar la variable en Render
        raise ValueError("La variable de entorno GCP_CREDENTIALS no está configurada.")
        
    credentials = json.loads(credentials_json_text)
    
    # Autoriza gspread usando las credenciales cargadas
    gc = gspread.service_account_from_dict(credentials)

    # Abre la hoja de cálculo por su URL. 
    # **REEMPLAZA ESTA URL CON LA URL COMPLETA DE TU HOJA DE CÁLCULO REAL**
    sh = gc.open_by_url("TU_URL_DE_GOOGLE_SHEETS") 
    sheet = sh.sheet1 # Asume que queremos la primera hoja
    logging.info("✅ Conexión a Google Sheets exitosa.")

except APIError as e:
    # Error de API, usualmente permisos o URL incorrecta
    logging.error(f"❌ ERROR CRÍTICO DE CONEXIÓN A GOOGLE SHEETS (API): Revise permisos y URL de la hoja. {e}")
    sheet = None
except Exception as e:
    # Otros errores, como JSON inválido
    logging.error(f"❌ ERROR CRÍTICO DE CONEXIÓN A GOOGLE SHEETS: {e}")
    sheet = None


# ---------------------------- Funciones del Bot -----------------------------

def guardar_datos(nombre, telefono, correo, opcion, tipo_servicio):
    """Guarda los datos en Google Sheets si la conexión es exitosa."""
    global sheet
    
    if sheet is None:
        logging.error("No se pueden guardar datos: La conexión a Google Sheets ha fallado.")
        return False
        
    try:
        # Fila de datos a insertar
        datos_cliente = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            nombre,
            telefono,
            correo,
            opcion,
            tipo_servicio
        ]
        # Inserta la fila en la hoja
        sheet.append_row(datos_cliente)
        logging.info(f"Datos guardados: {datos_cliente}")
        return True
    except Exception as e:
        logging.error(f"Error al escribir en Google Sheets: {e}")
        return False


# ---------------------------- Rutas Webhook -----------------------------

@app.route("/", methods=['GET'])
def home():
    """Ruta de salud para verificar si Render está funcionando."""
    if sheet is None:
        return "Bot de WhatsApp (VicSalTechStyle) - Estado: 🔴 ERROR DE CONEXIÓN A GOOGLE SHEETS. Ver logs de Render para detalles.", 500
    return "Bot de WhatsApp (VicSalTechStyle) - Estado: 🟢 LIVE. ¡Listo para recibir mensajes!", 200


@app.route("/wa_webhook", methods=['POST'])
def whatsapp_bot():
    """Maneja los mensajes entrantes de Twilio y ejecuta la lógica de conversación."""
    
    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "") # Número de WhatsApp del cliente
    
    resp = MessagingResponse()
    msg = resp.message() # El objeto de mensaje para adjuntar al TwiML
    
    logging.info(f"Mensaje entrante desde {from_number}: {incoming_msg}")
    
    # 1. Inicializar/Cargar estado del usuario
    if from_number not in usuarios:
        usuarios[from_number] = {"estado": "menu1"} 

    estado = usuarios[from_number]["estado"]

    # --- FLUJO DE LA CONVERSACIÓN (Máquina de estados simple) ---

    if estado == "menu1" or incoming_msg.lower() in ["reiniciar", "start"]:
        # Muestra el menú principal
        menu_text = "¡Hola, bienvenido a VicSalTech! 😄 Soy tu asistente virtual.\n¿Cómo puedo ayudarte?\n"
        for i, opcion in enumerate(MENUS_DATA["menu_principal"], start=1):
            menu_text += f"*{i}.* {opcion}\n" # Usando *i.* para resaltar
        menu_text += "\nPor favor, escribe el número de tu opción (1 a 5):"
        msg.body(menu_text)
        usuarios[from_number]["estado"] = "esperando_opcion"
        
    elif estado == "esperando_opcion":
        try:
            opcion_index = int(incoming_msg) - 1
            opciones_disponibles = MENUS_DATA["menu_principal"]
            
            opcion_seleccionada = opciones_disponibles[opcion_index]
            usuarios[from_number]["opcion"] = opcion_seleccionada
            usuarios[from_number]["estado"] = "menu2"
            
            # Muestra el submenú de Cotización/Solicitud
            msg.body(f"Elegiste: *{opcion_seleccionada}*\n\n*1.* Solicitar Cotización\n*2.* Solicitar Servicio\n\nEscribe el número:")
            
        except (ValueError, IndexError):
            msg.body("🚫 Opción inválida. Por favor escribe un número válido del menú (1 a 5).")
    
    elif estado == "menu2":
        if incoming_msg in ["1", "2"]:
            tipo_servicio = "Cotización" if incoming_msg == "1" else "Servicio"
            usuarios[from_number]["tipo_servicio"] = tipo_servicio
            usuarios[from_number]["estado"] = "nombre"
            msg.body("📝 Perfecto. Por favor escribe tu nombre completo:")
        else:
            msg.body("🚫 Opción inválida. Por favor escribe 1 para Cotización o 2 para Servicio.")
    
    elif estado == "nombre":
        usuarios[from_number]["nombre"] = incoming_msg
        usuarios[from_number]["estado"] = "telefono"
        msg.body("📞 Gracias. Por favor escribe tu número de teléfono (solo números):")
    
    elif estado == "telefono":
        usuarios[from_number]["telefono"] = incoming_msg
        usuarios[from_number]["estado"] = "correo"
        msg.body("📧 Entendido. Por favor escribe tu correo electrónico:")
    
    elif estado == "correo":
        usuarios[from_number]["correo"] = incoming_msg
        
        # 4. GUARDAR DATOS Y FINALIZAR
        guardar_datos(
            usuarios[from_number].get("nombre", "N/A"),
            usuarios[from_number].get("telefono", from_number),
            usuarios[from_number].get("correo", "N/A"),
            usuarios[from_number].get("opcion", "N/A"),
            usuarios[from_number].get("tipo_servicio", "N/A")
        )
        
        msg.body("✅ ¡Registro Completado! ¡Muchas Gracias! Uno de nuestros expertos se pondrá en contacto contigo a la brevedad.\n\nEscribe *reiniciar* si quieres empezar de nuevo.")
        usuarios.pop(from_number)  # Elimina el estado para reiniciar la próxima vez
    
    else:
        # Estado de resguardo
        msg.body("❓ Error inesperado. Escribe *reiniciar* para empezar de nuevo.")
        usuarios.pop(from_number) # Limpia el estado

    return str(resp)

