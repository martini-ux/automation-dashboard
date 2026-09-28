import streamlit as st
import json
import re
import requests
from difflib import SequenceMatcher
from pathlib import Path
from supabase import create_client


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Affiliate Response Assistant",
    page_icon="💬",
    layout="wide"
)


# =========================================================
# LOAD KNOWLEDGE BASE + PROMPT
# =========================================================

BASE_DIR = Path(__file__).parent

with open(
    BASE_DIR / "data" / "knowledge_base.json",
    "r",
    encoding="utf-8"
) as file:
    knowledge_base = json.load(file)

with open(
    BASE_DIR / "prompts" / "affiliate_manager.txt",
    "r",
    encoding="utf-8"
) as file:
    manager_prompt = file.read()


# =========================================================
# SESSION STATE
# =========================================================

defaults = {
    "english_question": "",
    "english_response": "",
    "bahasa_question": "",
    "bahasa_response": "",
    "generated_affiliate_name": "",
    "generated_original_question": "",
    "conversation_saved": False
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# SUPABASE
# =========================================================

@st.cache_resource
def get_supabase_client():

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SECRET_KEY"]
    )


# =========================================================
# TEXT HELPERS
# =========================================================

def normalize_text(text):

    text = text.lower().strip()

    text = re.sub(
        r"[^\w\s]",
        "",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


def similarity(a, b):

    return SequenceMatcher(
        None,
        normalize_text(a),
        normalize_text(b)
    ).ratio()


# =========================================================
# SMART FAQ FALLBACK
# =========================================================

def smart_faq_match(question):

    normalized_question = normalize_text(question)

    question_words = normalized_question.split()

    best_match = None
    best_score = 0


    for faq in knowledge_base.get("faq", []):

        english_question = faq.get(
            "question_en",
            ""
        )

        bahasa_question = faq.get(
            "question_id",
            ""
        )

        tags = faq.get(
            "tags",
            []
        )


        # -----------------------------------------
        # Full-question similarity
        # -----------------------------------------

        english_score = similarity(
            question,
            english_question
        )

        bahasa_score = similarity(
            question,
            bahasa_question
        )

        score = max(
            english_score,
            bahasa_score
        )


        # -----------------------------------------
        # Tag / keyword similarity
        # -----------------------------------------

        for tag in tags:

            normalized_tag = normalize_text(
                tag
            )

            tag_words = normalized_tag.split()

            for question_word in question_words:

                for tag_word in tag_words:

                    word_score = SequenceMatcher(
                        None,
                        question_word,
                        tag_word
                    ).ratio()

                    if word_score >= 0.80:

                        score = max(
                            score,
                            0.85
                        )


        # -----------------------------------------
        # Pick best FAQ
        # -----------------------------------------

        if score > best_score:

            best_score = score

            best_match = faq


    # Require reasonable confidence
    if best_match and best_score >= 0.60:

        return {

            "english_question":
                best_match.get(
                    "question_en",
                    ""
                ),

            "english_response":
                best_match.get(
                    "answer_en",
                    ""
                ),

            "bahasa_question":
                best_match.get(
                    "question_id",
                    ""
                ),

            "bahasa_response":
                best_match.get(
                    "answer_id",
                    ""
                )
        }


    return None


# =========================================================
# PARSE DEEPSEEK RESPONSE
# =========================================================

def extract_section(
    text,
    section,
    next_section=None
):

    if next_section:

        pattern = (
            rf"{section}:\s*"
            rf"(.*?)"
            rf"(?=\n{next_section}:)"
        )

    else:

        pattern = (
            rf"{section}:\s*(.*)$"
        )


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

        "english_question":

            extract_section(
                text,
                "ENGLISH_QUESTION",
                "ENGLISH_RESPONSE"
            ),

        "english_response":

            extract_section(
                text,
                "ENGLISH_RESPONSE",
                "BAHASA_QUESTION"
            ),

        "bahasa_question":

            extract_section(
                text,
                "BAHASA_QUESTION",
                "BAHASA_RESPONSE"
            ),

        "bahasa_response":

            extract_section(
                text,
                "BAHASA_RESPONSE"
            )
    }


# =========================================================
# DEEPSEEK ONLY
# =========================================================

def generate_deepseek_response(
    affiliate_name,
    affiliate_question
):

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


    payload = {

        "model": "deepseek-flash",

        "messages": [

            {
                "role": "system",
                "content": manager_prompt
            },

            {
                "role": "user",
                "content": user_message
            }
        ],

        "temperature": 0.5,

        "max_tokens": 900
    }


    headers = {

        "Authorization":
            f"Bearer {st.secrets['DEEPSEEK_API_KEY']}",

        "Content-Type":
            "application/json"
    }


    response = requests.post(

        "https://api.deepseek.com/chat/completions",

        headers=headers,

        json=payload,

        timeout=60
    )


    if response.status_code != 200:

        raise RuntimeError(
            f"DeepSeek returned "
            f"{response.status_code}: "
            f"{response.text}"
        )


    data = response.json()


    output = (
        data["choices"][0]
        ["message"]
        ["content"]
    )


    return parse_ai_response(
        output
    )


# =========================================================
# SAVE CONVERSATION
# =========================================================

def save_conversation():

    supabase = get_supabase_client()


    conversation = {

        "affiliate_name":
            st.session_state.generated_affiliate_name,

        "original_question":
            st.session_state.generated_original_question,

        "english_question":
            st.session_state.english_question,

        "english_response":
            st.session_state.english_response,

        "bahasa_question":
            st.session_state.bahasa_question,

        "bahasa_response":
            st.session_state.bahasa_response
    }


    return (
        supabase
        .table(
            "affiliate_conversations"
        )
        .insert(
            conversation
        )
        .execute()
    )


# =========================================================
# HEADER
# =========================================================

st.title(
    "💬 Affiliate Response Assistant"
)

st.caption(
    "Generate short, natural affiliate responses "
    "in English and Bahasa Indonesia."
)

st.divider()


# =========================================================
# INPUT
# =========================================================

affiliate_name = st.text_input(
    "Affiliate Name",
    placeholder="Example: Rizky"
)


affiliate_question = st.text_area(
    "Affiliate Question",
    placeholder=(
        "Paste the affiliate's message here..."
    ),
    height=140
)


generate_button = st.button(
    "✨ Generate Response",
    type="primary",
    use_container_width=True
)


# =========================================================
# GENERATE
# =========================================================

if generate_button:


    if not affiliate_name.strip():

        st.warning(
            "Please enter the affiliate name."
        )


    elif not affiliate_question.strip():

        st.warning(
            "Please paste the affiliate question."
        )


    else:

        with st.spinner(
            "Creating response..."
        ):

            generated = False


            # =============================================
            # TRY DEEPSEEK FIRST
            # =============================================

            try:

                result = generate_deepseek_response(
                    affiliate_name,
                    affiliate_question
                )


                if (
                    result["english_response"]
                    and
                    result["bahasa_response"]
                ):

                    generated = True


            except Exception:

                generated = False


            # =============================================
            # KNOWLEDGE BASE FALLBACK
            # =============================================

            if not generated:

                result = smart_faq_match(
                    affiliate_question
                )


                if result:

                    generated = True

                    st.info(
                        "DeepSeek is currently unavailable, "
                        "so the Knowledge Base was used."
                    )


            # =============================================
            # STORE RESULT
            # =============================================

            if generated:

                st.session_state.english_question = (
                    result["english_question"]
                )

                st.session_state.english_response = (
                    result["english_response"]
                )

                st.session_state.bahasa_question = (
                    result["bahasa_question"]
                )

                st.session_state.bahasa_response = (
                    result["bahasa_response"]
                )

                st.session_state.generated_affiliate_name = (
                    affiliate_name.strip()
                )

                st.session_state.generated_original_question = (
                    affiliate_question.strip()
                )

                st.session_state.conversation_saved = False


            else:

                # Clear old answer so we do not
                # accidentally save an old conversation.

                st.session_state.english_question = ""
                st.session_state.english_response = ""

                st.session_state.bahasa_question = ""
                st.session_state.bahasa_response = ""

                st.session_state.generated_affiliate_name = ""
                st.session_state.generated_original_question = ""

                st.session_state.conversation_saved = False


                st.error(
                    "DeepSeek is currently unavailable "
                    "and I could not find a reliable answer "
                    "in the Knowledge Base."
                )


# =========================================================
# OUTPUT
# =========================================================

st.divider()


english_column, bahasa_column = (
    st.columns(2)
)


# =========================================================
# ENGLISH
# =========================================================

with english_column:


    st.subheader(
        "🇬🇧 English"
    )


    st.markdown(
        "**Question**"
    )


    st.text_area(
        "English Question",
        value=(
            st.session_state
            .english_question
        ),
        height=100,
        disabled=True,
        label_visibility="collapsed"
    )


    st.markdown(
        "**Response**"
    )


    st.text_area(
        "English Response",
        value=(
            st.session_state
            .english_response
        ),
        height=220,
        disabled=True,
        label_visibility="collapsed"
    )


# =========================================================
# BAHASA
# =========================================================

with bahasa_column:


    st.subheader(
        "🇮🇩 Bahasa Indonesia"
    )


    st.markdown(
        "**Pertanyaan**"
    )


    st.text_area(
        "Bahasa Question",
        value=(
            st.session_state
            .bahasa_question
        ),
        height=100,
        disabled=True,
        label_visibility="collapsed"
    )


    st.markdown(
        "**Respons**"
    )


    st.text_area(
        "Bahasa Response",
        value=(
            st.session_state
            .bahasa_response
        ),
        height=220,
        disabled=True,
        label_visibility="collapsed"
    )


# =========================================================
# SAVE CONVERSATION
# =========================================================

st.divider()


has_response = bool(

    st.session_state.english_response

    and

    st.session_state.bahasa_response
)


save_button = st.button(

    "💾 Save Conversation",

    use_container_width=True,

    disabled=(
        not has_response
        or
        st.session_state.conversation_saved
    )
)


if save_button:


    try:

        with st.spinner(
            "Saving conversation..."
        ):

            save_conversation()


        st.session_state.conversation_saved = True


        st.success(
            "Conversation saved successfully."
        )


    except Exception as e:

        st.error(
            f"Supabase error: {str(e)}"
        )


if st.session_state.conversation_saved:

    st.caption(
        "✅ This conversation has been saved."
    )
