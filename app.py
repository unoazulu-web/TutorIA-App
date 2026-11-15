import sqlite3
import hashlib
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA DE STREAMLIT
# -----------------------------------------------------------------------------
st.set_page_config(page_title="RoboTutor AI", page_icon="🎓", layout="wide")

# -----------------------------------------------------------------------------
# 2. AUTO-INICIALIZACIÓN DE BASE DE DATOS Y CLIENTE CON FALLBACK
# -----------------------------------------------------------------------------
def init_db():
    """Crea la base de datos FTS5 (<10 ms) y la tabla SRS si no existen."""
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
        cursor.executemany("INSERT INTO tatoeba_fts (english_sentence, spanish_translation) VALUES (?, ?);", sample_data)
        conn.commit()
    conn.close()

init_db()

if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"].strip()
else:
    st.error("⚠️ No se encontró la API Key en st.secrets['GEMINI_API_KEY']. Agrégala en Secrets de Streamlit Cloud.")
    st.stop()

client = genai.Client(api_key=API_KEY)

def query_tatoeba(keyword: str, limit: int = 5):
    """Búsqueda ultra-rápida FTS5 en corpus bilingüe de Tatoeba (<10 ms)."""
    try:
        conn = sqlite3.connect("tatoeba_pairs.db")
        cursor = conn.cursor()
        cursor.execute("SELECT english_sentence, spanish_translation FROM tatoeba_fts WHERE tatoeba_fts MATCH ? LIMIT ?;", (keyword, limit))
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception:
        return []

def get_cefr_instructions(level: str) -> str:
    """Matriz pedagógica dinámica según nivel CEFR."""
    if level == "A1-A2 (Principiante)":
        return """
        CEFR LEVEL: A1-A2 (Beginner)
        - Conduct: Short, simple sentences, clear vocabulary. Brief bilingual support in Spanish if needed.
        - Correction Rate: Direct and guided (Recasting + brief natural explanation).
        - Fluency Goal: Automate 500 basic structures and everyday vocabulary.
        """
    elif level == "B1-B2 (Intermedio)":
        return """
        CEFR LEVEL: B1-B2 (Intermediate)
        - Conduct: 100% English conversation. Debate real-world topics, introduce phrasal verbs and idioms.
        - Correction Rate: Pure implicit recasting in real-time.
        - Fluency Goal: Eliminate mental translation and gain natural conversational fluency.
        """
    else:
        return """
        CEFR LEVEL: C1-C2 (Advanced)
        - Conduct: Native-speed discourse, analyze cultural nuances, formal vs. informal registers.
        - Correction Rate: Focused on subtle stylistic correction and advanced vocabulary.
        - Fluency Goal: Professional mastery and complex technical argumentation.
        """

def speak_in_browser(text: str):
    """Sintetiza la respuesta por voz en el navegador con Web Speech API (Latencia 0 ms)."""
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

def generate_response_with_fallback(contents, system_instruction):
    """Intenta conectarse a los modelos activos y realiza fallback automático si no responde alguno."""
    candidate_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.7,
        max_output_tokens=500,
    )
    
    last_exception = None
    for model_name in candidate_models:
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
            if res and res.text:
                return res.text
        except Exception as e:
            last_exception = e
            continue
            
    raise last_exception if last_exception else RuntimeError("No se pudo conectar a ningún modelo de Gemini.")

# -----------------------------------------------------------------------------
# 3. INTERFAZ Y LÓGICA DE USUARIO
# -----------------------------------------------------------------------------
st.title("🎓 RoboTutor AI - Adquisición Acelerada de Inglés")
st.caption("Input Comprensible (i+1) | Recasting Conversacional | Limpieza Multimodal Nativa")

with st.sidebar:
    st.header("⚙️ Configuración")
    cefr_level = st.selectbox(
        "Nivel CEFR:",
        ["A1-A2 (Principiante)", "B1-B2 (Intermedio)", "C1-C2 (Avanzado)"],
        index=1
    )
    
    enable_audio_reply = st.toggle("🔊 Respuesta por Voz Nativa (Browser API)", value=True)

    st.divider()
    st.subheader("🔍 Buscador de Frases (Tatoeba FTS5)")
    search_term = st.text_input("Buscar palabra clave:")
    if search_term:
        matches = query_tatoeba(search_term)
        if matches:
            for en, es in matches:
                st.markdown(f"**EN:** {en}\n\n**ES:** {es}")
                st.divider()
        else:
            st.info("Sin coincidencias exactas.")

    st.divider()
    if st.session_state.get("messages"):
        transcript = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
        st.download_button("📥 Descargar Reporte de Clase", transcript, "RoboTutor_Report.txt", "text/plain")

BASE_SYSTEM_PROMPT = """You are RoboTutor, an AI English teacher built on Task-Based Language Teaching (TBLT).

CORE PEDAGOGICAL PROTOCOL:
1. COMPREHENSIBLE INPUT (i+1): Keep 85% easy, 15% challenging. Keep responses focused and concise (3 to 4 complete sentences). NEVER stop mid-sentence.
2. RECASTING TECHNIQUE: Never interrupt or penalize explicitly. Rephrase student mistakes naturally inside your answer.
3. LEXICAL CHUNKS: Use natural collocations and sentence patterns.
4. ACTIVE ENGAGEMENT: Always close your response with a clear, open-ended question.
"""

full_system_instruction = BASE_SYSTEM_PROMPT + "\n" + get_cefr_instructions(cefr_level)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": f"Hello! I am RoboTutor. I see you are practicing at the **{cefr_level}** level. How are you doing today?"}
    ]

if "processed_audio_hashes" not in st.session_state:
    st.session_state.processed_audio_hashes = set()

# Renderizado de historial
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Escribe tu mensaje en inglés...")
audio_val = st.audio_input("🎙️ Graba tu respuesta hablada")

active_text = None
active_audio_tuple = None

if user_input:
    active_text = user_input
elif audio_val is not None:
    audio_bytes = audio_val.getvalue()
    audio_hash = hashlib.md5(audio_bytes).hexdigest()
    if audio_hash not in st.session_state.processed_audio_hashes:
        st.session_state.processed_audio_hashes.add(audio_hash)
        
        # Extraer y limpiar el tipo MIME para eliminar sufijos como ';codecs=opus'
        raw_mime = audio_val.type or "audio/wav"
        clean_mime = raw_mime.split(";")[0].strip()
        active_audio_tuple = (audio_bytes, clean_mime)

if active_text or active_audio_tuple:
    recent_messages = st.session_state.messages[-4:]
    formatted_contents = []
    for m in recent_messages:
        role = "user" if m["role"] == "user" else "model"
        formatted_contents.append(
            types.Content(role=role, parts=[types.Part.from_text(text=m["content"])])
        )

    if active_text:
        st.session_state.messages.append({"role": "user", "content": active_text})
        with st.chat_message("user"):
            st.markdown(active_text)
        formatted_contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=active_text)])
        )

    elif active_audio_tuple:
        bytes_data, clean_mime = active_audio_tuple
        with st.chat_message("user"):
            st.audio(bytes_data, format=clean_mime)
            st.caption("🎙️ Mensaje de voz enviado")

        st.session_state.messages.append({"role": "user", "content": "🎙️ [Mensaje de voz enviado]"})

        prompt_instruction = "Listen to my audio. Recast any grammar mistakes naturally, answer in complete sentences, and end with an open question."
        audio_part = types.Part.from_bytes(data=bytes_data, mime_type=clean_mime)
        text_part = types.Part.from_text(text=prompt_instruction)

        formatted_contents.append(
            types.Content(role="user", parts=[audio_part, text_part])
        )

    with st.chat_message("assistant"):
        with st.spinner("RoboTutor está procesando tu respuesta..."):
            try:
                bot_reply = generate_response_with_fallback(formatted_contents, full_system_instruction)
                st.markdown(bot_reply)
                st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                if enable_audio_reply:
                    speak_in_browser(bot_reply)
            except Exception as e:
                st.error(f"Error de conexión con la API de Gemini: {e}")
