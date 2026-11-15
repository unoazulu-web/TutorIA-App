import sqlite3
import streamlit as st
from google import genai
from google.genai import types

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN INICIAL DE PÁGINA DE STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(page_title="RoboTutor AI", page_icon="🎓", layout="wide")

# -----------------------------------------------------------------------------
# 2. AUTO-INICIALIZACIÓN DE BASE DE DATOS Y LECTURA SEGURA DE API KEY
# -----------------------------------------------------------------------------
def init_db():
    """Crea la base de datos FTS5 y la tabla SRS si no existen en el servidor."""
    conn = sqlite3.connect("tatoeba_pairs.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS tatoeba_fts USING fts5(
            english_sentence,
            spanish_translation
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS srs_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_error TEXT NOT NULL,
            recast_correction TEXT NOT NULL,
            cefr_level TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("SELECT COUNT(*) FROM tatoeba_fts;")
    if cursor.fetchone()[0] == 0:
        sample_data = [
            ("I went to the market yesterday.", "Fui al mercado ayer."),
            ("Could you tell me how to get to the station?", "¿Podría decirme cómo llegar a la estación?"),
            ("I'm looking forward to working with you.", "Tengo muchas ganas de trabajar contigo."),
            ("She has been studying English for three years.", "Ella ha estado estudiando inglés durante tres años."),
            ("If I had known, I would have called you.", "Si lo hubiera sabido, te habría llamado.")
        ]
        cursor.executemany("""
            INSERT INTO tatoeba_fts (english_sentence, spanish_translation) 
            VALUES (?, ?);
        """, sample_data)
        conn.commit()

    conn.close()

# Ejecutar inicialización de tablas SQLite
init_db()

# Carga segura de la API Key desde los Secrets encriptados de Streamlit
if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    st.error("⚠️ No se encontró la API Key. Añade 'GEMINI_API_KEY' en los Secrets de tu app en Streamlit Cloud.")
    st.stop()

# Usar el modelo activo gemini-2.0-flash
MODEL_ID = "gemini-2.0-flash"
client = genai.Client(api_key=API_KEY)

def query_tatoeba(keyword: str, limit: int = 5):
    """Consulta rápida en SQLite FTS5 (<10 ms) para Sentence Mining."""
    try:
        conn = sqlite3.connect("tatoeba_pairs.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT english_sentence, spanish_translation 
            FROM tatoeba_fts 
            WHERE tatoeba_fts MATCH ? 
            LIMIT ?;
        """, (keyword, limit))
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception:
        return []

def get_cefr_instructions(level: str) -> str:
    """Matriz de Adaptación Dinámica según el Nivel CEFR."""
    if level == "A1-A2 (Principiante)":
        return """
        CEFR LEVEL: A1-A2 (Beginner)
        - Conduct: Use short sentences, speak slowly and clearly. Provide brief, punctual bilingual support in Spanish when addressing complex grammar doubts.
        - Correction Rate: Direct and guided (Recasting + brief natural explanation).
        - Fluency Goal: Automate 500 basic structures and everyday vocabulary.
        """
    elif level == "B1-B2 (Intermedio)":
        return """
        CEFR LEVEL: B1-B2 (Intermediate)
        - Conduct: 100% English conversation. Debate real-world topics, introduce phrasal verbs and idioms from natural sentences.
        - Correction Rate: Pure implicit recasting in real-time.
        - Fluency Goal: Eliminate mental translation and gain natural conversational fluency.
        """
    else: # C1-C2
        return """
        CEFR LEVEL: C1-C2 (Advanced)
        - Conduct: Native-speed discourse, analyze cultural nuances, formal vs. informal registers, and fine pronunciation.
        - Correction Rate: Focused on subtle stylistic correction and advanced vocabulary.
        - Fluency Goal: Professional mastery and complex technical argumentation.
        """

# -----------------------------------------------------------------------------
# 3. INTERFAZ Y LÓGICA DE USUARIO EN STREAMLIT
# -----------------------------------------------------------------------------
st.title("🎓 RoboTutor AI - Método Científico de Adquisición de Lenguaje")
st.caption("Basado en Input Comprensible (i+1), Recasting Conversacional, Enfoque Léxico (Tatoeba) y SRS")

# Barra lateral de configuración CEFR y utilidades
with st.sidebar:
    st.header("⚙️ Configuración del Alumno")
    cefr_level = st.selectbox(
        "Selecciona tu Nivel CEFR:",
        ["A1-A2 (Principiante)", "B1-B2 (Intermedio)", "C1-C2 (Avanzado)"],
        index=1
    )
    
    st.divider()
    st.subheader("🔍 Buscador de Frases (Tatoeba FTS5)")
    search_term = st.text_input("Buscar expresión o palabra clave:")
    if search_term:
        matches = query_tatoeba(search_term)
        if matches:
            for en, es in matches:
                st.markdown(f"**EN:** {en}\n\n**ES:** {es}")
                st.divider()
        else:
            st.info("No se encontraron coincidencias exactas.")

    st.divider()
    if st.session_state.get("messages"):
        transcript = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
        st.download_button(
            label="📥 Descargar Reporte de la Clase (TXT)",
            data=transcript,
            file_name="RoboTutor_Session_Report.txt",
            mime="text/plain"
        )

BASE_SYSTEM_PROMPT = """You are RoboTutor, the world's most advanced AI English teacher built on the Natural Approach and Task-Based Language Teaching (TBLT).

CORE PEDAGOGICAL PROTOCOL:
1. COMPREHENSIBLE INPUT (i+1): Keep 85% of your language easy for the student's level, and 15% slightly challenging.
2. RECASTING TECHNIQUE: Never interrupt or penalize the user aggressively. If they make a grammar or pronunciation mistake, rephrase their sentence correctly inside your natural response (e.g., User: "Yesterday I go to market" -> RoboTutor: "Oh, you went to the market yesterday! What did you buy?").
3. LEXICAL CHUNKS: Incorporate natural sentence patterns and collocations instead of listing isolated rules.
4. ACTIVE ENGAGEMENT: Always close your response with an open-ended question to encourage continuous speaking.
"""

full_system_instruction = BASE_SYSTEM_PROMPT + "\n" + get_cefr_instructions(cefr_level)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": f"Hello! I am RoboTutor, your AI English coach. I see you are practicing at the **{cefr_level}** level. What did you do today?"}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Escribe tu mensaje en inglés...")
audio_val = st.audio_input("O presiona para grabar tu respuesta hablada")

active_prompt = None
if user_input:
    active_prompt = user_input
elif audio_val is not None:
    active_prompt = "Audio message received. Please respond to the user based on pedagogical recasting."

if active_prompt:
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    with st.chat_message("user"):
        st.markdown(active_prompt)

    formatted_contents = []
    for m in st.session_state.messages:
        role = "user" if m["role"] == "user" else "model"
        formatted_contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=m["content"])])
        )

    with st.chat_message("assistant"):
        with st.spinner("RoboTutor está analizando tu respuesta..."):
            try:
                response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=formatted_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=full_system_instruction,
                        temperature=0.7,
                    )
                )
                bot_reply = response.text
                st.markdown(bot_reply)
                st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            except Exception as e:
                st.error(f"Error al comunicar con RoboTutor API: {e}")
