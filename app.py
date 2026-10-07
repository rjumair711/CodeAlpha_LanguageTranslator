"""
Language Translation Tool
CodeAlpha AI Internship - Task 1

A Streamlit app that translates text between languages using Google Translate
(through the deep-translator library, so no API key is needed) and can read
the translation aloud with gTTS. If Google Translate is unavailable, the app
falls back to the MyMemory service, detecting the source language offline
with langdetect when "Auto-detect" is selected.

Run with:  streamlit run app.py
"""

from dataclasses import dataclass
from io import BytesIO

import requests
import streamlit as st
from deep_translator import GoogleTranslator, MyMemoryTranslator
from deep_translator.exceptions import (
    InvalidSourceOrTargetLanguage,
    LanguageNotSupportedException,
    NotValidLength,
    NotValidPayload,
    TooManyRequests,
)
from gtts import gTTS
from gtts.lang import tts_langs
from gtts.tts import gTTSError
from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
AUTO_DETECT = "Auto-detect"   # label of the extra option in the source list
MAX_CHARS = 5000              # Google Translate's limit for a single request
DEFAULT_TARGET = "english"

GOOGLE = "Google Translate"   # primary translation service
MYMEMORY = "MyMemory"         # backup service, used only when Google fails
FALLBACK_MAX_CHARS = 499      # MyMemory's limit: deep-translator rejects 500 characters or more

# MyMemory names a few languages differently from Google. This maps the
# Google name (used in the dropdowns) to the MyMemory name.
MYMEMORY_NAME_ALIASES = {
    "chinese (simplified)": "chinese simplified",
    "chinese (traditional)": "chinese traditional",
    "haitian creole": "haitian creole french",
    "irish": "irish gaelic",
    "kurdish (kurmanji)": "northern kurdish",
    "kurdish (sorani)": "kurdish sorani",
    "myanmar": "burmese",
    "norwegian": "norwegian bokmål",
    "odia (oriya)": "odia",
    "serbian": "serbian cyrillic",
    "tamil": "tamil india",
}


# Offline language detection (langdetect), used when the source is
# "Auto-detect" and the backup service has to be used.
DetectorFactory.seed = 0      # langdetect is random by default; this makes it repeatable
MIN_DETECT_CHARS = 20         # shorter texts are often detected wrongly
MIN_DETECT_CONFIDENCE = 0.90  # minimum probability to trust the detected language
# langdetect writes three codes differently from Google.
LANGDETECT_CODE_ALIASES = {"he": "iw", "zh-cn": "zh-CN", "zh-tw": "zh-TW"}


@dataclass
class TranslationResult:
    """What translate_text() returns."""

    text: str                            # the translated text
    service: str                         # GOOGLE or MYMEMORY
    detected_language: str | None = None  # set only when we detected the source locally


class TranslationError(Exception):
    """Raised with a user-friendly message when a translation cannot be done."""


class ServiceUnavailable(Exception):
    """Raised when Google Translate itself fails, so the backup should be tried.

    `offline` is True when the failure looks like a missing internet connection.
    """

    def __init__(self, message: str, offline: bool = False):
        super().__init__(message)
        self.offline = offline


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


@st.cache_data
def get_fallback_languages() -> set[str]:
    """Return the language names the backup service (MyMemory) supports."""
    translator = MyMemoryTranslator(source="english", target="french")
    return set(translator.get_supported_languages())


def to_fallback_language(name: str) -> str | None:
    """Convert a Google language name to MyMemory's name, or None if unsupported."""
    name = MYMEMORY_NAME_ALIASES.get(name, name)
    return name if name in get_fallback_languages() else None


def detect_language(text: str) -> str | None:
    """Detect the language of `text` offline with langdetect.

    Returns the language name used in the dropdowns (e.g. "french"), or None
    when the result cannot be trusted: the text is too short, langdetect is
    not confident enough, or it found a language Google does not list.
    """
    if len(text) < MIN_DETECT_CHARS:
        return None
    try:
        best_guess = detect_langs(text)[0]  # guesses are sorted, most likely first
    except LangDetectException:  # e.g. the text contains only digits or symbols
        return None
    if best_guess.prob < MIN_DETECT_CONFIDENCE:
        return None

    code = LANGDETECT_CODE_ALIASES.get(best_guess.lang, best_guess.lang)
    code_to_name = {code: name for name, code in get_translation_languages().items()}
    return code_to_name.get(code)


def format_language(name: str) -> str:
    """Turn an internal language name into a display label ("french" -> "French")."""
    return name if name == AUTO_DETECT else name.title()


# ----------------------------------------------------------------------------
# Core logic: translation and text-to-speech
# ----------------------------------------------------------------------------
def translate_with_google(text: str, source_name: str, target_name: str) -> str:
    """Translate with Google Translate (the primary service).

    Problems with the input itself raise TranslationError. Problems with the
    service (rate limit, no connection, server error) raise ServiceUnavailable,
    which tells the caller that the backup service is worth trying.
    """
    languages = get_translation_languages()
    source_code = "auto" if source_name == AUTO_DETECT else languages[source_name]
    target_code = languages[target_name]

    try:
        result = GoogleTranslator(source=source_code, target=target_code).translate(text)
    except (LanguageNotSupportedException, InvalidSourceOrTargetLanguage):
        raise TranslationError("That language is not supported. Please pick another one.")
    except NotValidLength:
        raise TranslationError(f"The text is too long. Please keep it under {MAX_CHARS} characters.")
    except NotValidPayload:
        raise TranslationError("The text could not be read. Please enter plain text.")
    except TooManyRequests:
        raise ServiceUnavailable(f"{GOOGLE} is temporarily blocking requests from this network (too many requests).")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise ServiceUnavailable(f"{GOOGLE} could not be reached.", offline=True)
    except Exception:  # RequestError, TranslationNotFound, or anything unexpected
        raise ServiceUnavailable(f"{GOOGLE} returned an error.")

    if not result:
        raise ServiceUnavailable(f"{GOOGLE} returned no translation.")
    return result


def translate_with_mymemory(text: str, source_name: str, target_name: str) -> str:
    """Translate with MyMemory (the backup service). Raises TranslationError on failure."""
    try:
        result = MyMemoryTranslator(source=source_name, target=target_name).translate(text)
    except TooManyRequests:
        raise TranslationError(f"{MYMEMORY} has reached its free daily limit. Please try again later.")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise TranslationError(f"{MYMEMORY} could not be reached.")
    except Exception:  # RequestError, no matches found, or anything unexpected
        raise TranslationError(f"{MYMEMORY} could not translate this text.")

    # MyMemory reports an exhausted quota inside the translated text itself.
    if not result or result.upper().startswith("MYMEMORY WARNING"):
        raise TranslationError(f"{MYMEMORY} could not translate this text right now.")
    return result


def translate_text(text: str, source_name: str, target_name: str) -> TranslationResult:
    """Translate `text` and return the translation plus how it was produced.

    Google Translate is always tried first. Only if Google itself is
    unavailable do we fall back to MyMemory, which has three extra limits:
    no auto-detect (we detect the language locally with langdetect instead),
    at most 500 characters, and a smaller language list.
    Every failure ends up as a TranslationError with a readable message,
    so the UI only has to handle one exception type.
    """
    try:
        return TranslationResult(translate_with_google(text, source_name, target_name), GOOGLE)
    except ServiceUnavailable as error:
        google_problem = str(error)
        offline = error.offline

    # --- Google failed: check whether the backup service can take this request ---
    detected_name = None
    if source_name == AUTO_DETECT:
        # MyMemory needs an explicit source language, so detect it on this computer.
        detected_name = detect_language(text)
        if detected_name is None:
            raise TranslationError(
                f"{google_problem} The backup service ({MYMEMORY}) cannot auto-detect languages, "
                "and the language could not be detected reliably from this text (it may be too short) - "
                "please choose the source language in the 'From' list and translate again."
            )
        if detected_name == target_name:
            raise TranslationError(
                f"The text appears to already be in {format_language(target_name)}. "
                "Please choose a different target language, or pick the source language in the 'From' list."
            )
        source_name = detected_name
    if len(text) > FALLBACK_MAX_CHARS:
        raise TranslationError(
            f"{google_problem} The backup service ({MYMEMORY}) only accepts up to "
            f"{FALLBACK_MAX_CHARS} characters, and your text has {len(text)}. "
            "Please shorten it or translate it in smaller parts."
        )
    fallback_source = to_fallback_language(source_name)
    fallback_target = to_fallback_language(target_name)
    if not fallback_source or not fallback_target:
        unsupported = source_name if not fallback_source else target_name
        raise TranslationError(
            f"{google_problem} The backup service ({MYMEMORY}) does not support "
            f"{format_language(unsupported)}. Please try again later."
        )

    try:
        translation = translate_with_mymemory(text, fallback_source, fallback_target)
        return TranslationResult(translation, MYMEMORY, detected_name)
    except TranslationError as error:
        if offline:
            raise TranslationError("Could not reach the translation services. Please check your internet connection.")
        raise TranslationError(f"{google_problem} The backup service also failed: {error}")


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
        "translation_service": "",  # service that produced it (Google or MyMemory)
        "detected_lang": "",     # source language detected locally (fallback + Auto-detect)
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
    st.session_state.translation_service = ""
    st.session_state.detected_lang = ""
    st.session_state.audio = None
    st.session_state.error = ""


def run_translation() -> None:
    """Validate the input, call the API and store the result in session state."""
    state = st.session_state
    text = state.input_text.strip()
    clear_result()

    # --- validation before calling the API ---
    if not text:
        state.error = "Please enter some text to translate."
        return
    if state.source_lang == state.target_lang:
        state.error = "Source and target languages are the same. Please choose different languages."
        return

    try:
        result = translate_text(text, state.source_lang, state.target_lang)
        state.translation = result.text
        state.translation_service = result.service
        state.detected_lang = result.detected_language or ""
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
    if state.detected_lang:
        st.caption(
            f"Detected: {format_language(state.detected_lang)} · via {MYMEMORY} "
            f"(backup service - {GOOGLE} was unavailable)."
        )
    elif state.translation_service == MYMEMORY:
        st.caption(f"Translated by {MYMEMORY} (backup service - {GOOGLE} was unavailable).")
    else:
        st.caption(f"Translated by {state.translation_service}.")

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
