# CodeAlpha_LanguageTranslator

A simple language translation web app built with Python and Streamlit.
Created for **Task 1 (Language Translation Tool)** of the CodeAlpha Artificial Intelligence internship.

## Description

The user types or pastes text, picks a source and a target language, and the app sends the text to
Google Translate and shows the translated result. The translation can be copied with one click or
played aloud. Translation goes through the [deep-translator](https://pypi.org/project/deep-translator/)
library, so no API key or billing account is required.

## Features

- Translate between 130+ languages
- **Auto-detect** option for the source language
- **Swap** button to switch source and target languages (the translation moves into the input box)
- **Copy** button on the translated text
- **Text-to-speech**: listen to the translation in the app (for languages supported by gTTS)
- **Backup translation service**: if Google Translate fails (for example when it rate-limits
  your network), the app automatically retries with MyMemory, and a caption under the result
  shows which service produced the translation
- **Offline language detection**: when the backup service is used with Auto-detect, the source
  language is detected on your computer with langdetect and shown in the caption
  (e.g. "Detected: French · via MyMemory")
- Two-column layout: input on the left, translation on the right
- Friendly error messages for empty input, identical languages, no internet connection,
  unsupported languages, rate limits and other API failures

## Screenshot

<!-- Replace the line below with a real screenshot, e.g. save it as screenshots/app.png -->
![App screenshot](screenshots/app.png)

## Tech stack

| Purpose        | Library                               |
| -------------- | ------------------------------------- |
| User interface | Streamlit                             |
| Translation    | deep-translator (`GoogleTranslator`)  |
| Backup translation | deep-translator (`MyMemoryTranslator`) |
| Offline language detection | langdetect                |
| Text-to-speech | gTTS                                  |

## Setup

Requires Python 3.10 or newer.

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/CodeAlpha_LanguageTranslator.git
cd CodeAlpha_LanguageTranslator

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 3. Install the dependencies
pip install -r requirements.txt
```

## How to run

```bash
streamlit run app.py
```

The app opens in your browser at http://localhost:8501.

## How to use

1. Choose the source language (or leave it on **Auto-detect**) and the target language.
2. Type or paste your text (up to 5000 characters).
3. Click **Translate**.
4. Use the copy icon on the result box to copy the translation, or click **Listen** to hear it.

## Project structure

```
CodeAlpha_LanguageTranslator/
├── app.py             # the whole application
├── requirements.txt   # Python dependencies
├── .gitignore
└── README.md
```

## Notes

- An internet connection is required for translation and text-to-speech.
- The app uses Google's free public endpoints, which are rate limited. When Google refuses a
  request, the app falls back to [MyMemory](https://mymemory.translated.net/), which is also free
  and needs no API key.

### Limits of the backup service (MyMemory)

MyMemory is only used when Google Translate fails, and it is more limited:

- **Text length**: fewer than 500 characters per translation. Longer text shows a message
  explaining the limit.
- **No built-in auto-detect**: with **Auto-detect** selected, the app detects the language locally
  with langdetect. Detection is only trusted for text of at least 20 characters with a confidence
  of 90% or more; otherwise the app asks you to pick the source language in the "From" list.
- **Fewer languages**: a few languages Google offers (e.g. Corsican) are not available.
- **Quality**: MyMemory is a translation memory, so results, especially for short phrases, can be
  less accurate than Google's.
- **Daily quota**: free use is limited per day.
