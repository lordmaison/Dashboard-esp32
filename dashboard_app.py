
import queue
import math
from datetime import datetime

import pandas as pd
import paho.mqtt.client as mqtt
import streamlit as st


# ==========================================
# 1. CONFIGURACIÓN
# ==========================================

BROKER_IP = "broker.hivemq.com"
BROKER_PORT = 1883
TOPIC = "esp32/variables"

MAX_MOSTRAR = 30
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

# Historial completo, sin límite de registros
if "historial" not in st.session_state:
    st.session_state.historial = []

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
                    "Tiempo": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S.%f"
                    )[:-3],

                    "Temperatura": valor,
                }

                # Guardar sin eliminar registros anteriores
                st.session_state.historial.append(registro)

        except queue.Empty:
            break


    # DataFrame con TODO el historial
    df = pd.DataFrame(st.session_state.historial)

    # DataFrame para visualización
    df_visual = df.tail(MAX_MOSTRAR)


    # ==========================================
    # 7. EXPORTACIÓN CSV
    # ==========================================

    st.subheader("📥 Exportación de datos")

    if not df.empty:

        csv = df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="📥 Descargar historial completo CSV",
            data=csv,
            file_name="historial_completo_temperaturas.csv",
            mime="text/csv",
            key="descargar_csv",
        )

        st.caption(
            f"Registros almacenados: {len(df)} | "
            f"Registros exportados: {len(df)}"
        )

    else:

        st.button(
            "📥 Descargar historial completo CSV",
            disabled=True,
            key="descargar_csv_vacio",
        )

        st.caption("Esperando datos para generar el archivo CSV.")


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
    # 9. GRÁFICA
    # ==========================================

    if not df_visual.empty:

        st.subheader("📈 Temperatura en tiempo real")

        st.line_chart(
            df_visual.set_index("Tiempo")["Temperatura"],
            y_label="Temperatura (°C)",
            x_label="Fecha y hora",
        )


        # ==========================================
        # 10. TABLA DE LECTURAS
        # ==========================================

        st.subheader("📋 Últimas lecturas")

        st.dataframe(
            df_visual.tail(5),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            f"Esperando datos del sensor. "
            f"Tópico MQTT: {TOPIC}"
        )


    # ==========================================
    # 11. ERRORES MQTT
    # ==========================================

    if st.session_state.mqtt_error:

        st.error(
            f"Error de conexión MQTT: "
            f"{st.session_state.mqtt_error}"
        )


# ==========================================
# 12. EJECUTAR DASHBOARD
# ==========================================

dashboard()
