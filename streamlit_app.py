import streamlit as st

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Affiliate Response Assistant",
    page_icon="💬",
    layout="wide"
)

# -------------------------------------------------
# HEADER
# -------------------------------------------------

st.title("💬 Affiliate Response Assistant")

st.caption(
    "Generate short, natural affiliate responses in English and Bahasa Indonesia."
)

st.divider()

# -------------------------------------------------
# AFFILIATE INFORMATION
# -------------------------------------------------

affiliate_name = st.text_input(
    "Affiliate Name",
    placeholder="Example: Rizky"
)

affiliate_question = st.text_area(
    "Affiliate Question",
    placeholder="Paste the affiliate's message here...",
    height=140
)

generate_button = st.button(
    "✨ Generate Response",
    type="primary",
    use_container_width=True
)

st.divider()

# -------------------------------------------------
# FIXED BILINGUAL RESPONSE AREA
# -------------------------------------------------

english_column, bahasa_column = st.columns(2)

with english_column:

    st.subheader("🇬🇧 English")

    st.markdown("**Question**")

    english_question = st.text_area(
        "English Question",
        value="",
        height=100,
        disabled=True,
        label_visibility="collapsed",
        key="english_question"
    )

    st.markdown("**Response**")

    english_response = st.text_area(
        "English Response",
        value="",
        height=220,
        disabled=True,
        label_visibility="collapsed",
        key="english_response"
    )

    st.button(
        "📋 Copy English",
        use_container_width=True,
        disabled=True
    )


with bahasa_column:

    st.subheader("🇮🇩 Bahasa Indonesia")

    st.markdown("**Pertanyaan**")

    bahasa_question = st.text_area(
        "Bahasa Question",
        value="",
        height=100,
        disabled=True,
        label_visibility="collapsed",
        key="bahasa_question"
    )

    st.markdown("**Respons**")

    bahasa_response = st.text_area(
        "Bahasa Response",
        value="",
        height=220,
        disabled=True,
        label_visibility="collapsed",
        key="bahasa_response"
    )

    st.button(
        "📋 Copy Bahasa",
        use_container_width=True,
        disabled=True
    )

# -------------------------------------------------
# SAVE
# -------------------------------------------------

st.divider()

st.button(
    "💾 Save Conversation",
    use_container_width=True,
    disabled=True
)

# -------------------------------------------------
# TEMPORARY TEST MESSAGE
# -------------------------------------------------

if generate_button:

    if not affiliate_name.strip():
        st.warning("Please enter the affiliate name.")

    elif not affiliate_question.strip():
        st.warning("Please paste the affiliate question.")

    else:
        st.success(
            "Interface is working. AI generation will be connected in the next steps."
        )
