import os
import json
import streamlit as st
import pandas as pd
import openai
import pdfplumber
from dotenv import load_dotenv

import cohere


# Load environment variables from .env file
load_dotenv()

# Access your API key
openai_api_key = os.getenv('OPENAI_API_KEY')
cohere_api_key = os.getenv('COHERE_API_KEY')

# Ensure the API key is set for the OpenAI library
openai.api_key = openai_api_key
co = cohere.Client(cohere_api_key)


def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"  # Adding a newline for page separation
    return text


def identify_questions(text):
    response = openai.chat.completions.create(
        model="gpt-4-0125-preview",
        temperature=0.1,
        messages=[
            {"role": "system", "content": "Identify and list all the questions in the following text:"},
            {"role": "user", "content": text},
        ]
    )
    print(response.choices[0].message.content.strip())

    return response.choices[0].message.content.strip()


def extract_artifacts(text):
    response = openai.chat.completions.create(
        model="gpt-4-0125-preview",
        temperature=0.1,
        messages=[
            {"role": "system",
                "content": "You are an RFP response writer. You look at RFPs with great detail. Extract all mentions of figures, tables, and required artifacts, with their specific sections in the following text. ONLY return the extracted artifacts (no other text is necessary)."},
            {"role": "user", "content": text},
        ]
    )
    print(response.choices[0].message.content.strip())

    return response.choices[0].message.content.strip()


def flag_keywords(text, keywords):
    flagged_items = []
    for keyword in keywords:
        if keyword.lower() in text.lower():
            # flagged_items.append(keyword)
            # append the sentence from text that contains the keyword, split at all sentence ending
            for sentence in text.split("."):
                if keyword.lower() in sentence.lower():
                    flagged_items.append(sentence.strip())

    return flagged_items


def generate_report(questions, artifacts, flagged_keywords):
    # Create DataFrames for each category
    questions_df = pd.DataFrame({
        "Questions": [questions]
    }).style.set_properties(**{'text-align': 'left', 'white-space': 'pre-wrap', 'height': '500px', 'width': '100%'})

    artifacts_df = pd.DataFrame({
        "Artifacts": [artifacts]
    }).style.set_properties(**{'text-align': 'left', 'white-space': 'pre-wrap', 'height': '500px', 'width': '100%'})

    keywords_df = pd.DataFrame({
        "Flagged Keywords": [', '.join(flagged_keywords)]
    }).style.set_properties(**{'text-align': 'left', 'white-space': 'pre-wrap', 'height': '500px', 'width': '100%'})

    return questions_df, artifacts_df, keywords_df


def sample_rag_with_cohere(document_text):
    print("sending msg to cohere API")
    response = co.chat(
        model="command-r-plus",
        message='''You are an expert RFP writer. You receive RFPs all day long. Your current task is to extract all the "questions" that we need to give an answer to in this document. Respond with a JSON object only. Example response:~~~{questions:[{idx: 1, question: "Please answer the questions asked in this bid event, including any file attachment uploads. Certain questions will require an answer in order to submit your response, while other questions are optional when they pertain to your company. Some questions require a specific answer which will be identified to you. You will be warned of disqualification if you answer with an unacceptable answer prior to submission."}, {idx:2:, question:"..."}, ...]}~~~
        ONLY return a valid JSON object (no other text is necessary), do not identify it as json, just return the object.''',
        documents=[
            {"text": document_text}
        ],
        temperature=0
    )

    return response.text


def parse_json_from_markdown(json_markdown):
    print("[+] Parsing JSON from Markdown...")
    # Strip the Markdown code block syntax to isolate the JSON string
    json_string = json_markdown.strip('```json')
    # Make sure to remove any leading or trailing whitespace
    json_string = json_string.strip()
    # Make sure json string is enclosed in curly braces
    if not json_string.startswith("{"):
        json_string = "{" + json_string

    # FIX THIS LATER
    if not json_string.endswith('"/}]/}'):
        json_string = json_string + '"/}]/}'

    # parsed_json = json.loads(json_string)
    # print("json string", json_string)
    return json_markdown
    # return parsed_json


def main():
    st.title("RFP Analysis Tool")

    # Manage button state
    if 'button_clicked' not in st.session_state:
        st.session_state.button_clicked = False

    use_sample_text = st.checkbox("Use sample text for analysis")

    uploaded_file = None
    if not use_sample_text:
        uploaded_file = st.file_uploader(
            "Upload your RFP document", type=["pdf"])

    keywords = st.text_input(
        "Enter keywords to flag, separated by commas").split(',')

    analyze_button = st.button(
        "Analyze", disabled=st.session_state.button_clicked)

    if analyze_button:
        st.session_state.button_clicked = True
        text_for_analysis = ""
        if use_sample_text:
            text_for_analysis = "Define your sample text here..."
        elif uploaded_file is not None:
            text_for_analysis = extract_text_from_pdf(uploaded_file)

        if text_for_analysis:
            questions = sample_rag_with_cohere(text_for_analysis)
            artifacts = extract_artifacts(text_for_analysis)
            flagged_keywords = flag_keywords(text_for_analysis, keywords)
            questions_df, artifacts_df, keywords_df = generate_report(
                questions, artifacts, flagged_keywords)
            st.write("Questions")
            st.dataframe(questions_df)

            st.write("Artifacts")
            st.dataframe(artifacts_df)

            st.write("Flagged Keywords")
            st.dataframe(keywords_df)

        st.session_state.button_clicked = False


if __name__ == "__main__":
    main()
