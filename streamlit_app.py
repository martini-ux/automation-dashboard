import streamlit as st
import json
import re
from pathlib import Path
from openai import OpenAI
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
# LOAD FILES
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

default_session_values = {
    "english_question": "",
    "english_response": "",
    "bahasa_question": "",
    "bahasa_response": "",
    "generated_affiliate_name": "",
    "generated_original_question": "",
    "conversation_saved": False
}


for key, value in default_session_values.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# DEEPSEEK CLIENT
# =========================================================

def get_deepseek_client():

    return OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com"
    )


# =========================================================
# SUPABASE CLIENT
# =========================================================

@st.cache_resource
def get_supabase_client():

    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SECRET_KEY"]
    )


# =========================================================
# TEXT NORMALIZATION
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


# =========================================================
# EXACT FAQ FALLBACK
# =========================================================

def exact_faq_match(question):

    normalized_question = normalize_text(
        question
    )

    for faq in knowledge_base.get("faq", []):

        english_question = normalize_text(
            faq.get(
                "question_en",
                ""
            )
        )

        bahasa_question = normalize_text(
            faq.get(
                "question_id",
                ""
            )
        )

        if (
            normalized_question == english_question
            or
            normalized_question == bahasa_question
        ):

            return {

                "english_question":
                    faq.get(
                        "question_en",
                        ""
                    ),

                "english_response":
                    faq.get(
                        "answer_en",
                        ""
                    ),

                "bahasa_question":
                    faq.get(
                        "question_id",
                        ""
                    ),

                "bahasa_response":
                    faq.get(
                        "answer_id",
                        ""
                    )
            }

    return None


# =========================================================
# PARSE AI RESPONSE
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
        flags=(
            re.DOTALL
            |
            re.IGNORECASE
        )
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
# GENERATE AI RESPONSE
# =========================================================

def generate_response(
    affiliate_name,
    affiliate_question
):

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


    output = (
        response
        .choices[0]
        .message
        .content
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


    result = (
        supabase
        .table(
            "affiliate_conversations"
        )
        .insert(
            conversation
        )
        .execute()
    )


    return result


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
# GENERATION
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

            try:

                result = generate_response(
                    affiliate_name,
                    affiliate_question
                )


                if (
                    result["english_response"]
                    and
                    result["bahasa_response"]
                ):

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

                    raise ValueError(
                        "AI response format was incomplete."
                    )


            except Exception as e:

                # -----------------------------------------
                # TEMPORARY DEBUG MESSAGE
                # Shows the real DeepSeek error
                # -----------------------------------------

                st.warning(
                    f"DeepSeek error: "
                    f"{type(e).__name__}: "
                    f"{str(e)}"
                )


                fallback = exact_faq_match(
                    affiliate_question
                )


                if fallback:

                    st.session_state.english_question = (
                        fallback["english_question"]
                    )

                    st.session_state.english_response = (
                        fallback["english_response"]
                    )

                    st.session_state.bahasa_question = (
                        fallback["bahasa_question"]
                    )

                    st.session_state.bahasa_response = (
                        fallback["bahasa_response"]
                    )

                    st.session_state.generated_affiliate_name = (
                        affiliate_name.strip()
                    )

                    st.session_state.generated_original_question = (
                        affiliate_question.strip()
                    )

                    st.session_state.conversation_saved = False


                    st.info(
                        "AI was unavailable, so an exact "
                        "FAQ answer was used."
                    )


                else:

                    st.error(
                        "AI service is temporarily unavailable. "
                        "Please try again."
                    )


# =========================================================
# OUTPUT
# =========================================================

st.divider()


english_column, bahasa_column = (
    st.columns(2)
)


# =========================================================
# ENGLISH COLUMN
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
# BAHASA COLUMN
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


save_disabled = (

    not has_response

    or

    st.session_state.conversation_saved
)


save_button = st.button(

    "💾 Save Conversation",

    use_container_width=True,

    disabled=save_disabled
)


# =========================================================
# SAVE BUTTON ACTION
# =========================================================

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

        # -----------------------------------------
        # TEMPORARY DEBUG MESSAGE
        # Shows the real Supabase error
        # -----------------------------------------

        st.error(
            f"Supabase error: "
            f"{type(e).__name__}: "
            f"{str(e)}"
        )


# =========================================================
# SAVED STATUS
# =========================================================

if st.session_state.conversation_saved:

    st.caption(
        "✅ This conversation has been saved."
    )
