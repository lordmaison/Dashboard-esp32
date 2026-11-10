import queue
import time
import pandas as pd
import paho.mqtt.client as mqtt
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

# Conexión al Broker MQTT en la Nube
BROKER_IP = "broker.hivemq.com"
TOPIC = "cybertwin/esp32/temperatura_ds18b20"

st.set_page_config(
    page_title="CyberTwin - Telemetría Wi-Fi Global",
    page_icon="🌡️",
    layout="wide",
)

st.title("🛡️ Dashboard CyberTwin: Monitoreo Remoto Wi-Fi (Cloud)")
st.markdown(
    "Acceso en tiempo real a las lecturas del sensor **DS18B20** transmitidas"
    " por la **ESP32** a través de Internet."
)
st.divider()

if "data_queue" not in st.session_state:
  st.session_state.data_queue = queue.Queue()

if "df_datos" not in st.session_state:
  st.session_state.df_datos = pd.DataFrame(columns=["Tiempo", "Temperatura"])


def on_connect(client, userdata, flags, rc):
  if rc == 0:
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
  try:
    valor_temp = float(msg.payload.decode("utf-8"))
    st.session_state.data_queue.put(valor_temp)
  except Exception:
    pass


if "mqtt_client" not in st.session_state:
  client = mqtt.Client()
  client.on_connect = on_connect
  client.on_message = on_message
  try:
    client.connect(BROKER_IP, 1883, 60)
    client.loop_start()

    if client._thread:
      add_script_run_ctx(client._thread)

    st.session_state.mqtt_client = client
  except Exception as e:
    st.error(f"Error al conectar con el Broker en la Nube: {e}")

col1, col2, col3 = st.columns(3)
metric_temp = col1.empty()
metric_status = col2.empty()
metric_max = col3.empty()

chart_placeholder = st.empty()
table_placeholder = st.empty()

while not st.session_state.data_queue.empty():
  temp_recibida = st.session_state.data_queue.get()
  hora_actual = time.strftime("%H:%M:%S")
  nueva_lectura = pd.DataFrame(
      [{"Tiempo": hora_actual, "Temperatura": temp_recibida}]
  )
  st.session_state.df_datos = pd.concat(
      [st.session_state.df_datos, nueva_lectura], ignore_index=True
  ).tail(30)

df_historial = st.session_state.df_datos

if not df_historial.empty:
  temp_actual = df_historial["Temperatura"].iloc[-1]
  metric_temp.metric(
      label="Temperatura Actual", value=f"{temp_actual:.2f} °C"
  )
  metric_status.metric(
      label="Estado de Red", value="Conectado a Nube (Wi-Fi Global) 🟢"
  )
  metric_max.metric(
      label="Máxima Registrada",
      value=f"{df_historial['Temperatura'].max():.2f} °C",
  )

  chart_placeholder.line_chart(df_historial.set_index("Tiempo")["Temperatura"])

  with table_placeholder.container():
    st.dataframe(df_historial.tail(5), use_container_width=True)
else:
  metric_status.metric(
      label="Estado de Red", value="Esperando datos de la ESP32 en la Nube... ⏳"
  )
  st.info(
      f"Suscripción activa al tópico global: '{TOPIC}'. Ejecuta main.py en la"
      " ESP32 para visualizar las gráficas."
  )

time.sleep(1)
st.rerun()