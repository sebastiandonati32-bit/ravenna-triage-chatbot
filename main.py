import os
import json
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
from pypdf import PdfReader
from contextlib import asynccontextmanager

load_dotenv()

# --- CONFIGURAZIONE PERCORSI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE_DIR, "knowledge_base")

PATH_RED_FLAGS = os.path.join(KB_DIR, "phase_1_safety", "red_flags.json")
PATH_CLINICAL = os.path.join(KB_DIR, "phase_2_clinical")
PATH_PROTOCOL = os.path.join(KB_DIR, "phase_2_clinical", "protocollo_domande.json")
PATH_SEDI = os.path.join(KB_DIR, "phase_3_logistics", "sedi_emilia_romagna.json")

# Variabili globali
RED_FLAGS_DATA = {}
CLINICAL_CONTEXT = ""
PROTOCOL_DATA = ""
SEDI_DATA = {}

# MEMORIA DELLA CONVERSAZIONE (Lista di dizionari)
# Ogni elemento sarà: {"role": "user/model", "text": "..."}
CHAT_HISTORY = []

def load_data():
    global RED_FLAGS_DATA, CLINICAL_CONTEXT, SEDI_DATA, PROTOCOL_DATA
    print("🔄 Caricamento dati in corso...")

    if os.path.exists(PATH_RED_FLAGS):
        with open(PATH_RED_FLAGS, "r", encoding="utf-8") as f:
            RED_FLAGS_DATA = json.load(f)
            print("✅ Red Flags caricate.")

    if os.path.exists(PATH_CLINICAL):
        pdf_files = [f for f in os.listdir(PATH_CLINICAL) if f.endswith(".pdf")]
        for pdf_file in pdf_files:
            try:
                reader = PdfReader(os.path.join(PATH_CLINICAL, pdf_file))
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                CLINICAL_CONTEXT += f"\n--- MANUALE CLINICO ---\n{text}"
                print(f"✅ PDF caricato: {pdf_file}")
            except:
                pass

    if os.path.exists(PATH_PROTOCOL):
        with open(PATH_PROTOCOL, "r", encoding="utf-8") as f:
            protocol_json = json.load(f)
            PROTOCOL_DATA = json.dumps(protocol_json, indent=2, ensure_ascii=False)
            print("✅ Protocollo caricato.")

    if os.path.exists(PATH_SEDI):
        with open(PATH_SEDI, "r", encoding="utf-8") as f:
            SEDI_DATA = json.load(f)
            print("✅ Dati Sedi caricati.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_data()
    yield

app = FastAPI(lifespan=lifespan)

api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

class ChatRequest(BaseModel):
    message: str
    reset: bool = False # Nuovo campo per resettare la memoria

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    global CHAT_HISTORY
    
    # Se il frontend chiede il reset (es. nuova chat), puliamo la memoria
    if request.reset:
        CHAT_HISTORY = []
        return {"response": "Chat resettata."}

    user_msg = request.message.lower()

    # FASE 1: SICUREZZA (Controllo immediato su ogni messaggio)
    if RED_FLAGS_DATA and "red_flags" in RED_FLAGS_DATA:
        for item in RED_FLAGS_DATA["red_flags"]:
            for keyword in item.get("keywords", []):
                if keyword.lower() in user_msg:
                    emergency_msg = RED_FLAGS_DATA.get("emergency_message", "CHIAMA IL 118")
                    return {"response": f"🚨 **ALLERTA SICUREZZA** 🚨\n\n{emergency_msg}\n\n*(Rilevato: {keyword})*"}

    # FASE 2: CLINICA (AI con Memoria Storica)
    bot_response = ""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Costruiamo la storia della conversazione per l'AI
        history_text = ""
        for chat in CHAT_HISTORY:
            role = "UTENTE" if chat["role"] == "user" else "INFERMIERE"
            history_text += f"{role}: {chat['text']}\n"
        
        # Aggiungiamo l'ultimo messaggio
        history_text += f"UTENTE: {request.message}\n"

        system_prompt = f"""
        Sei un infermiere di triage digitale dell'AUSL Romagna.
        
        OBIETTIVO:
        Eseguire un triage accurato seguendo il protocollo, passo dopo passo.
        
        MEMORIA CONVERSAZIONE:
        {history_text}
        
        REGOLE DI COMPORTAMENTO:
        1. Leggi la MEMORIA sopra. Non rifare domande a cui l'utente ha già risposto.
        2. Se l'utente ha appena risposto a una domanda, passa alla successiva del protocollo logico.
        3. Se l'utente non ha detto la città, chiedila.
        4. NON dare il verdetto finale (CAU o PS) finché non hai un quadro completo (almeno 2-3 domande fatte).
        5. Quando fai domande, usa SEMPRE il formato a scelta multipla (A, B, C).
        6. SOLO ALLA FINE, usa la frase: "In base a quello che mi hai riportato, sembra essere più indicato..."
        
        DATI CLINICI:
        {PROTOCOL_DATA}
        {CLINICAL_CONTEXT[:20000]}
        """
        
        response = model.generate_content(system_prompt)
        bot_response = response.text
        
        # Salviamo lo scambio in memoria
        CHAT_HISTORY.append({"role": "user", "text": request.message})
        CHAT_HISTORY.append({"role": "model", "text": bot_response})

    except Exception as e:
        bot_response = f"⚠️ Errore AI. Vai al CAU per sicurezza."

    # FASE 3: LOGISTICA INTELLIGENTE
    logistics_info = ""
    
    # Parole chiave di conclusione
    keywords_conclusione = ["indicato", "consiglio", "recati", "vai al", "più opportuno", "dirigiti"]
    triage_concluso = any(word in bot_response.lower() for word in keywords_conclusione)
    domanda_esplicita = "dove" in user_msg or "indirizzo" in user_msg or "via" in user_msg

    if (triage_concluso or domanda_esplicita) and SEDI_DATA:
        sedi = SEDI_DATA["ecosistema_sanitario_regionale"].get("sedi", [])
        
        # Cerca città nella storia completa (più affidabile)
        full_text = history_text.lower()
        citta_utente = None
        for sede in sedi:
            if sede.get("citta", "").lower() in full_text:
                citta_utente = sede.get("citta", "").lower()
                break
        
        if citta_utente:
            sedi_citta = [s for s in sedi if s.get("citta", "").lower() == citta_utente]
            consiglia_cau = "cau" in bot_response.lower()
            sedi_citta.sort(key=lambda x: x.get("tipo") == "CAU", reverse=consiglia_cau)

            if sedi_citta:
                logistics_info += f"\n\n📍 **STRUTTURE A {citta_utente.upper()}:**"
                for sede in sedi_citta:
                    icona = "🟢" if "CAU" in sede.get("tipo") else "🏥"
                    evidenza = " **(CONSIGLIATO)**" if (consiglia_cau and "CAU" in sede.get("tipo")) else ""
                    link_mon = f" | 🔗 [Monitoraggio File]({sede['link_monitoraggio']})" if sede.get("link_monitoraggio") else ""
                    logistics_info += f"\n\n{icona} **{sede['nome']}**{evidenza}\nIndirizzo: {sede['indirizzo']}\nOrari: {sede.get('orari')}{link_mon}"

    return {"response": bot_response + logistics_info}

if __name__ == "__main__":
    print("✅ SISTEMA AVVIATO: Vai su http://127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)