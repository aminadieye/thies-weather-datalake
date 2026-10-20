import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

# 1. Configuration de la page
st.set_page_config(
    page_title="Thiès Weather Analytics", page_icon="🌍", layout="wide"
)

st.title("📺 Bulletin Météo & Analyse - Région de Thiès")
st.write(
    "Explorez la carte de la région de Thiès, recherchez des localités de la"
    " région et suivez l'évolution de la température."
)

# Initialisation de la session
if "villes_recherchees" not in st.session_state:
  st.session_state["villes_recherchees"] = [
      {"nom": "Thiès", "lat": 14.7979, "lon": -16.9274, "dept": "Thiès"},
      {"nom": "Mbour", "lat": 14.4220, "lon": -16.9638, "dept": "Mbour"},
      {
          "nom": "Tivaouane",
          "lat": 14.9524,
          "lon": -16.8118,
          "dept": "Tivaouane",
      },
      {"nom": "Pout", "lat": 14.7739, "lon": -17.0611, "dept": "Thiès"},
  ]


# 2. Fonction de Géocodage avec validation géographique stricte pour la région de Thiès
def chercher_coordonnees(nom_lieu):
  url = f"https://geocoding-api.open-meteo.com/v1/search?name={nom_lieu}&count=5&language=fr&format=json"
  try:
    res = requests.get(url, timeout=5).json()
    results = res.get("results", [])

    for r in results:
      lat = r.get("latitude")
      lon = r.get("longitude")
      pays = r.get("country_code")

      # Validation : Le point doit être au Sénégal ET dans le périmètre GPS de la région de Thiès
      if pays == "SN" and (14.1 <= lat <= 15.3) and (-17.2 <= lon <= -16.5):
        dept = r.get("admin1", "Région de Thiès")
        if dept in ["Sénégal", None, ""]:
          dept = "Région de Thiès"
        return {
            "nom": r.get("name"),
            "lat": lat,
            "lon": lon,
            "dept": dept,
        }
  except Exception:
    pass

  return None


# 3. Fonction météo actuelle (incluant la température ressentie)
@st.cache_data(ttl=600)
def get_weather(lat, lon):
  url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m"
  try:
    res = requests.get(url, timeout=5).json()
    return res.get("current", {})
  except Exception:
    return {}


# 4. Fonction pour récupérer les prévisions horaires (pour la courbe)
@st.cache_data(ttl=600)
def get_hourly_forecast(lat, lon):
  url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m"
  try:
    res = requests.get(url, timeout=5).json()
    hourly = res.get("hourly", {})
    df_h = pd.DataFrame({
        "timestamp": hourly.get("time", []),
        "temperature": hourly.get("temperature_2m", []),
    })
    df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])
    return df_h
  except Exception:
    return pd.DataFrame()


def get_color(temp):
  if temp >= 32:
    return "red"
  elif temp >= 28:
    return "orange"
  elif temp >= 24:
    return "green"
  else:
    return "blue"


# 5. Barre de recherche latérale
st.sidebar.header("🔍 Rechercher une localité")
nouvelle_recherche = st.sidebar.text_input(
    "Nom de la ville, village ou quartier :", placeholder="ex: Cayar, Saly, Diass..."
)

if st.sidebar.button("Rechercher et Ajouter"):
  if nouvelle_recherche.strip():
    info_geo = chercher_coordonnees(nouvelle_recherche.strip())
    if info_geo:
      noms_existants = [
          v["nom"].lower() for v in st.session_state["villes_recherchees"]
      ]
      if info_geo["nom"].lower() not in noms_existants:
        st.session_state["villes_recherchees"].append(info_geo)
        st.sidebar.success(f"✅ {info_geo['nom']} ajouté à la carte !")
      else:
        st.sidebar.info(f"📍 {info_geo['nom']} est déjà sur la carte.")
    else:
      st.sidebar.error("❌ Localité introuvable dans la région de Thiès.")

# 6. Extraction des données météo actuelles
donnees = []
for item in st.session_state["villes_recherchees"]:
  m = get_weather(item["lat"], item["lon"])
  donnees.append({
      "Ville": item["nom"],
      "Région/Dept": item["dept"],
      "Latitude": item["lat"],
      "Longitude": item["lon"],
      "Température (°C)": m.get("temperature_2m", 0.0),
      "Ressentie (°C)": m.get("apparent_temperature", 0.0),
      "Humidité (%)": m.get("relative_humidity_2m", 0),
      "Vent (km/h)": m.get("wind_speed_10m", 0.0),
  })

df = pd.DataFrame(donnees)

# 7. Sélection de la ville active pour le détail et la courbe
ville_selectionnee = st.selectbox(
    "Sélectionnez une localité pour voir le détail et sa courbe :",
    df["Ville"].unique(),
)
row_sel = df[df["Ville"] == ville_selectionnee].iloc[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("🌡️ Température", f"{row_sel['Température (°C)']} °C")
c2.metric("🔥 Temp. Ressentie", f"{row_sel['Ressentie (°C)']} °C")
c3.metric("💧 Humidité", f"{row_sel['Humidité (%)']} %")
c4.metric("💨 Vent", f"{row_sel['Vent (km/h)']} km/h")

st.markdown("---")

# 8. Courbe d'évolution temporelle
st.subheader(f"📈 Évolution de la température à {ville_selectionnee}")
info_ville_coords = next(
    item
    for item in st.session_state["villes_recherchees"]
    if item["nom"] == ville_selectionnee
)
df_hourly = get_hourly_forecast(
    info_ville_coords["lat"], info_ville_coords["lon"]
)

if not df_hourly.empty:
  st.line_chart(
      df_hourly.set_index("timestamp")["temperature"],
      color="#FF4B4B",
      height=300,
  )
else:
  st.info("Chargement de la courbe d'évolution...")

st.markdown("---")

# 9. Carte interactive régionale
st.subheader("🗺️ Carte Interactive Régionale")

carte = folium.Map(
    location=[14.7979, -16.9274], zoom_start=9, tiles="OpenStreetMap"
)

for _, r in df.iterrows():
  couleur = get_color(r["Température (°C)"])
  folium.Marker(
      location=[r["Latitude"], r["Longitude"]],
      popup=(
          f"<b>{r['Ville']}</b><br>Temp : {r['Température (°C)']} °C<br>Ressenti"
          f" : {r['Ressentie (°C)']} °C"
      ),
      tooltip=f"{r['Ville']} : {r['Température (°C)']} °C",
      icon=folium.Icon(color=couleur, icon="info-sign"),
  ).add_to(carte)

st_folium(carte, width="100%", height=450)

# 10. Tableau récapitulatif
st.subheader("📋 Liste des points observés")
st.dataframe(
    df[[
        "Ville",
        "Région/Dept",
        "Température (°C)",
        "Ressentie (°C)",
        "Humidité (%)",
        "Vent (km/h)",
    ]],
    use_container_width=True,
)