import streamlit as st
import google.generativeai as genai
import os
import json
from pypdf import PdfReader

# --- CONFIGURAZIONE PAGINA (FRONTEND) ---
st.set_page_config(page_title="Triage Chatbot", page_icon="🏥")
st.title("🏥 Assistente Triage Emilia-Romagna")
st.markdown("Descrivi il tuo sintomo. In caso di emergenza, chiama il 118.\n\n*Describe your symptoms. In case of emergency, call 118.*")

# --- 1. CONFIGURAZIONE AI ---
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("⚠️ ERRORE: Chiave API non trovata! Configurala nei 'Secrets' di Streamlit.")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. CARICAMENTO DATI (BACKEND LOGIC) ---
@st.cache_resource
def load_knowledge_base():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    kb_dir = os.path.join(base_dir, "knowledge_base")
    
    data = {"red_flags": {}, "context": "", "protocol": "", "sedi": {}}
    
    path_rf = os.path.join(kb_dir, "phase_1_safety", "red_flags.json")
    path_cl = os.path.join(kb_dir, "phase_2_clinical")
    path_pr = os.path.join(kb_dir, "phase_2_clinical", "protocollo_domande.json")
    path_se = os.path.join(kb_dir, "phase_3_logistics", "sedi_emilia_romagna.json")

    # Caricamento sicuro dei file
    if os.path.exists(path_rf):
        with open(path_rf, "r", encoding="utf-8") as f:
            data["red_flags"] = json.load(f)

    if os.path.exists(path_cl):
        for f_name in os.listdir(path_cl):
            if f_name.endswith(".pdf"):
                try:
                    reader = PdfReader(os.path.join(path_cl, f_name))
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    data["context"] += f"\n--- MANUALE: {f_name} ---\n{text}"
                except:
                    pass

    if os.path.exists(path_pr):
        with open(path_pr, "r", encoding="utf-8") as f:
            data["protocol"] = json.dumps(json.load(f), indent=2, ensure_ascii=False)

    if os.path.exists(path_se):
        with open(path_se, "r", encoding="utf-8") as f:
            data["sedi"] = json.load(f)
            
    return data

KB = load_knowledge_base()

# --- 3. GESTIONE MEMORIA E RESET ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Bottone Reset nella barra laterale
with st.sidebar:
    if st.button("🗑️ Nuova Chat / New Chat"):
        st.session_state.messages = []
        st.rerun()

# Visualizzazione messaggi precedenti
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 4. LOGICA DEL CERVELLO (MAIN LOOP) ---
if prompt := st.chat_input("Scrivi qui / Type here..."):
    
    # Mostra messaggio utente
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    user_msg = prompt.lower()
    bot_reply = ""
    is_emergency = False

    # --- FASE 1: SICUREZZA (RED FLAGS) ---
    if "red_flags" in KB["red_flags"]:
        for item in KB["red_flags"]["red_flags"]:
            for keyword in item.get("keywords", []):
                if keyword.lower() in user_msg:
                    is_emergency = True
                    emerg_msg = KB["red_flags"].get("emergency_message", "CHIAMA IL 118")
                    bot_reply = f"🚨 **ALLERTA SICUREZZA / SAFETY ALERT** 🚨\n\n{emerg_msg}\n\n*Call 118 immediately.*\n\n*(Rilevato/Detected: {keyword})*"
                    break
    
    # --- FASE 2: CLINICA (AI INTELLIGENTE) ---
    if not is_emergency:
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            
            # Creiamo una trascrizione della chat per l'AI
            chat_transcript = ""
            for msg in st.session_state.messages:
                role_label = "PAZIENTE" if msg["role"] == "user" else "INFERMIERE"
                chat_transcript += f"{role_label}: {msg['content']}\n"

            # IL PROMPT CHE GESTISCE LINGUA E DOMANDE SEQUENZIALI
            system_prompt = f"""
            Sei un infermiere di triage esperto dell'AUSL Romagna.
            
            STORICO CONVERSAZIONE:
            {chat_transcript}
            
            ### 1. REGOLE LINGUA (FONDAMENTALE):
            - Rileva la lingua dell'utente.
            - Se scrive in INGLESE -> RISPONDI SEMPRE IN INGLESE.
            - Se scrive in ITALIANO -> RISPONDI SEMPRE IN ITALIANO.
            - Non cambiare lingua a caso.

            ### 2. PROTOCOLLO SEQUENZIALE (NON FARE LISTE):
            Devi fare domande UNO ALLA VOLTA.
            
            - **STEP A (Città):** Se non sai in che città è l'utente, chiedilo. Non puoi fare triage senza sapere dove mandarlo.
            - **STEP B (Clinica):** - Identifica il dato mancante più importante secondo il protocollo.
              - Fai SOLO QUELLA domanda.
              - Aspetta la risposta.
              - NON chiedere "Hai febbre? E tosse? E mal di pancia?" tutto insieme.
            - **STEP C (Decisione):**
              - Appena capisci se è da CAU o PS, fermati e dai il verdetto.

            ### DATI PROTOCOLLO:
            {KB['protocol']}
            
            Rispondi ora al PAZIENTE.
            """
            
            response = model.generate_content(system_prompt)
            bot_reply = response.text
            
        except Exception as e:
            bot_reply = f"⚠️ Errore AI: {e}"

    # --- FASE 3: LOGISTICA (Mostra indirizzi) ---
    if not is_emergency:
        keywords = ["indicato", "consiglio", "recati", "vai al", "recommend", "go to", "suggest", "emergency room", "pronto soccorso"]
        triage_concluso = any(word in bot_reply.lower() for word in keywords)
        
        # Recupero lista città e ricerca
        sedi = KB["sedi"]["ecosistema_sanitario_regionale"].get("sedi", []) if "ecosistema_sanitario_regionale" in KB["sedi"] else []
        citta_utente = None
        nomi_citta = set(s.get("citta", "").lower() for s in sedi)
        
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "user":
                for city in nomi_citta:
                    if city in msg["content"].lower():
                        citta_utente = city
                        break
            if citta_utente: break
        
        if triage_concluso and citta_utente:
            sedi_citta = [s for s in sedi if s.get("citta", "").lower() == citta_utente]
            consiglia_cau = "cau" in bot_reply.lower() and "pronto soccorso" not in bot_reply.lower()
            sedi_citta.sort(key=lambda x: x.get("tipo") == "CAU", reverse=consiglia_cau)

            bot_reply += f"\n\n📍 **STRUTTURE A / FACILITIES IN {citta_utente.upper()}:**"
            for sede in sedi_citta:
                icona = "🟢" if "CAU" in sede.get("tipo") else "🏥"
                link_mon = f" | 🔗 [Monitoraggio]({sede['link_monitoraggio']})" if sede.get("link_monitoraggio") else ""
                bot_reply += f"\n\n{icona} **{sede['nome']}**\nIndirizzo: {sede['indirizzo']}\nOrari: {sede.get('orari')}{link_mon}"
        
    # Mostra risposta AI
    with st.chat_message("assistant"):
        st.markdown(bot_reply)
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})