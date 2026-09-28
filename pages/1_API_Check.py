import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="API Check",
    page_icon="🔌",
    layout="wide"
)

st.title("🔌 API Connection Check")

st.write(
    "This page checks whether the saved API keys can connect and lists "
    "the model IDs available to each account."
)

if st.button("Check API Connections", type="primary"):

    # -----------------------------
    # OPENAI
    # -----------------------------
    st.subheader("OpenAI")

    try:
        openai_client = OpenAI(
            api_key=st.secrets["OPENAI_API_KEY"]
        )

        openai_models = openai_client.models.list()

        openai_ids = sorted([
            model.id for model in openai_models.data
        ])

        st.success("OpenAI API key connected successfully.")

        st.write("Available model IDs:")

        for model_id in openai_ids:
            st.code(model_id)

    except Exception as error:
        st.error("OpenAI connection failed.")
        st.write(str(error))

    st.divider()

    # -----------------------------
    # DEEPSEEK
    # -----------------------------
    st.subheader("DeepSeek")

    try:
        deepseek_client = OpenAI(
            api_key=st.secrets["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com"
        )

        deepseek_models = deepseek_client.models.list()

        deepseek_ids = sorted([
            model.id for model in deepseek_models.data
        ])

        st.success("DeepSeek API key connected successfully.")

        st.write("Available model IDs:")

        for model_id in deepseek_ids:
            st.code(model_id)

    except Exception as error:
        st.error("DeepSeek connection failed.")
        st.write(str(error))
