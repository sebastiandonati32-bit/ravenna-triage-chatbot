import google.generativeai as genai

print("--- INIZIO TEST ---")

# La tua chiave
api_key = "AIzaSyB3Tfm5y7cRiqN3rO_hLEO0ijx1faYDZR0"

try:
    genai.configure(api_key=api_key)
    print("📡 Chiave configurata. Chiedo la lista dei modelli a Google...")
    
    print("\n📋 ECCO I MODELLI DISPONIBILI:")
    print("-" * 30)
    
    found = False
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ {m.name}")
            found = True
            
    if not found:
        print("⚠️ Nessun modello trovato per 'generateContent'.")
        
    print("-" * 30)

except Exception as e:
    print(f"❌ ERRORE: {e}")

print("--- FINE TEST ---")