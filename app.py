import streamlit as st
import os
import json
import time
import re
import tempfile
import html
from openai import OpenAI, APIError
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

st.set_page_config(page_title="🚀 AI Social Media Content Generator", layout="wide", initial_sidebar_state="expanded")

OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
SHEET_ID = st.secrets["SHEET_ID"]

GOOGLE_SHEETS_CREDENTIALS_FILE = None
credentials_dict = None

try:
    credentials_string = st.secrets["GOOGLE_SHEETS_CREDENTIALS"]
    cleaned_credentials_string = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', credentials_string)
    credentials_dict = json.loads(cleaned_credentials_string)
    if 'private_key' in credentials_dict and isinstance(credentials_dict['private_key'], str):
        pk = credentials_dict['private_key']
        pk_fixed = pk.replace('\\n', '\n')
        pk_fixed = pk_fixed.replace('-----BEGIN PRIVATE KEY-----', '-----BEGIN PRIVATE KEY-----\n')
        pk_fixed = pk_fixed.replace('-----END PRIVATE KEY-----', '\n-----END PRIVATE KEY-----')
        pk_fixed = re.sub(r'\n+', '\n', pk_fixed).strip()
        if not pk_fixed.endswith('\n'):
             pk_fixed += '\n'
        credentials_dict['private_key'] = pk_fixed
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as f:
        json.dump(credentials_dict, f, indent=4)
        GOOGLE_SHEETS_CREDENTIALS_FILE = f.name
except:
    GOOGLE_SHEETS_CREDENTIALS_FILE = None

DEFAULT_MODEL = "google/gemini-2.5-flash"
FALLBACK_MODEL = "openai/gpt-4o-mini"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DATA_STORE = "saved_posts.json"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def load_data():
    if os.path.exists(DATA_STORE):
        try:
            with open(DATA_STORE, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except:
            return []
    return []

def save_data(data):
    with open(DATA_STORE, 'w') as f:
        json.dump(data, f, indent=4)

def clean_text_for_sheets(text):
    text = re.sub(r'<[^>]*>', '', text)
    text = html.unescape(text)
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    cleaned_text = ''.join(char for char in text if ord(char) >= 32 and ord(char) != 127)
    return cleaned_text.strip()

def export_to_google_sheets(data):
    if GOOGLE_SHEETS_CREDENTIALS_FILE is None:
        st.error("Cannot export. Google Sheets credentials failed to load or were malformed.")
        return False
    try:
        creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        cleaned_content = clean_text_for_sheets(data['content'])
        row = [
            data['date'],
            data['platform'],
            data['topic'],
            data['keywords'],
            cleaned_content,
            data['model_used']
        ]
        sheet = service.spreadsheets()
        result = sheet.values().append(
            spreadsheetId=SHEET_ID,
            range="Sheet1!A:F",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={'values':[row]}
        ).execute()
        updates = result.get('updates')
        if updates and updates.get('updatedCells') > 0:
            return True
        else:
            return False
    except:
        return False

def generate_with_ai(prompt, model=DEFAULT_MODEL, max_retries=5):
    if not OPENROUTER_API_KEY:
        return "Error: API Key missing.", model
    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY, default_headers={"X-Title": "Social Media AI Generator"})
    system_instruction = (
        "You are a professional social media content specialist. "
        "Generate posts that are engaging, clear, and ready for posting. "
        "Use emojis naturally. Highlight important points with <b style='color:#FF5733'>bold colored text</b>."
    )
    messages = [{"role": "system", "content": system_instruction},{"role":"user","content":prompt}]
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(model=model, messages=messages, temperature=0.7, max_tokens=2000)
            return response.choices[0].message.content, model
        except APIError:
            if attempt==max_retries-1 and model!=FALLBACK_MODEL:
                return generate_with_ai(prompt, model=FALLBACK_MODEL, max_retries=1)
            time.sleep(2**attempt)
        except Exception as e:
            return f"Unexpected Error: {e}", model
    return "Failed to generate content.", model

st.sidebar.title("⚙️ Settings")
theme = st.sidebar.selectbox("🌙 Theme", ["Light","Dark"])
brand_color = st.sidebar.color_picker("🎨 Brand Color","#6C63FF")
emoji_density = st.sidebar.slider("😎 Emoji Density (0-20)", 0, 20, 5)
font_size = st.sidebar.selectbox("🔤 Font Size", ["Small","Normal","Large"], index=1)
font_size_px = {"Small":13,"Normal":16,"Large":20}[font_size]
font_style = st.sidebar.selectbox("🖋️ Generated Content Font", ["Arial","Helvetica","Times New Roman","Courier New","Verdana"], index=0)
hashtag_font_style = st.sidebar.selectbox("🏷️ Hashtag Font", ["Arial","Helvetica","Times New Roman","Courier New","Verdana"], index=0)
HASHTAG_COLOR = "#FFCC00"

dark_css = f"""
<style>
:root {{
    --brand-color: {brand_color};
    --app-font-size: {font_size_px}px;
    --generated-font-style: '{font_style}', sans-serif;
    --hashtag-font-style: '{hashtag_font_style}', sans-serif;
    --hashtag-color: {HASHTAG_COLOR};
}}
.stApp {{
    background-color:#0f1724 !important;
    color:#e6eef6 !important;
}}
section[data-testid="stSidebar"] {{
    background-color:#0b0f1a !important;
    color:#e6eef6 !important;
}}
button[aria-label="Toggle sidebar"] svg, button[title="Toggle sidebar"] svg {{
    fill:#e6eef6 !important;
}}
h1,h2,h3,h4,h5,h6,
.stMarkdown h1,.stMarkdown h2,.stMarkdown h3,
.stMarkdown h4,.stMarkdown h5,.stMarkdown h6 {{
    color:var(--brand-color) !important;
    font-weight:700 !important;
}}
.stTabs [data-baseweb="tab"] {{
    color: var(--brand-color) !important;
    font-weight: 700 !important;
}}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{
    color: var(--brand-color) !important;
    border-bottom: 2px solid var(--brand-color) !important;
}}
label {{
    color:#e6eef6 !important;
    font-weight:600;
}}
.stButton>button {{
    background:linear-gradient(90deg,var(--brand-color),#4b4fb8) !important;
    color:white !important;
}}
.generated-content,
.generated-content * {{
    font-size: var(--app-font-size) !important;
    color:#e6eef6 !important;
    line-height:1.55 !important;
    font-family: var(--generated-font-style) !important;
}}
.generated-content span.hashtag {{
    color:var(--hashtag-color) !important;
    font-weight:700 !important;
    font-family: var(--hashtag-font-style) !important;
}}
.stExpanderHeader {{
    color:var(--brand-color) !important;
    font-weight:700 !important;
}}
.stExpanderContent {{
    background: rgba(255,255,255,0.03) !important;
    color:#e6eef6 !important;
    border:1px solid rgba(255,255,255,0.05) !important;
    padding:12px !important;
    border-radius:8px !important;
}}
</style>
"""

light_css = f"""
<style>
:root {{
    --brand-color: {brand_color};
    --app-font-size: {font_size_px}px;
    --generated-font-style: '{font_style}', sans-serif;
    --hashtag-font-style: '{hashtag_font_style}', sans-serif;
    --hashtag-color: {HASHTAG_COLOR};
}}
.generated-content,
.generated-content * {{
    font-size: var(--app-font-size) !important;
    font-family: var(--generated-font-style) !important;
}}
.generated-content span.hashtag {{
    font-family: var(--hashtag-font-style) !important;
}}
</style>
"""

st.markdown(dark_css if theme == "Dark" else light_css, unsafe_allow_html=True)

if 'saved_posts' not in st.session_state:
    st.session_state.saved_posts = load_data()
if 'generated_posts' not in st.session_state:
    st.session_state.generated_posts = []

tab1, tab2 = st.tabs(["✍️ Generate Content", "💾 Saved Posts"])

with tab1:
    st.header("💡 Generate Social Media Posts")
    col1, col2 = st.columns(2)
    with col1:
        platform = st.selectbox("🌐 Target Platform", ["LinkedIn (Professional)", "X (Twitter)", "Instagram Caption", "Facebook (Community)"])
        topic = st.text_input("✏️ Main Topic/Subject")
        tone = st.selectbox("🎨 Tone/Style", ["Informative", "Witty", "Inspirational", "Data-Driven", "Motivational", "Friendly", "Bold", "Luxury"])
    with col2:
        keywords = st.text_input("🏷️ Keywords/Hashtags")
        batch_count = st.number_input("📝 Number of Posts", min_value=1, max_value=10, value=1)
        custom_emoji_density = st.number_input("🎭 Exact Emoji Count", min_value=0, max_value=50, value=emoji_density)

    full_prompt = f"Generate a social media post for {platform} on '{topic}'. Include keywords/hashtags: {keywords}. Tone: {tone}. Use exactly {custom_emoji_density} emojis. Highlight important points with <b style='color:#FF5733'>bold colored text</b>."
    st.markdown("---")
    if st.button("🚀 Generate Post(s)", type="primary", use_container_width=True):
        if not topic:
            st.error("Please enter a topic.")
        else:
            st.session_state.generated_posts = []
            with st.spinner(f"Generating {batch_count} post(s)..."):
                for i in range(batch_count):
                    if i > 0:
                        time.sleep(1)
                    content, model_used = generate_with_ai(full_prompt)
                    st.session_state.generated_posts.append({"content": content, "model_used": model_used})
                st.rerun()

    for idx, post in enumerate(st.session_state.generated_posts, 1):
        content_with_hashtags = re.sub(r"(#[A-Za-z0-9_]+)", r'<span class="hashtag">\1</span>', post['content'])
        st.subheader(f"📝 Generated Post {idx}")
        st.markdown(f"<div class='generated-content' style='padding:15px;border:1px solid {brand_color};border-radius:8px;margin-bottom:20px;'>{content_with_hashtags}</div>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        if col1.button(f"💾 Save {idx}", key=f"save_{idx}", use_container_width=True):
            new_post = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "platform": platform, "topic": topic, "keywords": keywords, "content": post['content'], "model_used": post['model_used']}
            st.session_state.saved_posts.insert(0, new_post)
            save_data(st.session_state.saved_posts)
            st.success("Saved!")

        if col2.button(f"📤 Export {idx}", key=f"export_{idx}", use_container_width=True):
            post_to_export = {"date": time.strftime("%Y-%m-%d %H:%M:%S"), "platform": platform, "topic": topic, "keywords": keywords, "content": post['content'], "model_used": post['model_used']}
            success = export_to_google_sheets(post_to_export)
            if success:
                st.success("✅ Exported to Google Sheets!")
            else:
                st.error("❌ Export failed. Check credentials or sheet permissions.")

with tab2:
    st.header("💾 Saved Posts")
    if not st.session_state.saved_posts:
        st.info("No posts saved.")
    else:
        for i, post in enumerate(st.session_state.saved_posts):
            with st.expander(f"{post['platform']} | {post['topic']} | {post['date']}"):
                st.markdown(f"<div class='saved-post-meta'><strong>{post['topic']}</strong></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='saved-post-meta'>Keywords: <strong>{post['keywords']}</strong> | Model: <strong>{post['model_used']}</strong></div>", unsafe_allow_html=True)
                st.markdown("---")
                safe = post['content'].replace("\n","<br>")
                st.markdown(f"<div class='saved-post-content'>{safe}</div>", unsafe_allow_html=True)

                if st.button(f"❌ Delete {i+1}", key=f"del_{i}", type="secondary"):
                    st.session_state.saved_posts.pop(i)
                    save_data(st.session_state.saved_posts)
                    st.rerun()

        st.markdown("---")
        if st.button("🗑️ Clear All", type="secondary"):
            st.session_state.saved_posts = []
            save_data(st.session_state.saved_posts)
            st.rerun()
