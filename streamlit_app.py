import streamlit as st
import json
import re
from pathlib import Path
from openai import OpenAI


# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Affiliate Response Assistant",
    page_icon="💬",
    layout="wide"
)


# -------------------------------------------------
# LOAD KNOWLEDGE BASE + AI PROMPT
# -------------------------------------------------

BASE_DIR = Path(__file__).parent

with open(BASE_DIR / "data" / "knowledge_base.json", "r", encoding="utf-8") as file:
    knowledge_base = json.load(file)

with open(BASE_DIR / "prompts" / "affiliate_manager.txt", "r", encoding="utf-8") as file:
    manager_prompt = file.read()


# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------

defaults = {
    "english_question": "",
    "english_response": "",
    "bahasa_question": "",
    "bahasa_response": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# -------------------------------------------------
# DEEPSEEK CLIENT
# -------------------------------------------------

def get_deepseek_client():
    return OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com"
    )


# -------------------------------------------------
# EXACT FAQ FALLBACK
# -------------------------------------------------

def normalize_text(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def exact_faq_match(question):
    normalized_question = normalize_text(question)

    for faq in knowledge_base.get("faq", []):
        english = normalize_text(faq.get("question_en", ""))
        bahasa = normalize_text(faq.get("question_id", ""))

        if normalized_question == english or normalized_question == bahasa:
            return {
                "english_question": faq.get("question_en", ""),
                "english_response": faq.get("answer_en", ""),
                "bahasa_question": faq.get("question_id", ""),
                "bahasa_response": faq.get("answer_id", "")
            }

    return None


# -------------------------------------------------
# PARSE AI RESPONSE
# -------------------------------------------------

def extract_section(text, section, next_section=None):
    if next_section:
        pattern = rf"{section}:\s*(.*?)(?=\n{next_section}:)"
    else:
        pattern = rf"{section}:\s*(.*)$"

    match = re.search(
        pattern,
        text,
        flags=re.DOTALL | re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return ""


def parse_ai_response(text):
    return {
        "english_question": extract_section(
            text,
            "ENGLISH_QUESTION",
            "ENGLISH_RESPONSE"
        ),
        "english_response": extract_section(
            text,
            "ENGLISH_RESPONSE",
            "BAHASA_QUESTION"
        ),
        "bahasa_question": extract_section(
            text,
            "BAHASA_QUESTION",
            "BAHASA_RESPONSE"
        ),
        "bahasa_response": extract_section(
            text,
            "BAHASA_RESPONSE"
        )
    }


# -------------------------------------------------
# GENERATE RESPONSE
# -------------------------------------------------

def generate_response(affiliate_name, affiliate_question):

    client = get_deepseek_client()

    knowledge_text = json.dumps(
        knowledge_base,
        ensure_ascii=False,
        indent=2
    )

    user_message = f"""
AFFILIATE NAME:
{affiliate_name}

AFFILIATE MESSAGE:
{affiliate_question}

KNOWLEDGE BASE:
{knowledge_text}

Generate the best response according to your instructions.
"""

    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=[
            {
                "role": "system",
                "content": manager_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        temperature=0.5,
        max_tokens=900
    )

    output = response.choices[0].message.content

    return parse_ai_response(output)


# -------------------------------------------------
# HEADER
# -------------------------------------------------

st.title("💬 Affiliate Response Assistant")

st.caption(
    "Generate short, natural affiliate responses in English and Bahasa Indonesia."
)

st.divider()


# -------------------------------------------------
# INPUT
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


# -------------------------------------------------
# GENERATION
# -------------------------------------------------

if generate_button:

    if not affiliate_name.strip():
        st.warning("Please enter the affiliate name.")

    elif not affiliate_question.strip():
        st.warning("Please paste the affiliate question.")

    else:

        with st.spinner("Creating response..."):

            try:
                result = generate_response(
                    affiliate_name,
                    affiliate_question
                )

                if (
                    result["english_response"]
                    and result["bahasa_response"]
                ):
                    st.session_state.english_question = result["english_question"]
                    st.session_state.english_response = result["english_response"]
                    st.session_state.bahasa_question = result["bahasa_question"]
                    st.session_state.bahasa_response = result["bahasa_response"]

                else:
                    raise ValueError("AI response format was incomplete.")

            except Exception:

                fallback = exact_faq_match(
                    affiliate_question
                )

                if fallback:

                    st.session_state.english_question = fallback["english_question"]
                    st.session_state.english_response = fallback["english_response"]
                    st.session_state.bahasa_question = fallback["bahasa_question"]
                    st.session_state.bahasa_response = fallback["bahasa_response"]

                    st.info(
                        "AI was unavailable, so an exact FAQ answer was used."
                    )

                else:
                    st.error(
                        "AI service is temporarily unavailable. Please try again."
                    )


st.divider()


# -------------------------------------------------
# BILINGUAL OUTPUT
# -------------------------------------------------

english_column, bahasa_column = st.columns(2)


with english_column:

    st.subheader("🇬🇧 English")

    st.markdown("**Question**")

    st.text_area(
        "English Question",
        value=st.session_state.english_question,
        height=100,
        disabled=True,
        label_visibility="collapsed"
    )

    st.markdown("**Response**")

    st.text_area(
        "English Response",
        value=st.session_state.english_response,
        height=220,
        disabled=True,
        label_visibility="collapsed"
    )


with bahasa_column:

    st.subheader("🇮🇩 Bahasa Indonesia")

    st.markdown("**Pertanyaan**")

    st.text_area(
        "Bahasa Question",
        value=st.session_state.bahasa_question,
        height=100,
        disabled=True,
        label_visibility="collapsed"
    )

    st.markdown("**Respons**")

    st.text_area(
        "Bahasa Response",
        value=st.session_state.bahasa_response,
        height=220,
        disabled=True,
        label_visibility="collapsed"
    )


# -------------------------------------------------
# SAVE — COMING NEXT
# -------------------------------------------------

st.divider()

st.button(
    "💾 Save Conversation",
    use_container_width=True,
    disabled=True
)
