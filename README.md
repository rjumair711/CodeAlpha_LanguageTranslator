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
- The app uses Google's free public endpoints, which are rate limited. If you see a
  "Too many requests" message, wait a while or try a different network.
