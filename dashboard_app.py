import queue
import math
import altair as alt
import pandas as pd
import paho.mqtt.client as mqtt
import streamlit as st

from datetime import datetime
from zoneinfo import ZoneInfo

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

if "historial" not in st.session_state:
    st.session_state.historial = []

if "mqtt_connected" not in st.session_state:
    st.session_state.mqtt_connected = False

if "mqtt_error" not in st.session_state:
    st.session_state.mqtt_error = None

if "grafica_pausada" not in st.session_state:
    st.session_state.grafica_pausada = False

if "historial_grafica" not in st.session_state:
    st.session_state.historial_grafica = pd.DataFrame()


# ==========================================
# 3. FORMATO DE HORA
# ==========================================

def formato_hora(fecha_hora):
    return fecha_hora.strftime("%I:%M:%S%p").lstrip("0").lower()


# ==========================================
# 4. CALLBACKS MQTT
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
# 5. INICIALIZACIÓN MQTT
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
# 6. INTERFAZ PRINCIPAL
# ==========================================

st.title("🌡️ Dashboard: Monitoreo Remoto Wi-Fi")

st.markdown(
    "Visualización en tiempo real de las lecturas del sensor "
    "**DS18B20**, transmitidas mediante una **ESP32** "
    "utilizando el protocolo MQTT."
)

st.divider()


# ==========================================
# 7. ACTUALIZACIÓN DEL DASHBOARD
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

            # Obtener fecha y hora de Bogotá
            ahora = datetime.now(ZoneInfo("America/Bogota"))

            registro = {
                "Fecha": ahora.strftime("%Y-%m-%d"),
                "Hora": formato_hora(ahora),
                "Temperatura (°C)": valor,
                "Momento": ahora,
            }

            # Guardar la lectura en el historial
            st.session_state.historial.append(registro)

        except queue.Empty:
            break


    # DataFrame con todo el historial
    df = pd.DataFrame(
        st.session_state.historial,
        columns=[
            "Fecha",
            "Hora",
            "Temperatura (°C)",
            "Momento",
        ]
    )

    # DataFrame para visualización general
    df_visual = df.tail(MAX_MOSTRAR)


    # ==========================================
    # 8. EXPORTACIÓN CSV
    # ==========================================

    st.subheader("📥 Exportación de datos")

    if not df.empty:

        # Exportar únicamente las columnas solicitadas
        df_csv = df[
            ["Fecha", "Hora", "Temperatura (°C)"]
        ]

        csv = df_csv.to_csv(index=False).encode("utf-8-sig")

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
    # 9. INDICADORES DE TEMPERATURA
    # ==========================================

    st.subheader("📊 Indicadores")

    if not df.empty:

        temperatura_actual = df["Temperatura (°C)"].iloc[-1]
        temperatura_minima = df["Temperatura (°C)"].min()
        temperatura_maxima = df["Temperatura (°C)"].max()
        temperatura_promedio = df["Temperatura (°C)"].mean()

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric(
            "Temperatura Actual",
            f"{temperatura_actual:.2f} °C"
        )

        col2.metric(
            "Temperatura Mínima",
            f"{temperatura_minima:.2f} °C"
        )

        col3.metric(
            "Temperatura Máxima",
            f"{temperatura_maxima:.2f} °C"
        )

        col4.metric(
            "Temperatura Promedio",
            f"{temperatura_promedio:.2f} °C"
        )

        if st.session_state.mqtt_connected:
            col5.metric("Estado de Red", "Conectado 🟢")
        else:
            col5.metric("Estado de Red", "Desconectado 🔴")

    else:

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Temperatura Actual", "-- °C")
        col2.metric("Temperatura Mínima", "-- °C")
        col3.metric("Temperatura Máxima", "-- °C")
        col4.metric("Temperatura Promedio", "-- °C")

        if st.session_state.mqtt_connected:
            col5.metric("Estado de Red", "Conectado 🟢")
        else:
            col5.metric("Estado de Red", "Desconectado 🔴")


    # ==========================================
    # 10. GRÁFICA INTERACTIVA
    # ==========================================

    st.subheader("📈 Temperatura en tiempo real")

    col_boton, col_estado = st.columns([1, 3])

    with col_boton:

        if st.session_state.grafica_pausada:

            if st.button("▶ Reanudar gráfica", key="reanudar_grafica"):

                st.session_state.grafica_pausada = False
                st.rerun()

        else:

            if st.button("⏸ Pausar gráfica", key="pausar_grafica"):

                st.session_state.grafica_pausada = True
                st.rerun()

    with col_estado:

        if st.session_state.grafica_pausada:
            st.info("Gráfica pausada. Las lecturas siguen almacenándose.")
        else:
            st.success("Gráfica actualizándose.")


    if not df.empty:

        # Actualizar los datos de la gráfica solamente
        # cuando no está pausada
        if not st.session_state.grafica_pausada:

            st.session_state.historial_grafica = (
                df.tail(MAX_MOSTRAR).copy()
            )

        df_grafica = st.session_state.historial_grafica.copy()

        if not df_grafica.empty:

            # Información del periodo mostrado
            fecha_inicio = df_grafica["Fecha"].iloc[0]
            fecha_fin = df_grafica["Fecha"].iloc[-1]

            if fecha_inicio == fecha_fin:

                st.caption(f"Fecha de las lecturas: {fecha_inicio}")

            else:

                st.caption(
                    f"Periodo de las lecturas: "
                    f"{fecha_inicio} a {fecha_fin}"
                )

            # Gráfica basada en el momento real de cada lectura
            # El eje X muestra únicamente la hora
            puntos = alt.Chart(df_grafica).mark_circle(
                size=150,
                opacity=0.9
            ).encode(

                x=alt.X(
                    "Momento:T",
                    title="Hora",
                    axis=alt.Axis(
                        format="%-I:%M:%S%p",
                        labelAngle=0
                    )
                ),

                y=alt.Y(
                    "Temperatura (°C):Q",
                    title="Temperatura (°C)"
                ),

                tooltip=[
                    alt.Tooltip("Fecha:N", title="Fecha"),
                    alt.Tooltip("Hora:N", title="Hora"),
                    alt.Tooltip(
                        "Temperatura (°C):Q",
                        title="Temperatura",
                        format=".2f"
                    )
                ]
            )

            linea = alt.Chart(df_grafica).mark_line(
                strokeWidth=2
            ).encode(

                x=alt.X(
                    "Momento:T",
                    title="Hora",
                    axis=alt.Axis(
                        format="%-I:%M:%S%p",
                        labelAngle=0
                    )
                ),

                y=alt.Y(
                    "Temperatura (°C):Q",
                    title="Temperatura (°C)"
                )
            )

            grafica = (linea + puntos).properties(
                height=350
            ).interactive()

            st.altair_chart(
                grafica,
                use_container_width=True
            )

    else:

        st.info("Esperando datos para generar la gráfica.")


    # ==========================================
    # 11. TABLA DE ÚLTIMAS LECTURAS
    # ==========================================

    st.subheader("📋 Últimas lecturas")

    if not df.empty:

        df_tabla = df_visual[
            ["Fecha", "Hora", "Temperatura (°C)"]
        ].tail(5)

        st.dataframe(
            df_tabla,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            f"Esperando datos del sensor. "
            f"Tópico MQTT: {TOPIC}"
        )


    # ==========================================
    # 12. ERRORES MQTT
    # ==========================================

    if st.session_state.mqtt_error:

        st.error(
            f"Error de conexión MQTT: "
            f"{st.session_state.mqtt_error}"
        )


# ==========================================
# 13. EJECUTAR DASHBOARD
# ==========================================

dashboard()
