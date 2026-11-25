# Práctica 12 - Tu API (NASA Asteroides NeoWs)
# Yuliana Elizabeth Banda Del Angel

import os
import json
import requests
import pandas as pd
import matplotlib.pyplot as plt

# Carpeta donde está este archivo (para encontrar token.txt)
CARPETA = os.path.dirname(os.path.abspath(__file__))


# ---------- 1. Leer y validar el token ----------
def leer_token():
    ruta = os.path.join(CARPETA, "token.txt")

    # ¿Existe el archivo?
    if not os.path.exists(ruta):
        print("ERROR: no encontré token.txt en la carpeta de la práctica.")
        raise SystemExit(1)

    # Leerlo y quitar espacios o saltos de línea
    with open(ruta, encoding="utf-8-sig") as f:
        token = f.read().strip()

    # ¿Está vacío?
    if token == "":
        print("ERROR: token.txt está vacío.")
        raise SystemExit(1)

    # ¿Está incompleto? (las llaves de la NASA son largas)
    if len(token) < 30:
        print(f"ERROR: el token solo tiene {len(token)} caracteres. Parece incompleto.")
        raise SystemExit(1)

    # ¿Tiene espacios en medio? (se copió mal)
    if " " in token:
        print("ERROR: el token tiene espacios. Revisa que lo copiaste bien.")
        raise SystemExit(1)

    print(f"Token leído correctamente ({len(token)} caracteres).")
    return token

token = leer_token()

# ---------- 2. Pedir una semana a la API ----------
URL = "https://api.nasa.gov/neo/rest/v1/feed"

def pedir_semana(token, inicio, fin):
    parametros = {"start_date": inicio, "end_date": fin, "api_key": token}
    print(f"Consultando la API: {inicio} a {fin} ...")

    try:
        respuesta = requests.get(URL, params=parametros, timeout=30)
    except requests.exceptions.RequestException:
        print("ERROR: no se pudo conectar con la API. Revisa tu internet.")
        raise SystemExit(1)

    # La NASA escribe el token dentro de la respuesta: lo tapamos
    texto = respuesta.text.replace(token, "TOKEN_OCULTO")

    # Regla 2: revisar el código de estado
    codigo = respuesta.status_code
    if codigo in (401, 403):
        print(f"ERROR {codigo}: el token no sirve. Revisa que esté bien copiado en token.txt.")
        raise SystemExit(1)
    if codigo == 400:
        print("ERROR 400: la petición está mal hecha (revisa las fechas: máximo 7 días).")
        print(texto[:300])
        raise SystemExit(1)
    if codigo == 429:
        print("ERROR 429: te pasaste del límite de peticiones (1,000 por hora). Espera una hora.")
        raise SystemExit(1)
    if codigo != 200:
        print(f"ERROR {codigo}: la API respondió algo inesperado.")
        print(texto[:300])
        raise SystemExit(1)

    # Regla 3: revisar que de verdad llegó JSON
    if "json" not in (respuesta.headers.get("Content-Type") or ""):
        print(texto[:300])
        raise SystemExit(1)

    return json.loads(texto)

# ---------- 3. Guardar la respuesta y reutilizarla ----------
ARCHIVO_JSON = os.path.join(CARPETA, "respuesta.json")

# 6 semanas de 7 días (la API no deja pedir más de 7 días a la vez)
SEMANAS = [
    ("2026-09-27", "2026-10-03"),
    ("2026-10-04", "2026-10-10"),
    ("2026-10-11", "2026-10-17"),
    ("2026-10-18", "2026-10-24"),
    ("2026-10-25", "2026-10-31"),
    ("2026-11-01", "2026-11-07"),
]

def obtener_datos(token):
    # Si ya existe el archivo, lo leemos y NO consultamos la API
    if os.path.exists(ARCHIVO_JSON):
        print("Leyendo respuesta.json (no se gastan peticiones).")
        with open(ARCHIVO_JSON, encoding="utf-8") as f:
            return json.load(f)

    # Si no existe, consultamos semana por semana y juntamos todo
    print("No existe respuesta.json: consultando la API...")
    juntos = {"element_count": 0, "near_earth_objects": {}}
    for inicio, fin in SEMANAS:
        datos = pedir_semana(token, inicio, fin)
        juntos["element_count"] += datos["element_count"]
        juntos["near_earth_objects"].update(datos["near_earth_objects"])

    with open(ARCHIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(juntos, f, ensure_ascii=False, indent=2)
    print(f"Guardé {juntos['element_count']} asteroides en respuesta.json")
    return juntos


datos = obtener_datos(token)

# ---------- 4. Pasar el JSON a una tabla y limpiar ----------
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
    return pd.DataFrame(filas)


def limpiar(df):
    print("\n========== LIMPIEZA DE DATOS ==========")
    print(f"Registros al cargar: {len(df)}")

    print("\nTipos de dato al cargar:")
    print(df.dtypes)

    print("\nFaltantes por columna (al cargar):")
    print(df.isna().sum())

    # Velocidad y distancia llegan como TEXTO: convertirlas a número
    for col in ["velocidad_kms", "distancia_lunar"]:
        antes = df[col].notna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        despues = df[col].notna().sum()
        print(f"\n'{col}' convertida de texto a número: se perdieron {antes - despues} valores.")

    # La fecha llega como texto: convertirla a fecha
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    # Peligroso: pasarlo a "Sí" / "No" para que se lea bien en las gráficas
    df["peligroso"] = df["peligroso"].map({True: "Sí", False: "No"})

    # Quitar renglones con faltantes y repetidos
    total = len(df)
    df = df.dropna()
    sin_faltantes = len(df)
    df = df.drop_duplicates(subset=["nombre", "fecha"])
    print(f"\nRenglones quitados por faltantes: {total - sin_faltantes}")
    print(f"Renglones quitados por repetidos: {sin_faltantes - len(df)}")

    print("\nTipos de dato después de limpiar:")
    print(df.dtypes)

    print(f"\nRegistros utilizables: {len(df)}")
    print("=======================================\n")
    return df


df = armar_tabla(datos)
df = limpiar(df)

# ---------- 5. Gráficas ----------
import numpy as np
import matplotlib.dates as mdates

# Paleta del curso
GRIS = "#B9C3D1"   # contexto
AZUL = "#1C4C9A"   # lo que destaco


# Gráfica 1 - DISTRIBUCIÓN: tamaño de los asteroides
def grafica_1(df):
    fig, ax = plt.subplots(figsize=(9, 5))
    bordes = np.arange(0, 1550, 50)   # barras de 50 en 50 metros
    n, bins, barras = ax.hist(df["diametro_m"], bins=bordes, color=GRIS, edgecolor="white")

    # Pinto de azul las barras de menos de 300 m (donde se concentran)
    for barra, izq in zip(barras, bins[:-1]):
        if izq < 300:
            barra.set_facecolor(AZUL)

    pct = (df["diametro_m"] < 300).mean() * 100
    grandes = (df["diametro_m"] > 1000).sum()
    ax.set_title(f"El {pct:.0f}% de los asteroides mide menos de 300 m; solo {grandes} superan 1 km",
                 fontsize=12, loc="left")
    ax.set_xlabel("Diámetro máximo estimado (m)")
    ax.set_ylabel("Número de asteroides")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(CARPETA, "grafica1_distribucion.png"), dpi=150)  # primero guardar
    plt.show()                                                                  # luego mostrar


# Gráfica 2 - COMPARACIÓN: peligrosos vs no peligrosos
def grafica_2(df):
    fig, ax = plt.subplots(figsize=(7, 5))
    no = df[df["peligroso"] == "No"]["diametro_m"]
    si = df[df["peligroso"] == "Sí"]["diametro_m"]

    cajas = ax.boxplot([no, si], patch_artist=True, widths=0.5,
                       medianprops={"color": "black"})
    ax.set_xticks([1, 2], [f"No peligrosos\n({len(no)})",
                           f"Potencialmente peligrosos\n({len(si)})"])
    cajas["boxes"][0].set_facecolor(GRIS)   # contexto
    cajas["boxes"][1].set_facecolor(AZUL)   # lo que destaco

    ax.set_title(f"Los peligrosos son unas {si.median()/no.median():.1f} veces más grandes "
                 f"(mediana {si.median():.0f} m vs {no.median():.0f} m)", fontsize=12, loc="left")
    ax.set_xlabel("Clasificación de la NASA (número de asteroides)")
    ax.set_ylabel("Diámetro máximo estimado (m)")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(CARPETA, "grafica2_comparacion.png"), dpi=150)
    plt.show()


# Gráfica 3 - RELACIÓN: velocidad vs distancia
def grafica_3(df):
    fig, ax = plt.subplots(figsize=(9, 5))
    x = df["velocidad_kms"]
    y = df["distancia_lunar"]
    ax.scatter(x, y, color=GRIS, edgecolor="#8A96A8", s=30)

    # Línea de tendencia
    m, b = np.polyfit(x, y, 1)
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, m * xs + b, color=AZUL, linewidth=2.5)

    r = x.corr(y)   # correlación: qué tanto se mueven juntas
    ax.set_title(f"Velocidad y distancia casi no se relacionan (r = {r:.2f}): "
                 "los rápidos pasan apenas un poco más lejos", fontsize=12, loc="left")
    ax.set_xlabel("Velocidad relativa a la Tierra (km/s)")
    ax.set_ylabel("Distancia de paso (distancias lunares)")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(CARPETA, "grafica3_relacion.png"), dpi=150)
    plt.show()


# Gráfica 4 - EVOLUCIÓN: asteroides por día
def grafica_4(df):
    por_dia = df.groupby("fecha").size()
    promedio = por_dia.mean()
    dia_max = por_dia.idxmax()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(por_dia.index, por_dia.values, color=AZUL, linewidth=2, marker="o", markersize=4)
    ax.axhline(promedio, color=GRIS, linestyle="--", linewidth=2)
    ax.text(por_dia.index[0], promedio + 0.3, f"Promedio: {promedio:.1f} por día", color="#5A6578")
    ax.annotate(f"{por_dia.max()} asteroides\n({dia_max:%d/%m})", xy=(dia_max, por_dia.max()),
                xytext=(15, -5), textcoords="offset points", color=AZUL)

    ax.set_title(f"Pasan unos {promedio:.0f} asteroides por día; el pico fue el "
                 f"{dia_max:%d/%m} con {por_dia.max()}", fontsize=12, loc="left")
    ax.set_xlabel("Fecha de máximo acercamiento (día/mes, 2026)")
    ax.set_ylabel("Asteroides por día")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.set_ylim(0, por_dia.max() + 2)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(os.path.join(CARPETA, "grafica4_evolucion.png"), dpi=150)
    plt.show()


# ---------- Hacer las 4 gráficas ----------
grafica_1(df)
grafica_2(df)
grafica_3(df)
grafica_4(df)