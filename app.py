import streamlit as st
import os
import json
import time
import re
import tempfile
from openai import OpenAI, APIError
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
SHEET_ID = st.secrets["SHEET_ID"]

with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as f:
    f.write(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
    GOOGLE_SHEETS_CREDENTIALS_FILE = f.name

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

def export_to_google_sheets(data):
    try:
        creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        row = [data['date'], data['platform'], data['topic'], data['keywords'], data['content'].replace('\n',' ').strip(), data['model_used']]
        sheet = service.spreadsheets()
        result = sheet.values().append(
            spreadsheetId=SHEET_ID,
            range="Sheet1!A:F",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={'values':[row]}
        ).execute()
        return result.get('updates').get('updatedCells') > 0
    except Exception as e:
        st.error(f"Error exporting: {e}")
        return False

def generate_with_ai(prompt, model=DEFAULT_MODEL, max_retries=5):
    if not OPENROUTER_API_KEY:
        return "Error: API Key missing.", model
    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY,
                    default_headers={"X-Title": "Social Media AI Generator"})
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
        except APIError as e:
            if attempt==max_retries-1 and model!=FALLBACK_MODEL:
                return generate_with_ai(prompt, model=FALLBACK_MODEL, max_retries=1)
            time.sleep(2**attempt)
        except Exception as e:
            return f"Unexpected Error: {e}", model
    return "Failed to generate content.", model

st.set_page_config(page_title="🚀 AI Social Media Content Generator", layout="wide", initial_sidebar_state="expanded")

st.sidebar.title("⚙️ Settings")
theme = st.sidebar.selectbox("🌙 Theme", ["Light","Dark"])
brand_color = st.sidebar.color_picker("🎨 Brand Color","#6C63FF")
emoji_density = st.sidebar.slider("😎 Emoji Density (0-20)", 0, 20, 5)
font_size = st.sidebar.selectbox("🔤 Font Size", ["Small","Normal","Large"], index=1)
font_size_px = {"Small":12,"Normal":16,"Large":20}[font_size]
HASHTAG_COLOR = "#FFCC00"

dark_css = f"""
<style>
.stApp {{background-color:#0f1724 !important;color:#e6eef6 !important;}}
section[data-testid="stSidebar"] {{background-color:#0b0f1a !important;color:#e6eef6 !important;}}
button[aria-label="Toggle sidebar"] svg, button[title="Toggle sidebar"] svg {{fill:#e6eef6 !important;}}
h1,h2,h3,h4,h5,h6,.stMarkdown h1,.stMarkdown h2,.stMarkdown h3,.stMarkdown h4,.stMarkdown h5,.stMarkdown h6,.stHeader {{color:{brand_color} !important;font-weight:700 !important;}}
label, .stTextInput>label, .stTextArea>label, .stSelectbox>label, .stNumberInput>label {{color:#e6eef6 !important;font-weight:600;}}
.stButton>button {{background:linear-gradient(90deg,{brand_color},#4b4fb8) !important;color:white;}}
.stTextInput>div>input,.stTextArea textarea,.stSelectbox select,.stNumberInput input {{background-color:#0b0f1a;color:#e6eef6;border:1px solid rgba(255,255,255,0.04);font-size:{font_size_px}px !important;}}
.generated-content {{font-size:{font_size_px}px;color:#e6eef6 !important;}}
.generated-content span.hashtag {{color:{HASHTAG_COLOR};font-weight:700;}}
.stExpanderHeader {{color:{brand_color} !important; font-weight:600;}}
/* Saved posts expanders dark mode */
.stExpanderContent {{background-color:#0b0f1a !important;color:#e6eef6 !important;}}
.stExpanderContent p, .stExpanderContent span {{color:#e6eef6 !important;}}
</style>
"""

light_css = f"""
<style>
.stApp {{background-color:#ffffff !important;color:#111 !important;}}
h1,h2,h3,h4,h5,h6,.stMarkdown h1,.stMarkdown h2,.stMarkdown h3,.stMarkdown h4,.stMarkdown h5,.stMarkdown h6,.stHeader {{color:{brand_color} !important;font-weight:700 !important;}}
label, .stTextInput>label, .stTextArea>label, .stSelectbox>label, .stNumberInput>label {{color:#111 !important;font-weight:600;}}
.stButton>button {{background:linear-gradient(90deg,{brand_color},#4b4fb8) !important;color:white;}}
.stTextInput>div>input,.stTextArea textarea,.stSelectbox select,.stNumberInput input {{font-size:{font_size_px}px !important;}}
.generated-content {{font-size:{font_size_px}px;color:#111 !important;}}
.generated-content span.hashtag {{color:{HASHTAG_COLOR};font-weight:700;}}
.stExpanderHeader {{color:{brand_color} !important; font-weight:600;}}
</style>
"""

st.markdown(dark_css if theme=="Dark" else light_css, unsafe_allow_html=True)

if 'saved_posts' not in st.session_state:
    st.session_state.saved_posts = load_data()
if 'generated_posts' not in st.session_state:
    st.session_state.generated_posts = []

tab1,tab2 = st.tabs(["✍️ Generate Content","💾 Saved Posts"])

with tab1:
    st.header("💡 Generate Social Media Posts")
    col1,col2 = st.columns(2)
    with col1:
        platform = st.selectbox("🌐 Target Platform", ["LinkedIn (Professional)","X (Twitter)","Instagram Caption","Facebook (Community)"])
        topic = st.text_input("✏️ Main Topic/Subject", placeholder="e.g., Future of Remote Work")
        tone = st.selectbox("🎨 Tone/Style", ["Informative","Witty","Inspirational","Data-Driven","Motivational","Friendly","Bold","Luxury"], index=0)
    with col2:
        keywords = st.text_input("🏷️ Keywords/Hashtags", placeholder="e.g., productivity, hybrid work, #remotefirst")
        batch_count = st.number_input("📝 Number of Posts (Batch Generation)", min_value=1, max_value=10, value=1)
        custom_emoji_density = st.number_input("🎭 Exact Emoji Count per Post (Optional)", min_value=0, max_value=50, value=emoji_density)

    full_prompt = f"Generate a social media post for {platform} on '{topic}'. Include keywords/hashtags: {keywords}. Tone: {tone}. Use exactly {custom_emoji_density} emojis. Highlight important points with <b style='color:#FF5733'>bold colored text</b> and make it engaging."

    st.markdown("---")
    if st.button("🚀 Generate Post(s)", type="primary", use_container_width=True):
        if not topic:
            st.error("Please enter a topic.")
        else:
            st.session_state.generated_posts = []
            with st.spinner(f"Generating {batch_count} post(s)..."):
                for i in range(batch_count):
                    if i>0: time.sleep(1)
                    content, model_used = generate_with_ai(full_prompt)
                    st.session_state.generated_posts.append({"content":content,"model_used":model_used})
                st.rerun()

    for idx, post in enumerate(st.session_state.generated_posts,1):
        content_with_hashtags = re.sub(r"(#[A-Za-z0-9_]+)", r'<span class="hashtag">\1</span>', post['content'])
        st.subheader(f"📝 Generated Post {idx}")
        st.markdown(f"<div class='generated-content' style='margin-bottom:20px;padding:15px;border:1px solid {brand_color};border-radius:8px;'>{content_with_hashtags}</div>", unsafe_allow_html=True)
        col_btn1,col_btn2 = st.columns(2)
        if col_btn1.button(f"💾 Save Post {idx}", key=f"save_btn_{idx}", use_container_width=True):
            new_post = {"date":time.strftime("%Y-%m-%d %H:%M:%S"),"platform":platform,"topic":topic,"keywords":keywords,"content":post['content'],"model_used":post['model_used']}
            st.session_state.saved_posts.insert(0,new_post)
            save_data(st.session_state.saved_posts)
            st.success(f"Post {idx} saved!")
        if col_btn2.button(f"📤 Export Post {idx}", key=f"export_btn_{idx}", use_container_width=True):
            post_to_export = {"date":time.strftime("%Y-%m-%d %H:%M:%S"),"platform":platform,"topic":topic,"keywords":keywords,"content":post['content'],"model_used":post['model_used']}
            if export_to_google_sheets(post_to_export): st.success(f"Post {idx} exported!")

with tab2:
    st.header("💾 Saved Posts")
    if not st.session_state.saved_posts:
        st.info("No posts saved yet.")
    else:
        for i, post in enumerate(st.session_state.saved_posts):
            with st.expander(f"{post['platform']} | {post['topic']} | {post['date']}"):
                st.markdown(f"**Topic:** {post['topic']}")
                st.markdown(f"**Keywords:** {post['keywords']}")
                st.markdown(f"**Model:** {post['model_used']}")
                st.markdown("---")
                st.markdown(f"<div style='font-size:{font_size_px}px;color:#e6eef6;'>{post['content']}</div>", unsafe_allow_html=True)
                if st.button(f"❌ Delete Post {i+1}", key=f"del_{i}", type="secondary"):
                    st.session_state.saved_posts.pop(i)
                    save_data(st.session_state.saved_posts)
                    st.rerun()
        st.markdown("---")
        if st.button("🗑️ Clear All Saved Posts", type="secondary"):
            st.session_state.saved_posts = []
            save_data(st.session_state.saved_posts)
            st.success("All cleared!")
            st.rerun()
