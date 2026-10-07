"""
Language Translation Tool
CodeAlpha AI Internship - Task 1

A Streamlit app that translates text between languages using Google Translate
(through the deep-translator library, so no API key is needed) and can read
the translation aloud with gTTS.

Run with:  streamlit run app.py
"""

from io import BytesIO

import requests
import streamlit as st
from deep_translator import GoogleTranslator
from deep_translator.exceptions import (
    InvalidSourceOrTargetLanguage,
    LanguageNotSupportedException,
    NotValidLength,
    NotValidPayload,
    RequestError,
    TooManyRequests,
    TranslationNotFound,
)
from gtts import gTTS
from gtts.lang import tts_langs
from gtts.tts import gTTSError

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
AUTO_DETECT = "Auto-detect"   # label of the extra option in the source list
MAX_CHARS = 5000              # Google Translate's limit for a single request
DEFAULT_TARGET = "english"


class TranslationError(Exception):
    """Raised with a user-friendly message when a translation cannot be done."""


class SpeechError(Exception):
    """Raised with a user-friendly message when audio cannot be generated."""


# ----------------------------------------------------------------------------
# Language data
# ----------------------------------------------------------------------------
@st.cache_data
def get_translation_languages() -> dict[str, str]:
    """Return the languages Google Translate supports as {name: code}.

    Example: {"english": "en", "french": "fr", ...}. The list ships with
    deep-translator, so this works offline. Cached so it is built only once.
    """
    return GoogleTranslator().get_supported_languages(as_dict=True)


@st.cache_data
def get_speech_languages() -> set[str]:
    """Return the set of language codes that gTTS can speak."""
    return set(tts_langs().keys())


def format_language(name: str) -> str:
    """Turn an internal language name into a display label ("french" -> "French")."""
    return name if name == AUTO_DETECT else name.title()


# ----------------------------------------------------------------------------
# Core logic: translation and text-to-speech
# ----------------------------------------------------------------------------
def translate_text(text: str, source_code: str, target_code: str) -> str:
    """Send `text` to the translation API and return the translated string.

    `source_code` may be "auto" to let Google detect the language.
    Every failure is converted into a TranslationError with a readable message,
    so the UI only has to handle one exception type.
    """
    try:
        translator = GoogleTranslator(source=source_code, target=target_code)
        result = translator.translate(text)
    except (LanguageNotSupportedException, InvalidSourceOrTargetLanguage):
        raise TranslationError("That language is not supported. Please pick another one.")
    except NotValidLength:
        raise TranslationError(f"The text is too long. Please keep it under {MAX_CHARS} characters.")
    except NotValidPayload:
        raise TranslationError("The text could not be read. Please enter plain text.")
    except TooManyRequests:
        raise TranslationError("Too many requests were sent. Please wait a moment and try again.")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise TranslationError("Could not reach the translation service. Please check your internet connection.")
    except (RequestError, TranslationNotFound, requests.exceptions.RequestException):
        raise TranslationError("The translation service returned an error. Please try again.")
    except Exception as error:  # last-resort safety net so the app never crashes
        raise TranslationError(f"Something unexpected went wrong: {error}")

    if not result:
        raise TranslationError("No translation was returned for this text.")
    return result


@st.cache_data(show_spinner=False)
def text_to_speech(text: str, lang_code: str) -> bytes:
    """Convert `text` to spoken MP3 audio with gTTS and return the raw bytes.

    Cached, so pressing "Listen" again for the same text does not call the
    service a second time. Failures are raised as SpeechError.
    """
    try:
        buffer = BytesIO()
        gTTS(text=text, lang=lang_code).write_to_fp(buffer)  # write MP3 into memory
        return buffer.getvalue()
    except gTTSError:
        raise SpeechError("Could not generate audio. Please check your internet connection and try again.")
    except Exception as error:
        raise SpeechError(f"Audio generation failed: {error}")


# ----------------------------------------------------------------------------
# Session state and button callbacks
# ----------------------------------------------------------------------------
def init_session_state() -> None:
    """Create the values that must survive Streamlit's reruns."""
    defaults = {
        "source_lang": AUTO_DETECT,
        "target_lang": DEFAULT_TARGET,
        "input_text": "",
        "translation": "",       # last translated text
        "translation_lang": "",  # language name the translation is written in
        "audio": None,           # MP3 bytes for the last translation
        "error": "",             # message to show from the last action
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def swap_languages() -> None:
    """Swap source and target, and move the translation into the input box.

    Runs as a button callback, i.e. before the widgets are redrawn, which is
    the only moment Streamlit allows changing a widget's value from code.
    """
    state = st.session_state
    state.source_lang, state.target_lang = state.target_lang, state.source_lang
    if state.translation:
        state.input_text = state.translation
    clear_result()


def clear_result() -> None:
    """Forget the previous translation, audio and error message."""
    st.session_state.translation = ""
    st.session_state.translation_lang = ""
    st.session_state.audio = None
    st.session_state.error = ""


def run_translation() -> None:
    """Validate the input, call the API and store the result in session state."""
    state = st.session_state
    languages = get_translation_languages()
    text = state.input_text.strip()
    clear_result()

    # --- validation before calling the API ---
    if not text:
        state.error = "Please enter some text to translate."
        return
    if state.source_lang == state.target_lang:
        state.error = "Source and target languages are the same. Please choose different languages."
        return

    source_code = "auto" if state.source_lang == AUTO_DETECT else languages[state.source_lang]
    target_code = languages[state.target_lang]

    try:
        state.translation = translate_text(text, source_code, target_code)
        state.translation_lang = state.target_lang
    except TranslationError as error:
        state.error = str(error)


def run_speech() -> None:
    """Generate audio for the current translation and store it in session state."""
    state = st.session_state
    lang_code = get_translation_languages()[state.translation_lang]
    try:
        state.audio = text_to_speech(state.translation, lang_code)
        state.error = ""
    except SpeechError as error:
        state.audio = None
        state.error = str(error)


# ----------------------------------------------------------------------------
# User interface
# ----------------------------------------------------------------------------
def render_header() -> None:
    """Page title and short description."""
    st.title("🌐 Language Translation Tool")
    st.write(
        "Type or paste text, choose the languages, and get an instant translation. "
        "You can copy the result or listen to it being read aloud."
    )
    st.divider()


def render_language_selectors() -> None:
    """Source language, swap button and target language on one row."""
    names = list(get_translation_languages().keys())
    source_col, swap_col, target_col = st.columns([5, 1, 5], vertical_alignment="bottom")

    with source_col:
        st.selectbox("From", [AUTO_DETECT] + names, key="source_lang", format_func=format_language)
    with swap_col:
        # Swapping is impossible while the source is "Auto-detect",
        # because "Auto-detect" cannot be used as a target language.
        st.button(
            "⇄",
            on_click=swap_languages,
            disabled=st.session_state.source_lang == AUTO_DETECT,
            help="Swap languages (choose a specific source language first)",
            use_container_width=True,
        )
    with target_col:
        st.selectbox("To", names, key="target_lang", format_func=format_language)


def render_input_panel() -> None:
    """Left column: the text box and the Translate button."""
    st.subheader("Enter text")
    st.text_area(
        "Text to translate",
        key="input_text",
        height=220,
        max_chars=MAX_CHARS,
        placeholder="Type or paste your text here...",
        label_visibility="collapsed",
    )
    st.button("Translate", type="primary", on_click=run_translation, use_container_width=True)


def render_output_panel() -> None:
    """Right column: the translation, copy button and text-to-speech."""
    state = st.session_state
    st.subheader("Translation")

    if not state.translation:
        st.info("Your translation will appear here.")
        return

    # st.code shows the text in a box with a built-in copy-to-clipboard button.
    st.code(state.translation, language=None, wrap_lines=True, height=220)
    st.caption(
        f"Translated to {format_language(state.translation_lang)} · "
        "use the copy icon in the top-right corner of the box to copy."
    )

    # Text-to-speech is offered only for languages that gTTS can speak.
    lang_code = get_translation_languages()[state.translation_lang]
    if lang_code in get_speech_languages():
        st.button("🔊 Listen", on_click=run_speech, use_container_width=True)
        if state.audio:
            st.audio(state.audio, format="audio/mp3")
    else:
        st.caption("Text-to-speech is not available for this language.")


def main() -> None:
    """Build the page from top to bottom."""
    st.set_page_config(page_title="Language Translation Tool", page_icon="🌐", layout="wide")
    init_session_state()

    render_header()
    render_language_selectors()

    input_col, output_col = st.columns(2, gap="large")
    with input_col:
        render_input_panel()
    with output_col:
        render_output_panel()

    # Errors from the last action (validation, network, API) are shown here.
    if st.session_state.error:
        st.error(st.session_state.error)

    st.divider()
    st.caption("Built with Streamlit, deep-translator and gTTS · CodeAlpha AI Internship, Task 1")


if __name__ == "__main__":
    main()
