import streamlit as st
import google.generativeai as genai
import os
import json
from pypdf import PdfReader

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Triage Chatbot", page_icon="🏥")
st.title("🏥 Assistente Triage Emilia-Romagna")
st.markdown("Descrivi il tuo sintomo. In caso di emergenza, chiama il 118.\n\n*Describe your symptoms. In case of emergency, call 118.*")

# --- 1. CONFIGURAZIONE AI ---
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("⚠️ ERRORE: Chiave API non trovata! Configurala nei 'Secrets'.")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. CARICAMENTO DATI ---
@st.cache_resource
def load_knowledge_base():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    kb_dir = os.path.join(base_dir, "knowledge_base")
    
    data = {"red_flags": {}, "context": "", "protocol": "", "sedi": {}}
    
    path_rf = os.path.join(kb_dir, "phase_1_safety", "red_flags.json")
    path_cl = os.path.join(kb_dir, "phase_2_clinical")
    path_pr = os.path.join(kb_dir, "phase_2_clinical", "protocollo_domande.json")
    path_se = os.path.join(kb_dir, "phase_3_logistics", "sedi_emilia_romagna.json")

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

# --- 3. GESTIONE CHAT ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history_text" not in st.session_state:
    st.session_state.history_text = ""

with st.sidebar:
    if st.button("🗑️ Nuova Chat / New Chat"):
        st.session_state.messages = []
        st.session_state.history_text = ""
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 4. LOGICA DEL CERVELLO ---
if prompt := st.chat_input("Come ti senti? / How do you feel?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    user_msg = prompt.lower()
    bot_reply = ""
    is_emergency = False

    # FASE 1: SICUREZZA
    if "red_flags" in KB["red_flags"]:
        for item in KB["red_flags"]["red_flags"]:
            for keyword in item.get("keywords", []):
                if keyword.lower() in user_msg:
                    is_emergency = True
                    emerg_msg = KB["red_flags"].get("emergency_message", "CHIAMA IL 118")
                    bot_reply = f"🚨 **ALLERTA SICUREZZA / SAFETY ALERT** 🚨\n\n{emerg_msg}\n\n*Call 118 immediately.*\n\n*(Rilevato/Detected: {keyword})*"
                    break
    
    # FASE 2: CLINICA (AI)
    if not is_emergency:
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            
            conversation_history = ""
            for msg in st.session_state.messages:
                conversation_history += f"{msg['role'].upper()}: {msg['content']}\n"

            # --- SYSTEM PROMPT MODIFICATO PER OBBLIGARE 1 DOMANDA ALLA VOLTA ---
            system_prompt = f"""
            Sei un infermiere di triage digitale dell'AUSL Romagna.
            
            CONTESTO:
            {conversation_history}
            
            ### REGOLE LINGUA:
            - Se l'utente scrive in INGLESE -> Rispondi in INGLESE.
            - Se l'utente scrive in ITALIANO -> Rispondi in ITALIANO.

            ### PROCEDURA OPERATIVA (SEQUENZIALE):
            Devi agire come un programma informatico che esegue un ciclo.

            1. **CHECK CITTÀ**:
               - Se NON sai la città dell'utente -> Chiedi SOLO la città. Non chiedere altro.
            
            2. **CHECK DATI CLINICI (LOOP)**:
               - Se sai la città, guarda il protocollo.
               - Identifica il **PRIMO** dato mancante necessario per valutare la gravità.
               - **VIETATO CHIEDERE PIÙ DI UNA COSA.**
               - Fai SOLO la domanda relativa a quel singolo dato mancante.
               - Aspetta la risposta dell'utente prima di passare al dato successivo.
            
            3. **FORMATO DOMANDA**:
               - Usa elenchi puntati o lettere (A, B, C) SOLO per le opzioni di risposta di QUELLA singola domanda.
               - Esempio CORRETTO:
                 "Quanto è alta la febbre?"
                 A) < 38
                 B) > 38
               - Esempio SBAGLIATO (VIETATO):
                 "Quanto è alta la febbre? E hai mal di testa?"

            4. **CONCLUSIONE**:
               - Appena hai dati sufficienti per capire se è grave (PS) o lieve (CAU), INTERROMPI le domande e dai il consiglio.

            ### DATI:
            {KB['protocol']}
            """
            
            response = model.generate_content(system_prompt)
            bot_reply = response.text
            
        except Exception as e:
            bot_reply = f"⚠️ Errore AI: {e}"

    # FASE 3: LOGISTICA
    if not is_emergency:
        keywords_conclusione = ["indicato", "consiglio", "recati", "vai al", "più opportuno", "recommend", "go to", "suggest", "urgently", "emergency room", "pronto soccorso"]
        triage_concluso = any(word in bot_reply.lower() for word in keywords_conclusione)
        
        sedi = KB["sedi"]["ecosistema_sanitario_regionale"].get("sedi", []) if "ecosistema_sanitario_regionale" in KB["sedi"] else []
        citta_utente = None
        nomi_citta_disponibili = set(s.get("citta", "").lower() for s in sedi)
        
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "user":
                for city in nomi_citta_disponibili:
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
                evidenza = " **(✓)**" if (consiglia_cau and "CAU" in sede.get("tipo")) or (not consiglia_cau and "PS" in sede.get("tipo")) else ""
                link_mon = f" | 🔗 [Monitoraggio/Status]({sede['link_monitoraggio']})" if sede.get("link_monitoraggio") else ""
                bot_reply += f"\n\n{icona} **{sede['nome']}**{evidenza}\nIndirizzo: {sede['indirizzo']}\nOrari: {sede.get('orari')}{link_mon}"
        
    with st.chat_message("assistant"):
        st.markdown(bot_reply)
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})