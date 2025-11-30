import os
import json
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv
from pypdf import PdfReader
from contextlib import asynccontextmanager

# Carica le variabili d'ambiente
load_dotenv()

# --- CONFIGURAZIONE PERCORSI ---
# Qui costruiamo i percorsi corretti
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE_DIR, "knowledge_base")

# Percorsi corretti (Senza errori di battitura)
PATH_RED_FLAGS = os.path.join(KB_DIR, "phase_1_safety", "red_flags.json")
PATH_CLINICAL = os.path.join(KB_DIR, "phase_2_clinical")
PATH_SEDI = os.path.join(KB_DIR, "phase_3_logistics", "sedi_ravenna.json")

# Variabili globali
RED_FLAGS_DATA = {}
CLINICAL_CONTEXT = ""
SEDI_DATA = {}

def load_data():
    global RED_FLAGS_DATA, CLINICAL_CONTEXT, SEDI_DATA
    print("🔄 Caricamento dati in corso...")

    # 1. Carica Red Flags
    if os.path.exists(PATH_RED_FLAGS):
        try:
            with open(PATH_RED_FLAGS, "r", encoding="utf-8") as f:
                RED_FLAGS_DATA = json.load(f)
            print("✅ Red Flags caricate.")
        except Exception as e:
            print(f"❌ Errore lettura Red Flags: {e}")
    else:
        print(f"⚠️ File Red Flags non trovato. Il codice cerca qui: {PATH_RED_FLAGS}")

    # 2. Carica PDF Clinici
    if os.path.exists(PATH_CLINICAL):
        pdf_files = [f for f in os.listdir(PATH_CLINICAL) if f.endswith(".pdf")]
        if pdf_files:
            for pdf_file in pdf_files:
                try:
                    reader = PdfReader(os.path.join(PATH_CLINICAL, pdf_file))
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    CLINICAL_CONTEXT += f"\n--- DOCUMENTO: {pdf_file} ---\n{text}"
                    print(f"✅ PDF caricato: {pdf_file}")
                except Exception as e:
                    print(f"❌ Errore lettura {pdf_file}: {e}")
        else:
            print("⚠️ Nessun PDF trovato.")
    else:
        print(f"⚠️ Cartella Clinica non trovata: {PATH_CLINICAL}")

    # 3. Carica Sedi
    if os.path.exists(PATH_SEDI):
        try:
            with open(PATH_SEDI, "r", encoding="utf-8") as f:
                SEDI_DATA = json.load(f)
            print("✅ Dati Sedi caricati.")
        except Exception as e:
            print(f"❌ Errore lettura Sedi: {e}")
    else:
        print(f"⚠️ File Sedi non trovato. Il codice cerca qui: {PATH_SEDI}")

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

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    user_msg = request.message.lower()

    # FASE 1: SICUREZZA
    if RED_FLAGS_DATA and "red_flags" in RED_FLAGS_DATA:
        for item in RED_FLAGS_DATA["red_flags"]:
            for keyword in item.get("keywords", []):
                if keyword.lower() in user_msg:
                    emergency_msg = RED_FLAGS_DATA.get("emergency_message", "ERRORE: CHIAMA IL 118")
                    return {"response": f"🚨 **ALLERTA SICUREZZA** 🚨\n\n{emergency_msg}"}

    # FASE 2: CLINICA
    bot_response = ""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = f"Sei un infermiere di triage. Usa questo contesto: {CLINICAL_CONTEXT[:30000]}... Domanda: {request.message}"
        response = model.generate_content(prompt)
        bot_response = response.text
    except Exception as e:
        bot_response = f"⚠️ Errore AI: {str(e)}"

    # FASE 3: LOGISTICA
    logistics_info = ""
    if SEDI_DATA and "ecosistema_sanitario_ravenna" in SEDI_DATA:
        for sede in SEDI_DATA["ecosistema_sanitario_ravenna"].get("sedi", []):
            citta = sede.get("citta", "").lower()
            nome = sede.get("nome", "").lower()
            if citta in user_msg or nome in user_msg:
                logistics_info += f"\n\n📍 **{sede['nome']}**\n{sede['indirizzo']}, {sede['citta']}\nOrari: {sede.get('orari')}"

    return {"response": bot_response + logistics_info}

if __name__ == "__main__":
    print("✅ SISTEMA AVVIATO: Vai su http://127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
