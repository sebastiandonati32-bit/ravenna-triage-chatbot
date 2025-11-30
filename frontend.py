import streamlit as st
import requests

st.set_page_config(page_title="Triage Chatbot", page_icon="🏥")

st.title("🏥 Assistente Triage Ravenna")
st.write("Se vedi questo messaggio, il Frontend funziona!")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Come ti senti?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
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