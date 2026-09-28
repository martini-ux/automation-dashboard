import streamlit as st
import json
import re
import requests

from difflib import SequenceMatcher
from pathlib import Path


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Affiliate Response Assistant",
    page_icon="💬",
    layout="wide"
)


# =========================================================
# SETTINGS
# =========================================================

GROQ_MODEL = "openai/gpt-oss-120b"
DEEPSEEK_MODEL = "deepseek-flash"

GROQ_URL = (
    "https://api.groq.com/openai/v1/chat/completions"
)

DEEPSEEK_URL = (
    "https://api.deepseek.com/chat/completions"
)


# =========================================================
# LOAD KNOWLEDGE BASE + MANAGER PROMPT
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
    "bahasa_response": ""
}


for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text(text):

    text = str(text).lower().strip()

    text = re.sub(
        r"[^\w\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def tokenize(text):

    return [
        word
        for word in normalize_text(text).split()
        if len(word) >= 2
    ]


# =========================================================
# SEARCH SYNONYMS
#
# Helps English + Indonesian questions retrieve the same
# knowledge.
# =========================================================

SYNONYMS = {

    "commission": [
        "commission",
        "commision",
        "komisi",
        "revshare",
        "earning",
        "earnings",
        "profit"
    ],

    "payout": [
        "payout",
        "payment",
        "withdraw",
        "withdrawal",
        "balance",
        "pembayaran",
        "penarikan",
        "saldo"
    ],

    "link": [
        "link",
        "affiliate",
        "tracking",
        "tautan",
        "link afiliasi"
    ],

    "promo": [
        "promo",
        "code",
        "kode",
        "promotion",
        "promosi"
    ],

    "wallet": [
        "wallet",
        "dompet",
        "player account",
        "payment wallet"
    ],

    "ftd": [
        "ftd",
        "first time depositor",
        "deposit",
        "depositor",
        "setoran"
    ],

    "subid": [
        "subid",
        "tracking",
        "campaign",
        "traffic"
    ],

    "player": [
        "player",
        "players",
        "pemain",
        "active player",
        "pemain aktif"
    ],

    "registration": [
        "registration",
        "register",
        "affiliate",
        "daftar",
        "pendaftaran"
    ],

    "marketing": [
        "marketing",
        "promotion",
        "traffic",
        "audience",
        "promosi",
        "traffic source"
    ]
}


# =========================================================
# EXPAND USER QUERY
# =========================================================

def expand_query(question):

    normalized = normalize_text(question)

    words = set(
        tokenize(question)
    )


    for main_word, related_words in SYNONYMS.items():

        found = False

        for related in related_words:

            related_normalized = normalize_text(
                related
            )


            if related_normalized in normalized:
                found = True
                break


            for question_word in words:

                for related_word in tokenize(
                    related_normalized
                ):

                    score = SequenceMatcher(
                        None,
                        question_word,
                        related_word
                    ).ratio()


                    if score >= 0.84:

                        found = True
                        break


                if found:
                    break


            if found:
                break


        if found:

            words.add(
                main_word
            )

            for related in related_words:

                for word in tokenize(related):
                    words.add(word)


    return words


# =========================================================
# BUILD SEARCHABLE KNOWLEDGE CHUNKS
# =========================================================

def create_knowledge_chunks():

    chunks = []


    # -----------------------------------------------------
    # FAQ — each FAQ is its own chunk
    # -----------------------------------------------------

    for faq in knowledge_base.get(
        "faq",
        []
    ):

        chunks.append({
            "path":
                "FAQ > "
                + faq.get(
                    "id",
                    "FAQ"
                ),

            "data":
                faq
        })


    # -----------------------------------------------------
    # Troubleshooting — each issue separately
    # -----------------------------------------------------

    for item in knowledge_base.get(
        "troubleshooting",
        []
    ):

        chunks.append({
            "path":
                "Troubleshooting > "
                + item.get(
                    "issue",
                    "Issue"
                ),

            "data":
                item
        })


    # -----------------------------------------------------
    # Affiliate classes separately
    # -----------------------------------------------------

    affiliate_classes = knowledge_base.get(
        "affiliate_classes",
        {}
    )


    for class_name, class_data in (
        affiliate_classes.items()
    ):

        chunks.append({
            "path":
                f"Affiliate Class > {class_name}",

            "data":
                class_data
        })


    # -----------------------------------------------------
    # Main knowledge sections
    # -----------------------------------------------------

    section_names = [

        "commission",

        "payout_rules",

        "affiliate_link_generation",

        "promo_codes",

        "payment_wallet",

        "glossary",

        "promo_material_guidelines",

        "compliance",

        "onboarding",

        "final_strategy",

        "registration",

        "activation"
    ]


    for section_name in section_names:

        section = knowledge_base.get(
            section_name
        )


        if section is not None:

            chunks.append({
                "path":
                    section_name,

                "data":
                    section
            })


    return chunks


KNOWLEDGE_CHUNKS = create_knowledge_chunks()


# =========================================================
# SCORE KNOWLEDGE CHUNK
# =========================================================

def score_chunk(
    question,
    query_words,
    chunk
):

    chunk_text = (
        chunk["path"]
        + " "
        + json.dumps(
            chunk["data"],
            ensure_ascii=False
        )
    )


    chunk_normalized = normalize_text(
        chunk_text
    )

    chunk_words = set(
        tokenize(chunk_text)
    )


    score = 0.0


    # -----------------------------------------------------
    # Exact keyword matches
    # -----------------------------------------------------

    for query_word in query_words:

        if query_word in chunk_words:

            score += 4.0


        elif query_word in chunk_normalized:

            score += 2.0


    # -----------------------------------------------------
    # Fuzzy word matches
    # Handles misspellings: commission / commision
    # -----------------------------------------------------

    for query_word in query_words:

        best_word_score = 0


        for chunk_word in chunk_words:

            if abs(
                len(query_word)
                -
                len(chunk_word)
            ) > 4:

                continue


            fuzzy_score = SequenceMatcher(
                None,
                query_word,
                chunk_word
            ).ratio()


            best_word_score = max(
                best_word_score,
                fuzzy_score
            )


        if best_word_score >= 0.90:

            score += 2.0


        elif best_word_score >= 0.82:

            score += 1.0


    # -----------------------------------------------------
    # Bonus if query looks like the FAQ question
    # -----------------------------------------------------

    if chunk["path"].startswith("FAQ"):

        faq_question_en = str(
            chunk["data"].get(
                "question_en",
                ""
            )
        )

        faq_question_id = str(
            chunk["data"].get(
                "question_id",
                ""
            )
        )


        english_similarity = SequenceMatcher(
            None,
            normalize_text(question),
            normalize_text(faq_question_en)
        ).ratio()


        bahasa_similarity = SequenceMatcher(
            None,
            normalize_text(question),
            normalize_text(faq_question_id)
        ).ratio()


        score += (
            max(
                english_similarity,
                bahasa_similarity
            )
            * 4
        )


    return score


# =========================================================
# RETRIEVE ONLY RELEVANT KNOWLEDGE
# =========================================================

def retrieve_knowledge(
    question,
    max_chunks=5,
    max_characters=7500
):

    query_words = expand_query(
        question
    )


    scored = []


    for chunk in KNOWLEDGE_CHUNKS:

        score = score_chunk(
            question,
            query_words,
            chunk
        )


        if score > 0:

            scored.append(
                (
                    score,
                    chunk
                )
            )


    scored.sort(
        key=lambda item: item[0],
        reverse=True
    )


    selected = []

    total_characters = 0


    for score, chunk in scored[:max_chunks]:

        chunk_string = json.dumps(
            {
                "section":
                    chunk["path"],

                "information":
                    chunk["data"]
            },
            ensure_ascii=False,
            indent=2
        )


        if (
            total_characters
            +
            len(chunk_string)
            >
            max_characters
        ):

            continue


        selected.append(
            chunk_string
        )

        total_characters += len(
            chunk_string
        )


    # -----------------------------------------------------
    # Always include core manager rules
    # -----------------------------------------------------

    manager_rules = json.dumps(
        {
            "manager_rules":
                knowledge_base.get(
                    "manager_rules",
                    {}
                )
        },
        ensure_ascii=False,
        indent=2
    )


    selected.insert(
        0,
        manager_rules
    )


    return "\n\n".join(
        selected
    )


# =========================================================
# STRUCTURED OUTPUT SCHEMA FOR GROQ
# =========================================================

GROQ_RESPONSE_FORMAT = {

    "type":
        "json_schema",

    "json_schema": {

        "name":
            "affiliate_response",

        "strict":
            True,

        "schema": {

            "type":
                "object",

            "properties": {

                "english_question": {
                    "type":
                        "string"
                },

                "english_response": {
                    "type":
                        "string"
                },

                "bahasa_question": {
                    "type":
                        "string"
                },

                "bahasa_response": {
                    "type":
                        "string"
                }
            },

            "required": [

                "english_question",

                "english_response",

                "bahasa_question",

                "bahasa_response"
            ],

            "additionalProperties":
                False
        }
    }
}


# =========================================================
# BUILD LLM PROMPT
# =========================================================

def build_user_prompt(
    affiliate_name,
    affiliate_question
):

    relevant_knowledge = (
        retrieve_knowledge(
            affiliate_question
        )
    )


    return f"""
AFFILIATE NAME:
{affiliate_name}

AFFILIATE MESSAGE:
{affiliate_question}

RELEVANT OFFICIAL KNOWLEDGE:
{relevant_knowledge}

IMPORTANT:

Use the official knowledge above as the source of truth.

Do not invent company rules, numbers, requirements,
payout information, commission information, or policies.

If the official knowledge does not contain enough information
to safely answer an official/company-specific question, use:

English:
Let me double-check that for you so I can give you the correct information.

Bahasa Indonesia:
Biar saya cek dulu supaya saya bisa memberikan informasi yang benar kepada kamu.

Write ONE best response.

Keep it natural, friendly, human-like, useful, and short enough
for Telegram or WhatsApp.

Always provide both English and Bahasa Indonesia.
"""


# =========================================================
# GROQ — PRIMARY LLM
# =========================================================

def generate_with_groq(
    affiliate_name,
    affiliate_question
):

    user_prompt = build_user_prompt(
        affiliate_name,
        affiliate_question
    )


    payload = {

        "model":
            GROQ_MODEL,

        "messages": [

            {
                "role":
                    "system",

                "content":
                    manager_prompt
            },

            {
                "role":
                    "user",

                "content":
                    user_prompt
            }
        ],

        "reasoning_effort":
            "low",

        "max_completion_tokens":
            700,

        "response_format":
            GROQ_RESPONSE_FORMAT
    }


    headers = {

        "Authorization":
            f"Bearer {st.secrets['GROQ_API_KEY']}",

        "Content-Type":
            "application/json"
    }


    response = requests.post(

        GROQ_URL,

        headers=headers,

        json=payload,

        timeout=45
    )


    if response.status_code != 200:

        raise RuntimeError(
            f"Groq request failed: "
            f"{response.status_code}"
        )


    data = response.json()


    content = (
        data["choices"][0]
        ["message"]
        ["content"]
    )


    result = json.loads(
        content
    )


    return result


# =========================================================
# DEEPSEEK — BACKUP LLM
# =========================================================

def generate_with_deepseek(
    affiliate_name,
    affiliate_question
):

    user_prompt = build_user_prompt(
        affiliate_name,
        affiliate_question
    )


    deepseek_prompt = (
        user_prompt
        +
        """

Return ONLY valid JSON in exactly this structure:

{
  "english_question": "...",
  "english_response": "...",
  "bahasa_question": "...",
  "bahasa_response": "..."
}

Do not include markdown or code fences.
"""
    )


    payload = {

        "model":
            DEEPSEEK_MODEL,

        "messages": [

            {
                "role":
                    "system",

                "content":
                    manager_prompt
            },

            {
                "role":
                    "user",

                "content":
                    deepseek_prompt
            }
        ],

        "thinking": {
            "type":
                "disabled"
        },

        "max_tokens":
            700,

        "temperature":
            0.4
    }


    headers = {

        "Authorization":
            f"Bearer {st.secrets['DEEPSEEK_API_KEY']}",

        "Content-Type":
            "application/json"
    }


    response = requests.post(

        DEEPSEEK_URL,

        headers=headers,

        json=payload,

        timeout=45
    )


    if response.status_code != 200:

        raise RuntimeError(
            f"DeepSeek request failed: "
            f"{response.status_code}"
        )


    data = response.json()


    content = (
        data["choices"][0]
        ["message"]
        ["content"]
    )


    # Remove accidental Markdown fences
    content = re.sub(
        r"^```json\s*",
        "",
        content.strip(),
        flags=re.IGNORECASE
    )

    content = re.sub(
        r"\s*```$",
        "",
        content.strip()
    )


    return json.loads(
        content
    )


# =========================================================
# FAQ FALLBACK
# =========================================================

def faq_fallback(question):

    query_words = expand_query(
        question
    )


    best_faq = None

    best_score = 0


    for faq in knowledge_base.get(
        "faq",
        []
    ):

        chunk = {
            "path":
                "FAQ",

            "data":
                faq
        }


        score = score_chunk(
            question,
            query_words,
            chunk
        )


        if score > best_score:

            best_score = score
            best_faq = faq


    # Require a strong match.
    # Better to say "I will check" than give wrong facts.

    if (
        best_faq
        and
        best_score >= 8
    ):

        return {

            "english_question":
                best_faq.get(
                    "question_en",
                    question
                ),

            "english_response":
                best_faq.get(
                    "answer_en",
                    ""
                ),

            "bahasa_question":
                best_faq.get(
                    "question_id",
                    question
                ),

            "bahasa_response":
                best_faq.get(
                    "answer_id",
                    ""
                )
        }


    return {

        "english_question":
            question,

        "english_response":
            (
                "Let me double-check that for you "
                "so I can give you the correct information."
            ),

        "bahasa_question":
            question,

        "bahasa_response":
            (
                "Biar saya cek dulu supaya saya bisa "
                "memberikan informasi yang benar kepada kamu."
            )
    }


# =========================================================
# VALIDATE LLM RESULT
# =========================================================

def valid_result(result):

    if not isinstance(
        result,
        dict
    ):

        return False


    required = [

        "english_question",

        "english_response",

        "bahasa_question",

        "bahasa_response"
    ]


    for key in required:

        if (
            key not in result
            or
            not str(
                result[key]
            ).strip()
        ):

            return False


    return True


# =========================================================
# MAIN GENERATION PIPELINE
#
# GROQ
#   ↓ failure
# DEEPSEEK
#   ↓ failure
# KNOWLEDGE BASE
# =========================================================

def generate_response(
    affiliate_name,
    affiliate_question
):

    # -----------------------------------------------------
    # 1. GROQ PRIMARY
    # -----------------------------------------------------

    try:

        result = generate_with_groq(
            affiliate_name,
            affiliate_question
        )


        if valid_result(result):

            return result


    except Exception:

        pass


    # -----------------------------------------------------
    # 2. DEEPSEEK BACKUP
    # -----------------------------------------------------

    try:

        result = generate_with_deepseek(
            affiliate_name,
            affiliate_question
        )


        if valid_result(result):

            return result


    except Exception:

        pass


    # -----------------------------------------------------
    # 3. KNOWLEDGE BASE FALLBACK
    # -----------------------------------------------------

    return faq_fallback(
        affiliate_question
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


            result = generate_response(

                affiliate_name.strip(),

                affiliate_question.strip()
            )


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
# BAHASA INDONESIA
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
