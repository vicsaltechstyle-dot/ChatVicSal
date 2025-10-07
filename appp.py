# Importaciones necesarias
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import logging 

# Configuración de Logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# =======================================================
# ⚠️ MENÚ INTERNO (Corregido y Limpiado)
# =======================================================
menus_data = {
    "menu_principal": [
        "Curso Excel",
        "Chat bot para negocio",
        "Automatización de Procesos con Python",
        "Diseño de Dashboards y análisis de datos en Excel",
        "Consultoría en Tecnología"
    ]
}


# --- CONFIGURACIÓN DE RUTAS Y CONEXIÓN ---

# Se construye la ruta relativa del archivo credentials.json
ruta_base = os.path.dirname(__file__) 
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
ruta_credenciales = os.path.join(ruta_base, "credentials.json")

# Conexión a Google Sheets
try:
    # ⚠️ ASUME que 'credentials.json' está en la misma carpeta
    creds = ServiceAccountCredentials.from_json_keyfile_name(ruta_credenciales, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Registro_clientes").sheet1
    logging.info("✅ Conexión a Google Sheets exitosa.")
except Exception as e:
    logging.error(f"❌ ERROR CRÍTICO DE CONEXIÓN A GOOGLE SHEETS: {e}")
    sheet = None 

# Función para guardar datos
def guardar_datos(nombre, telefono, correo, opcion, tipo_servicio):
    if sheet:
        try:
            fecha_hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([fecha_hora, nombre, telefono, correo, opcion, tipo_servicio])
            logging.info(f"💾 Datos guardados: {nombre}, {opcion}")
        except Exception as e:
            logging.error(f"❌ ERROR al guardar en Google Sheets: {e}")
            
# Estado del chat por usuario (Persistencia en memoria)
usuarios = {}

# =======================================================
# RUTA WEBHOOK DE TWILIO (MÉTODO POST)
# =======================================================
@app.route("/whatsapp", methods=["POST"])
def whatsapp_bot():
    """Maneja los mensajes entrantes de Twilio y ejecuta la lógica de conversación."""
    
    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "") 
    resp = MessagingResponse()
    msg = resp.message()
    
    # 1. Inicializar/Cargar estado del usuario
    if from_number not in usuarios:
        usuarios[from_number] = {"estado": "menu1"} 

    estado = usuarios[from_number]["estado"]

    # --- FLUJO DE LA CONVERSACIÓN (Máquina de estados simple) ---

    if estado == "menu1" or incoming_msg.lower() in ["reiniciar", "start"]:
        menu_text = "Hola, bienvenido a VicSalTech 😄\n¿Cómo puedo ayudarte?\n"
        for i, opcion in enumerate(menus_data["menu_principal"], start=1):
            # Se usa el índice (i) para la numeración, no la opción en sí
            menu_text += f"{i}. {opcion}\n"
        menu_text += "Por favor escribe el número de tu opción."
        msg.body(menu_text)
        usuarios[from_number]["estado"] = "esperando_opcion"
        
    elif estado == "esperando_opcion":
        try:
            opcion_index = int(incoming_msg) - 1
            # Accede a la opción usando el índice numérico
            opcion_seleccionada = menus_data["menu_principal"][opcion_index]
            usuarios[from_number]["opcion"] = opcion_seleccionada
            usuarios[from_number]["estado"] = "menu2"
            msg.body(f"Elegiste: {opcion_seleccionada}\n1. Cotización\n2. Solicitar servicio\nEscribe el número:")
            
        except (ValueError, IndexError):
            msg.body("🚫 Opción inválida. Por favor escribe un número válido del menú.")
    
    elif estado == "menu2":
        if incoming_msg in ["1", "2"]:
            tipo_servicio = "Cotización" if incoming_msg == "1" else "Solicitud"
            usuarios[from_number]["tipo_servicio"] = tipo_servicio
            usuarios[from_number]["estado"] = "nombre"
            msg.body("📝 Perfecto. Por favor escribe tu nombre completo:")
        else:
            msg.body("🚫 Opción inválida. Por favor escribe 1 para Cotización o 2 para Solicitar servicio.")
    
    elif estado == "nombre":
        usuarios[from_number]["nombre"] = incoming_msg
        usuarios[from_number]["estado"] = "telefono"
        msg.body("📞 Gracias. Por favor escribe tu número de teléfono:")
    
    elif estado == "telefono":
        usuarios[from_number]["telefono"] = incoming_msg
        usuarios[from_number]["estado"] = "correo"
        msg.body("📧 Entendido. Por favor escribe tu correo electrónico:")
    
    elif estado == "correo":
        usuarios[from_number]["correo"] = incoming_msg
        
        # 4. GUARDAR DATOS Y FINALIZAR
        guardar_datos(
            usuarios[from_number]["nombre"],
            usuarios[from_number]["telefono"],
            usuarios[from_number]["correo"],
            usuarios[from_number]["opcion"],
            usuarios[from_number]["tipo_servicio"]
        )
        
        msg.body("✅ ¡Registro Completado! ¡Muchas Gracias!. Uno de nuestros expertos se pondrá en contacto contigo a la brevedad. Escribe 'reiniciar' si quieres empezar de nuevo.")
        usuarios.pop(from_number) 
    
    else:
        msg.body("❓ Error inesperado. Escribe 'reiniciar' para empezar de nuevo.")
        usuarios.pop(from_number) 

    return str(resp)
# Se elimina app.run() para que Gunicorn/Render gestione el inicio.
