
import queue
import math
from datetime import datetime
from collections import deque

import pandas as pd
import paho.mqtt.client as mqtt
import streamlit as st


# ==========================================
# 1. CONFIGURACIÓN
# ==========================================

BROKER_IP = "broker.hivemq.com"
BROKER_PORT = 1883
TOPIC = "esp32/variables"

MAX_REGISTROS = 30
INTERVALO_ACTUALIZACION = "1s"

st.set_page_config(
    page_title="Visualización de Variables",
    page_icon="🌡️",
    layout="wide",
)


# ==========================================
# 2. ESTADO DE LA APLICACIÓN
# ==========================================

if "data_queue" not in st.session_state:
    st.session_state.data_queue = queue.Queue()

if "historial" not in st.session_state:
    st.session_state.historial = deque(maxlen=MAX_REGISTROS)

if "mqtt_connected" not in st.session_state:
    st.session_state.mqtt_connected = False

if "mqtt_error" not in st.session_state:
    st.session_state.mqtt_error = None


# ==========================================
# 3. CALLBACKS MQTT
# ==========================================

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(TOPIC)
        userdata.put(("status", True))
    else:
        userdata.put(("status", False))


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    userdata.put(("status", False))


def on_message(client, userdata, msg):
    try:
        temperatura = float(msg.payload.decode("utf-8").strip())

        # Validación del rango del sensor DS18B20
        if not math.isfinite(temperatura):
            return

        if not -55 <= temperatura <= 125:
            return

        userdata.put(("data", temperatura))

    except (ValueError, UnicodeDecodeError):
        pass


# ==========================================
# 4. INICIALIZACIÓN MQTT
# ==========================================

if "mqtt_client" not in st.session_state:

    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            userdata=st.session_state.data_queue,
        )

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message

        client.connect(BROKER_IP, BROKER_PORT, 60)
        client.loop_start()

        st.session_state.mqtt_client = client

    except Exception as e:
        st.session_state.mqtt_error = str(e)


# ==========================================
# 5. INTERFAZ PRINCIPAL
# ==========================================

st.title("🌡️ Dashboard: Monitoreo Remoto Wi-Fi")

st.markdown(
    "Visualización en tiempo real de las lecturas del sensor "
    "**DS18B20**, transmitidas mediante una **ESP32** "
    "utilizando el protocolo MQTT."
)

st.divider()


# ==========================================
# 6. ACTUALIZACIÓN DEL DASHBOARD
# ==========================================

@st.fragment(run_every=INTERVALO_ACTUALIZACION)
def dashboard():

    # Procesar mensajes pendientes
    while True:
        try:
            tipo, valor = st.session_state.data_queue.get_nowait()

            if tipo == "status":
                st.session_state.mqtt_connected = valor

            elif tipo == "data":
                registro = {
                    "Tiempo": datetime.now().strftime("%H:%M:%S"),
                    "Temperatura": valor,
                }

                st.session_state.historial.append(registro)

        except queue.Empty:
            break

    # Crear DataFrame
    df = pd.DataFrame(list(st.session_state.historial))


    # ==========================================
    # 7. EXPORTACIÓN DE DATOS CSV
    # ==========================================

    st.subheader("📥 Exportación de datos")

    if not df.empty:

        csv = df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="📥 Descargar datos CSV",
            data=csv,
            file_name="registro_temperaturas.csv",
            mime="text/csv",
            key="descargar_csv",
        )

        st.caption(
            f"El archivo contiene {len(df)} registros "
            "de temperatura."
        )

    else:
        st.button(
            "📥 Descargar datos CSV",
            disabled=True,
            key="descargar_csv_vacio",
        )

        st.caption("No hay datos disponibles para exportar.")


    # ==========================================
    # 8. INDICADORES
    # ==========================================

    col1, col2, col3 = st.columns(3)

    if not df.empty:

        temperatura_actual = df["Temperatura"].iloc[-1]
        temperatura_maxima = df["Temperatura"].max()

        col1.metric(
            "Temperatura Actual",
            f"{temperatura_actual:.2f} °C",
        )

        col3.metric(
            "Máxima Registrada",
            f"{temperatura_maxima:.2f} °C",
        )

    else:
        col1.metric("Temperatura Actual", "-- °C")
        col3.metric("Máxima Registrada", "-- °C")

    if st.session_state.mqtt_connected:
        col2.metric("Estado de Red", "Conectado 🟢")
    else:
        col2.metric("Estado de Red", "Desconectado 🔴")


    # ==========================================
    # 9. GRÁFICA E HISTORIAL
    # ==========================================

    if not df.empty:

        st.subheader("📈 Temperatura en tiempo real")

        st.line_chart(
            df.set_index("Tiempo")["Temperatura"],
            y_label="Temperatura (°C)",
            x_label="Hora",
        )

        st.subheader("📋 Últimas lecturas")

        st.dataframe(
            df.tail(5),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            f"Esperando datos del sensor. "
            f"Tópico MQTT: {TOPIC}"
        )


    # ==========================================
    # 10. ERRORES MQTT
    # ==========================================

    if st.session_state.mqtt_error:
        st.error(
            f"Error de conexión MQTT: "
            f"{st.session_state.mqtt_error}"
        )


# ==========================================
# 11. EJECUTAR DASHBOARD
# ==========================================

dashboard()
