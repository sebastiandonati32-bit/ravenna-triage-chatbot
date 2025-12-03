import streamlit as st
import requests

st.set_page_config(page_title="Triage Chatbot", page_icon="🏥")
st.title("🏥 Assistente Triage Emilia-Romagna")
st.markdown("Descrivi il tuo sintomo. In caso di emergenza, chiama il 118.")

# Gestione Sessione
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Al primo avvio, diciamo al server di pulire la memoria vecchia
    try:
        requests.post("http://127.0.0.1:8000/chat", json={"message": "", "reset": True})
    except:
        pass

# Sidebar per reset manuale
with st.sidebar:
    if st.button("🗑️ Nuova Chat"):
        st.session_state.messages = []
        try:
            requests.post("http://127.0.0.1:8000/chat", json={"message": "", "reset": True})
        except:
            pass
        st.rerun()

# Mostra chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input
if prompt := st.chat_input("Come ti senti?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Ragionamento clinico..."):
            try:
                response = requests.post("http://127.0.0.1:8000/chat", json={"message": prompt})
                if response.status_code == 200:
                    bot_reply = response.json().get("response", "Errore risposta.")
                else:
                    bot_reply = "⚠️ Errore server."
            except:
                bot_reply = "⚠️ Il cervello è spento!"
            
            st.markdown(bot_reply)
    
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})