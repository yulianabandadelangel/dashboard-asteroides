# Dashboard de Asteroides (NASA NeoWs) con Streamlit
# Basado en mi Práctica 12 - Herramientas de Visualización
# Yuliana Elizabeth Banda Del Angel

import os
import json
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import streamlit as st

st.set_page_config(page_title="Asteroides cerca de la Tierra", page_icon="☄️", layout="wide")

CARPETA = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_JSON = os.path.join(CARPETA, "respuesta.json")
URL = "https://api.nasa.gov/neo/rest/v1/feed"

# Paleta del curso
GRIS = "#B9C3D1"   # contexto
AZUL = "#1C4C9A"   # lo que destaco

# 6 semanas de 7 días (la API no deja pedir más de 7 días a la vez)
SEMANAS = [
    ("2026-09-27", "2026-10-03"),
    ("2026-10-04", "2026-10-10"),
    ("2026-10-11", "2026-10-17"),
    ("2026-10-18", "2026-10-24"),
    ("2026-10-25", "2026-10-31"),
    ("2026-11-01", "2026-11-07"),
]


# ---------- 1. Leer el token (solo se usa si no existe respuesta.json) ----------
def leer_token():
    ruta = os.path.join(CARPETA, "token.txt")
    if not os.path.exists(ruta):
        st.error("No encontré token.txt ni respuesta.json en la carpeta.")
        st.stop()
    with open(ruta, encoding="utf-8-sig") as f:
        token = f.read().strip()
    if token == "" or len(token) < 30 or " " in token:
        st.error("El token de token.txt está vacío, incompleto o tiene espacios.")
        st.stop()
    return token


# ---------- 2. Pedir una semana a la API ----------
def pedir_semana(token, inicio, fin):
    parametros = {"start_date": inicio, "end_date": fin, "api_key": token}
    try:
        respuesta = requests.get(URL, params=parametros, timeout=30)
    except requests.exceptions.RequestException:
        st.error("No se pudo conectar con la API. Revisa tu internet.")
        st.stop()

    # La NASA escribe el token dentro de la respuesta: lo tapamos
    texto = respuesta.text.replace(token, "TOKEN_OCULTO")

    codigo = respuesta.status_code
    if codigo in (401, 403):
        st.error(f"Error {codigo}: el token no sirve.")
        st.stop()
    if codigo == 429:
        st.error("Error 429: te pasaste del límite de peticiones. Espera una hora.")
        st.stop()
    if codigo != 200:
        st.error(f"Error {codigo}: la API respondió algo inesperado.")
        st.stop()
    return json.loads(texto)


# ---------- 3. Obtener los datos (de respuesta.json o de la API) ----------
@st.cache_data
def obtener_datos():
    if os.path.exists(ARCHIVO_JSON):
        with open(ARCHIVO_JSON, encoding="utf-8") as f:
            return json.load(f)

    token = leer_token()
    juntos = {"element_count": 0, "near_earth_objects": {}}
    for inicio, fin in SEMANAS:
        datos = pedir_semana(token, inicio, fin)
        juntos["element_count"] += datos["element_count"]
        juntos["near_earth_objects"].update(datos["near_earth_objects"])
    with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(juntos, f, ensure_ascii=False, indent=2)
    return juntos


# ---------- 4. Pasar el JSON a una tabla y limpiar ----------
@st.cache_data
def armar_tabla(datos):
    filas = []
    for fecha, asteroides in datos["near_earth_objects"].items():
        for a in asteroides:
            acercamiento = a["close_approach_data"][0]
            filas.append({
                "nombre": a["name"],
                "fecha": acercamiento["close_approach_date"],
                "diametro_m": a["estimated_diameter"]["meters"]["estimated_diameter_max"],
                "velocidad_kms": acercamiento["relative_velocity"]["kilometers_per_second"],
                "distancia_lunar": acercamiento["miss_distance"]["lunar"],
                "peligroso": a["is_potentially_hazardous_asteroid"],
            })
    df = pd.DataFrame(filas)

    # Limpieza (igual que en la práctica 12)
    df["velocidad_kms"] = pd.to_numeric(df["velocidad_kms"], errors="coerce")
    df["distancia_lunar"] = pd.to_numeric(df["distancia_lunar"], errors="coerce")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["peligroso"] = df["peligroso"].map({True: "Sí", False: "No"})
    df = df.dropna().drop_duplicates(subset=["nombre", "fecha"])
    return df


datos = obtener_datos()
df_completo = armar_tabla(datos)


# ---------- 5. Filtros (barra lateral) ----------
st.sidebar.header("Filtros")

fecha_min = df_completo["fecha"].min().date()
fecha_max = df_completo["fecha"].max().date()
rango = st.sidebar.date_input("Rango de fechas", (fecha_min, fecha_max),
                              min_value=fecha_min, max_value=fecha_max)

tipo = st.sidebar.radio("Tipo de asteroide", ["Todos", "Solo peligrosos", "Solo no peligrosos"])

tam_max = int(df_completo["diametro_m"].max()) + 1
tamanos = st.sidebar.slider("Diámetro (m)", 0, tam_max, (0, tam_max))

# Aplicar filtros
df = df_completo.copy()
if isinstance(rango, (list, tuple)) and len(rango) == 2:
    df = df[(df["fecha"].dt.date >= rango[0]) & (df["fecha"].dt.date <= rango[1])]
if tipo == "Solo peligrosos":
    df = df[df["peligroso"] == "Sí"]
elif tipo == "Solo no peligrosos":
    df = df[df["peligroso"] == "No"]
df = df[(df["diametro_m"] >= tamanos[0]) & (df["diametro_m"] <= tamanos[1])]

st.sidebar.caption("Fuente: NASA NeoWs (api.nasa.gov)")


# ---------- 6. Encabezado y números clave ----------
st.title("☄️ Asteroides que pasan cerca de la Tierra")
st.write("Datos de la API **NASA NeoWs** · 27 sep – 7 nov 2026 · "
         "Alumna: Yuliana Elizabeth Banda Del Angel")

if len(df) < 2:
    st.warning("Con estos filtros no quedan suficientes asteroides. Cambia los filtros.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Asteroides", len(df))
c2.metric("Potencialmente peligrosos", (df["peligroso"] == "Sí").sum())
c3.metric("Diámetro mediano", f"{df['diametro_m'].median():.0f} m")
c4.metric("Paso más cercano", f"{df['distancia_lunar'].min():.1f} dist. lunares")

st.divider()


# ---------- 7. Gráficas (las mismas 4 de la práctica) ----------
def limpiar_ejes(ax):
    ax.spines[["top", "right"]].set_visible(False)


# Gráfica 1 - DISTRIBUCIÓN
def grafica_1(df):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bordes = np.arange(0, df["diametro_m"].max() + 50, 50)
    n, bins, barras = ax.hist(df["diametro_m"], bins=bordes, color=GRIS, edgecolor="white")
    for barra, izq in zip(barras, bins[:-1]):
        if izq < 300:
            barra.set_facecolor(AZUL)
    ax.set_xlabel("Diámetro máximo estimado (m)")
    ax.set_ylabel("Número de asteroides")
    limpiar_ejes(ax)
    plt.tight_layout()
    return fig


# Gráfica 2 - COMPARACIÓN
def grafica_2(df):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    no = df[df["peligroso"] == "No"]["diametro_m"]
    si = df[df["peligroso"] == "Sí"]["diametro_m"]
    grupos, nombres, colores = [], [], []
    if len(no) > 0:
        grupos.append(no); nombres.append(f"No peligrosos\n({len(no)})"); colores.append(GRIS)
    if len(si) > 0:
        grupos.append(si); nombres.append(f"Potencialmente peligrosos\n({len(si)})"); colores.append(AZUL)
    cajas = ax.boxplot(grupos, patch_artist=True, widths=0.5, medianprops={"color": "black"})
    ax.set_xticks(range(1, len(grupos) + 1), nombres)
    for caja, color in zip(cajas["boxes"], colores):
        caja.set_facecolor(color)
    ax.set_ylabel("Diámetro máximo estimado (m)")
    limpiar_ejes(ax)
    plt.tight_layout()
    return fig


# Gráfica 3 - RELACIÓN
def grafica_3(df):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x, y = df["velocidad_kms"], df["distancia_lunar"]
    ax.scatter(x, y, color=GRIS, edgecolor="#8A96A8", s=30)
    m, b = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, m * xs + b, color=AZUL, linewidth=2.5)
    ax.set_xlabel("Velocidad relativa a la Tierra (km/s)")
    ax.set_ylabel("Distancia de paso (distancias lunares)")
    limpiar_ejes(ax)
    plt.tight_layout()
    return fig


# Gráfica 4 - EVOLUCIÓN
def grafica_4(df):
    por_dia = df.groupby("fecha").size()
    promedio = por_dia.mean()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(por_dia.index, por_dia.values, color=AZUL, linewidth=2, marker="o", markersize=4)
    ax.axhline(promedio, color=GRIS, linestyle="--", linewidth=2)
    ax.set_xlabel("Fecha de máximo acercamiento (día/mes)")
    ax.set_ylabel("Asteroides por día")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.set_ylim(0, por_dia.max() + 2)
    limpiar_ejes(ax)
    plt.tight_layout()
    return fig


# Acomodo en 2 filas de 2 gráficas
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. ¿De qué tamaño son la mayoría?")
    pct = (df["diametro_m"] < 300).mean() * 100
    st.caption(f"El {pct:.0f}% mide menos de 300 m (barras azules).")
    st.pyplot(grafica_1(df))

with col2:
    st.subheader("2. ¿Los peligrosos son más grandes?")
    no = df[df["peligroso"] == "No"]["diametro_m"]
    si = df[df["peligroso"] == "Sí"]["diametro_m"]
    if len(no) > 0 and len(si) > 0:
        st.caption(f"Mediana: {si.median():.0f} m (peligrosos) contra {no.median():.0f} m (no peligrosos).")
    else:
        st.caption("Con el filtro actual solo hay un grupo.")
    st.pyplot(grafica_2(df))

col3, col4 = st.columns(2)

with col3:
    st.subheader("3. ¿Los más rápidos pasan más cerca?")
    r = df["velocidad_kms"].corr(df["distancia_lunar"])
    st.caption(f"Correlación r = {r:.2f} (cerca de 0 = casi no se relacionan).")
    st.pyplot(grafica_3(df))

with col4:
    st.subheader("4. ¿Cuántos pasan cada día?")
    por_dia = df.groupby("fecha").size()
    st.caption(f"Promedio: {por_dia.mean():.1f} por día · Pico: {por_dia.idxmax():%d/%m} con {por_dia.max()}.")
    st.pyplot(grafica_4(df))

st.divider()


# ---------- 8. Tabla de datos ----------
with st.expander("Ver tabla de datos"):
    tabla = df.sort_values("fecha").copy()
    tabla["fecha"] = tabla["fecha"].dt.strftime("%Y-%m-%d")
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.download_button("Descargar CSV", tabla.to_csv(index=False).encode("utf-8"),
                       "asteroides.csv", "text/csv")
