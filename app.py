import sqlite3
import streamlit as st
import streamlit.components.v1 as components
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

init_db()

if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    st.error("⚠️ No se encontró la API Key. Añade 'GEMINI_API_KEY' en los Secrets de tu app en Streamlit Cloud.")
    st.stop()

MODEL_ID = "gemini-3.8-flash"
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

def speak_in_browser(text: str):
    """Ejecuta Web Speech API directamente en el navegador para latencia 0."""
    safe_text = text.replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ')
    js_code = f"""
    <script>
        if ('speechSynthesis' in window) {{
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance('{safe_text}');
            utterance.lang = 'en-US';
            utterance.rate = 1.0;
            window.speechSynthesis.speak(utterance);
        }}
    </script>
    """
    components.html(js_code, height=0, width=0)

# -----------------------------------------------------------------------------
# 3. INTERFAZ Y LÓGICA DE USUARIO EN STREAMLIT
# -----------------------------------------------------------------------------
st.title("🎓 RoboTutor AI - Método Científico de Adquisición de Lenguaje")
st.caption("Basado en Input Comprensible (i+1), Recasting Conversacional, Enfoque Léxico (Tatoeba) y SRS")

with st.sidebar:
    st.header("⚙️ Configuración del Alumno")
    cefr_level = st.selectbox(
        "Selecciona tu Nivel CEFR:",
        ["A1-A2 (Principiante)", "B1-B2 (Intermedio)", "C1-C2 (Avanzado)"],
        index=1
    )
    
    enable_audio_reply = st.toggle("🔊 Respuesta por Voz Novedosa (Web Speech API)", value=True)

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

# Renderizar el historial existente
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Captura de entrada (Texto o Voz)
user_input = st.chat_input("Escribe tu mensaje en inglés...")
audio_val = st.audio_input("O presiona para grabar tu respuesta hablada")

if user_input or audio_val is not None:
    # 1. Pasar unicamente historial en texto para optimizar la velocidad
    formatted_contents = []
    for m in st.session_state.messages:
        role = "user" if m["role"] == "user" else "model"
        formatted_contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=m["content"])])
        )

    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        formatted_contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_input)])
        )

    elif audio_val is not None:
        audio_bytes = audio_val.getvalue()
        mime_type = audio_val.type or "audio/wav"

        with st.chat_message("user"):
            st.audio(audio_bytes, format=mime_type)
            st.caption("🎙️ Mensaje de voz enviado")

        st.session_state.messages.append({"role": "user", "content": "🎙️ [Audio grabado por el estudiante]"})

        prompt_instruction = "Listen to my voice audio response carefully. Answer my points naturally using Recasting for any errors, and ask a relevant question."
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        text_part = types.Part.from_text(text=prompt_instruction)

        formatted_contents.append(
            types.Content(role="user", parts=[audio_part, text_part])
        )

    # Generación progresiva de texto en tiempo real
    with st.chat_message("assistant"):
        try:
            response_stream = client.models.generate_content_stream(
                model=MODEL_ID,
                contents=formatted_contents,
                config=types.GenerateContentConfig(
                    system_instruction=full_system_instruction,
                    temperature=0.7,
                )
            )

            def generate_chunks():
                for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text

            bot_reply = st.write_stream(generate_chunks())
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})

            # Reproducción de voz nativa inmediata sin demoras de red
            if enable_audio_reply and bot_reply:
                speak_in_browser(bot_reply)

        except Exception as e:
            st.error(f"Error al comunicar con RoboTutor API: {e}")
