import contextlib
import streamlit as st
import html
import time
import socket
from pathlib import Path

from email_service import SMTPClient, MessageBuilder
from email_service.smtp_client import SMTPClientError
from email_service.message_builder import EmailRecipients, Attachment, MessageBuilderError
from utils.validators import parse_email_input, is_valid_email, sanitize_email_input
from utils.config import (
    TEMPLATES_DIR,
    validate_attachment_size,
    validate_attachment_type,
    MAX_ATTACHMENT_SIZE_MB,
    ATTACH_DIR,
    DEFAULT_CONTENT
)


@st.cache_data(ttl=3600)
def get_credentials() -> tuple[str, str]:
    """
    Get Gmail credentials from Streamlit secrets.
    
    For local development: Create .streamlit/secrets.toml
    For Streamlit Cloud: Add secrets in app settings
    
    Returns:
        tuple: (sender_email, app_password)
    """
    try:
        sender_email = st.secrets.gmail.sender_email
        app_password = st.secrets.gmail.app_password
        return sender_email, app_password
    except (KeyError, AttributeError, FileNotFoundError):
        try:
            from sender_config import SENDER_EMAIL, APP_PASSWORD
            return SENDER_EMAIL, APP_PASSWORD
        except ImportError:
            return "", ""


st.set_page_config(
    page_title="GDG Email Dashboard",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_available_templates() -> list[str]:
    templates = []
    if TEMPLATES_DIR.exists():
        templates = [f.stem for f in TEMPLATES_DIR.iterdir() 
                     if f.is_file() and f.suffix == ".html" and f.name != "content.html"]
    return sorted(templates) if templates else ["base"]


def get_template_path(template_name: str) -> Path:
    template_path = TEMPLATES_DIR / f"{template_name}.html"
    if template_path.exists():
        return template_path
    raise FileNotFoundError(f"Template '{template_name}' not found")


def inject_custom_css():
    st.markdown("""
    <style>
        /* === GOOGLE FONTS === */
        @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=Roboto:wght@400;500;700&display=swap');
        
        * {
            font-family: 'Google Sans', 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        
        /* === DARK NAVY BASE (Cloud Skills Boost Style) === */
        .stApp {
            background: linear-gradient(180deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
            min-height: 100vh;
        }
        
        /* === SIDEBAR STYLING (White Background with Light Theme) === */
        [data-testid="stSidebar"] {
            background: #ffffff !important;
            border-right: 1px solid #e1e4e8;
        }
        
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 2rem;
        }
        
        /* Hide collapse button to prevent sidebar from being collapsed */
        [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"] {
            display: none !important;
            visibility: hidden !important;
        }
        
        /* === SIDEBAR LIGHT THEME === */
        /* Set base theme variables for sidebar */
        [data-testid="stSidebar"] {
            --text-color: #1a1a1a;
            --secondary-text-color: #57606a;
            --background-color: #ffffff;
            --secondary-background-color: #f6f8fa;
            --border-color: #d0d7de;
        }
        
        /* Base text color for all elements */
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stMarkdown strong,
        section[data-testid="stSidebar"] .stMarkdown span,
        section[data-testid="stSidebar"] .stCaption {
            color: #1a1a1a !important;
        }
        
        /* Input fields - including disabled state */
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] input:disabled,
        section[data-testid="stSidebar"] input[disabled],
        section[data-testid="stSidebar"] .stTextInput input {
            background-color: #f6f8fa !important;
            color: #1a1a1a !important;
            border: 1px solid #d0d7de !important;
            -webkit-text-fill-color: #1a1a1a !important;
            opacity: 1 !important;
        }
        
        /* Select dropdown */
        section[data-testid="stSidebar"] [data-baseweb="select"] {
            background-color: #f6f8fa !important;
        }
        
        section[data-testid="stSidebar"] [data-baseweb="select"] > div {
            background-color: #f6f8fa !important;
            border-color: #d0d7de !important;
            color: #1a1a1a !important;
        }
        
        section[data-testid="stSidebar"] [data-baseweb="select"] span {
            color: #1a1a1a !important;
        }
        
        /* Multiselect tags - keep green */
        section[data-testid="stSidebar"] [data-baseweb="tag"] {
            background-color: #238636 !important;
        }
        
        section[data-testid="stSidebar"] [data-baseweb="tag"] span {
            color: #ffffff !important;
        }
        
        /* Divider */
        section[data-testid="stSidebar"] hr {
            border-color: #d0d7de !important;
        }
        
        /* Alert messages */
        section[data-testid="stSidebar"] .stAlert p {
            color: #1a1a1a !important;
        }
        
        .sidebar-header {
            color: #1a1a1a !important;
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .sidebar-section {
            background: #f6f8fa;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            border: 1px solid #d0d7de;
        }
        
        /* === MAIN HEADER === */
        .main-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 8px;
        }
        
        .main-header h1 {
            color: #ffffff;
            font-size: 32px;
            font-weight: 700;
            margin: 0;
            font-family: 'Segoe UI', 'Google Sans', sans-serif;
        }
        
        .main-header .emoji {
            font-size: 36px;
        }
        
        .main-subtitle {
            color: #8b949e;
            font-size: 16px;
            margin-bottom: 24px;
        }
        
        /* === WHITE INFO CARDS (Cloud Skills Style) === */
        .info-card {
            background: #ffffff;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
            border-left: 4px solid #3fb950;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .info-card-blue {
            border-left-color: #58a6ff;
        }
        
        .info-card-yellow {
            border-left-color: #d29922;
        }
        
        .info-card h3 {
            color: #24292f;
            font-size: 14px;
            font-weight: 600;
            margin: 0 0 8px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .info-card .value {
            color: #24292f;
            font-size: 28px;
            font-weight: 700;
        }
        
        .info-card .subtitle {
            color: #3fb950;
            font-size: 13px;
            margin-top: 4px;
        }
        
        /* === SUCCESS BANNER (Green) === */
        .success-banner {
            background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
            border-radius: 8px;
            padding: 12px 20px;
            margin: 16px 0;
            color: #ffffff;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .success-banner::before {
            content: "✓";
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 20px;
            height: 20px;
            background: rgba(255,255,255,0.2);
            border-radius: 4px;
            font-size: 12px;
        }
        
        /* === SECTION HEADERS === */
        .section-header {
            display: flex;
            align-items: center;
            gap: 12px;
            color: #ffffff;
            font-size: 20px;
            font-weight: 600;
            margin: 32px 0 20px 0;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .section-header .icon {
            font-size: 24px;
        }
        
        /* === STREAMLIT OVERRIDES === */
        .stMarkdown h3 {
            color: #c9d1d9 !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            margin-bottom: 12px !important;
        }
        
        .stMarkdown h4 {
            color: #8b949e !important;
            font-size: 13px !important;
            font-weight: 500 !important;
        }
        
        /* === INPUTS (Dark Style) === */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            background: #0d1117 !important;
            border: 1px solid #30363d !important;
            border-radius: 8px !important;
            color: #c9d1d9 !important;
            font-size: 14px !important;
            padding: 12px 16px !important;
            transition: all 0.2s ease !important;
        }
        
        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: #58a6ff !important;
            box-shadow: 0 0 0 3px rgba(88,166,255,0.15) !important;
            background: #0d1117 !important;
        }
        
        .stTextInput > div > div > input::placeholder,
        .stTextArea > div > div > textarea::placeholder {
            color: #484f58 !important;
        }
        
        .stTextInput > label, .stTextArea > label, .stSelectbox > label, .stMultiSelect > label {
            color: #8b949e !important;
            font-size: 13px !important;
            font-weight: 500 !important;
        }
        
        /* === SELECT BOX === */
        .stSelectbox > div > div {
            background: #0d1117 !important;
            border: 1px solid #30363d !important;
            border-radius: 8px !important;
        }
        
        .stSelectbox > div > div:hover {
            border-color: #58a6ff !important;
        }
        
        /* === MULTISELECT === */
        .stMultiSelect > div > div {
            background: #0d1117 !important;
            border: 1px solid #30363d !important;
            border-radius: 8px !important;
        }
        
        /* === PRIMARY BUTTON (Teal/Green like Fetch Badges) === */
        .stButton > button {
            background: linear-gradient(135deg, #238636 0%, #2ea043 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 12px 24px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            letter-spacing: 0.3px !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 4px 12px rgba(35,134,54,0.3) !important;
        }
        
        .stButton > button:hover {
            background: linear-gradient(135deg, #2ea043 0%, #3fb950 100%) !important;
            box-shadow: 0 6px 16px rgba(35,134,54,0.4) !important;
            transform: translateY(-1px) !important;
        }
        
        .stButton > button:active {
            transform: translateY(0) !important;
        }
        
        /* === SIDEBAR BUTTON (Light Blue) === */
        [data-testid="stSidebar"] .stButton > button {
            background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%) !important;
            box-shadow: 0 4px 12px rgba(31,111,235,0.3) !important;
        }
        
        [data-testid="stSidebar"] .stButton > button:hover {
            background: linear-gradient(135deg, #388bfd 0%, #58a6ff 100%) !important;
            box-shadow: 0 6px 16px rgba(31,111,235,0.4) !important;
        }
        
        /* === STATUS MESSAGES === */
        .success-box {
            background: linear-gradient(135deg, rgba(46,160,67,0.15) 0%, rgba(35,134,54,0.1) 100%);
            border: 1px solid rgba(46,160,67,0.4);
            border-left: 4px solid #3fb950;
            padding: 16px 20px;
            border-radius: 8px;
            margin: 16px 0;
            color: #3fb950;
            font-weight: 500;
        }
        
        .error-box {
            background: linear-gradient(135deg, rgba(248,81,73,0.15) 0%, rgba(248,81,73,0.1) 100%);
            border: 1px solid rgba(248,81,73,0.4);
            border-left: 4px solid #f85149;
            padding: 16px 20px;
            border-radius: 8px;
            margin: 16px 0;
            color: #f85149;
            font-weight: 500;
        }
        
        .warning-box {
            background: linear-gradient(135deg, rgba(210,153,34,0.15) 0%, rgba(210,153,34,0.1) 100%);
            border: 1px solid rgba(210,153,34,0.4);
            border-left: 4px solid #d29922;
            padding: 16px 20px;
            border-radius: 8px;
            margin: 16px 0;
            color: #d29922;
            font-weight: 500;
        }
        
        .info-box {
            background: linear-gradient(135deg, rgba(88,166,255,0.15) 0%, rgba(88,166,255,0.1) 100%);
            border: 1px solid rgba(88,166,255,0.4);
            border-left: 4px solid #58a6ff;
            padding: 16px 20px;
            border-radius: 8px;
            margin: 16px 0;
            color: #58a6ff;
            font-weight: 500;
        }
        
        /* === PROGRESS BAR STYLE === */
        .progress-container {
            background: #21262d;
            border-radius: 12px;
            padding: 20px 24px;
            margin: 16px 0;
            border: 1px solid #30363d;
        }
        
        .progress-bar {
            background: #21262d;
            border-radius: 20px;
            height: 24px;
            overflow: hidden;
            margin: 12px 0;
        }
        
        .progress-fill {
            background: linear-gradient(90deg, #238636 0%, #3fb950 100%);
            height: 100%;
            border-radius: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 12px;
        }
        
        /* === METRIC CARDS ROW === */
        .metrics-row {
            display: flex;
            gap: 16px;
            margin: 20px 0;
        }
        
        .metric-card {
            flex: 1;
            background: #ffffff;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border-left: 4px solid #58a6ff;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .metric-card.green {
            border-left-color: #3fb950;
        }
        
        .metric-card.yellow {
            border-left-color: #d29922;
        }
        
        .metric-card .label {
            color: #57606a;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        
        .metric-card .value {
            color: #24292f;
            font-size: 24px;
            font-weight: 700;
        }
        
        /* === DIVIDER === */
        .section-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent 0%, #30363d 50%, transparent 100%);
            margin: 24px 0;
        }
        
        /* === PREVIEW CONTAINER === */
        .preview-container {
            background: #21262d;
            border-radius: 12px;
            border: 1px solid #30363d;
            overflow: hidden;
        }
        
        .preview-header {
            background: #161b22;
            padding: 14px 20px;
            border-bottom: 1px solid #30363d;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .preview-header span {
            color: #c9d1d9;
            font-weight: 600;
            font-size: 14px;
        }
        
        /* === CAPTIONS === */
        .stCaption {
            color: #8b949e !important;
            font-size: 12px !important;
        }
        
        /* === EXPANDER === */
        .streamlit-expanderHeader {
            background: #21262d !important;
            border-radius: 8px !important;
            color: #c9d1d9 !important;
            border: 1px solid #30363d !important;
        }
        
        .streamlit-expanderContent {
            background: #161b22 !important;
            border-radius: 0 0 8px 8px !important;
            border: 1px solid #30363d !important;
            border-top: none !important;
        }
        
        /* === ABOUT SECTION === */
        .about-section {
            background: #f6f8fa;
            border-radius: 12px;
            padding: 16px;
            margin-top: 16px;
            border: 1px solid #d0d7de;
        }
        
        .about-section h4 {
            color: #1a1a1a !important;
            font-size: 14px;
            font-weight: 600;
            margin: 0 0 12px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .about-section p {
            color: #1a1a1a !important;
            font-size: 13px;
            margin: 8px 0;
            line-height: 1.5;
        }
        
        .about-section p strong {
            color: #1a1a1a !important;
        }
        
        .feature-item {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            margin: 8px 0;
            color: #1a1a1a !important;
            font-size: 13px;
        }
        
        .feature-item span {
            color: #1a1a1a !important;
        }
        
        .feature-item .check {
            color: #1a7f37 !important;
            font-size: 14px;
        }
        
        /* === HIDE STREAMLIT DEFAULTS === */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* === SCROLLBAR === */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: #0d1117;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: #30363d;
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #484f58;
        }
        
        /* === ALERTS === */
        .stAlert {
            background: #21262d !important;
            border-radius: 8px !important;
            border: 1px solid #30363d !important;
        }
    </style>
    """, unsafe_allow_html=True)


def render_header():
    st.markdown("""
    <div class="main-header">
        <span class="emoji">📧</span>
        <h1>GDG Email Dashboard</h1>
    </div>
    <p class="main-subtitle">Send professional HTML emails with Gmail SMTP</p>
    """, unsafe_allow_html=True)


def render_credentials_section() -> tuple[str, str]:
    sender_email, app_password = get_credentials()
    
    if sender_email:
        if len(sender_email) > 8 and "@" in sender_email:
            local, domain = sender_email.split("@", 1)
            masked_email = local[:3] + "•" * min(8, len(local) - 3) + "@" + domain
        else:
            masked_email = "•" * 8 + "@configured"
    else:
        masked_email = "Not configured"
    
    # Determine configuration source
    config_source = "secrets.toml" if sender_email else "not found"
    
    st.markdown(f"""
    <div style="margin-bottom: 16px;">
        <label style="color: #1a1a1a; font-size: 14px; font-weight: 500; display: block; margin-bottom: 8px;">📧 GDG Email</label>
        <div style="background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px; padding: 10px 14px; color: #1a1a1a; font-size: 14px;">
            {masked_email}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    password_status = "•" * 10 if app_password else "Not configured"
    st.markdown(f"""
    <div style="margin-bottom: 16px;">
        <label style="color: #1a1a1a; font-size: 14px; font-weight: 500; display: block; margin-bottom: 8px;">🔒 App Password</label>
        <div style="background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px; padding: 10px 14px; color: #1a1a1a; font-size: 14px;">
            {password_status}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if not sender_email or not app_password:
        st.warning("⚠️ Add credentials to .streamlit/secrets.toml")
    else:
        st.caption(f"✅ Loaded from {config_source}")
    
    return sender_email, app_password


def render_template_section() -> str:
    templates = get_available_templates()
    
    if not templates:
        st.error("No templates found")
        return "base"
    
    return st.selectbox(
        "🎨 Email Template",
        options=templates,
        index=0,
        help="Choose an email template",
        format_func=lambda x: f"{x.replace('_', ' ').title()}"
    )


def render_recipients_section() -> tuple[str, str, str]:
    if "cached_to_emails" not in st.session_state:
        st.session_state.cached_to_emails = ""
    if "cached_cc_emails" not in st.session_state:
        st.session_state.cached_cc_emails = ""
    if "cached_bcc_emails" not in st.session_state:
        st.session_state.cached_bcc_emails = ""
    
    to_emails = st.text_area(
        "To (required)",
        value=st.session_state.cached_to_emails,
        placeholder="email1@example.com, email2@example.com",
        help="Comma-separated list of primary recipients",
        height=100,
        key="to_emails_input"
    )
    # Update cache when value changes
    st.session_state.cached_to_emails = to_emails
    
    col1, col2 = st.columns(2)
    
    with col1:
        cc_emails = st.text_input(
            "CC",
            value=st.session_state.cached_cc_emails,
            placeholder="cc@example.com",
            help="Carbon copy - visible to all",
            key="cc_emails_input"
        )
        st.session_state.cached_cc_emails = cc_emails
    
    with col2:
        bcc_emails = st.text_input(
            "BCC",
            value=st.session_state.cached_bcc_emails,
            placeholder="bcc@example.com",
            help="Blind carbon copy - hidden",
            key="bcc_emails_input"
        )
        st.session_state.cached_bcc_emails = bcc_emails
    
    # Show recipient count
    if to_emails.strip():
        to_list, invalid = parse_email_input(sanitize_email_input(to_emails))
        if invalid:
            st.error(f"❌ {invalid}")
        elif to_list:
            st.success(f"✓ {len(to_list)} recipient(s)")
    
    return to_emails, cc_emails, bcc_emails


def load_default_content() -> str:
    with contextlib.suppress(Exception):
        if DEFAULT_CONTENT.exists():
            return DEFAULT_CONTENT.read_text(encoding="utf-8")
    return ""


def render_content_section() -> tuple[str, str]:
    # Initialize session state for subject (persists on browser reload)
    if "cached_subject" not in st.session_state:
        st.session_state.cached_subject = ""
    
    subject = st.text_input(
        "Subject",
        value=st.session_state.cached_subject,
        placeholder="Enter email subject line",
        help="Clear and concise subject",
        key="subject_input"
    )
    # Update cache when value changes
    st.session_state.cached_subject = subject
    
    st.caption("💡 HTML content is injected into {{CONTENT}} in your template")
    
    # Initialize session state for HTML content (persists on browser reload)
    if "cached_html_content" not in st.session_state:
        st.session_state.cached_html_content = load_default_content()
    
    html_content = st.text_area(
        "HTML Body",
        value=st.session_state.cached_html_content,
        height=500,
        key="content_editor",
        help="HTML content for email body"
    )
    # Update cache when value changes
    st.session_state.cached_html_content = html_content
    
    return subject, html_content


def render_attachments_section() -> list:
    st.markdown("**📎 Attachments**")
    
    if not ATTACH_DIR.exists():
        st.caption("Create attach/ folder")
        return []
    
    available_files = []
    try:
        available_files = [f.name for f in ATTACH_DIR.iterdir() if f.is_file()]
    except PermissionError:
        st.error("Cannot access attach/")
        return []
    
    if not available_files:
        st.caption("No files available")
        return []
    
    selected_files = st.multiselect(
        "Select files",
        options=available_files,
        default=available_files,
        help=f"Max {MAX_ATTACHMENT_SIZE_MB}MB per file"
    )
    
    valid_attachments = []
    total_size = 0
    
    for filename in selected_files:
        try:
            file_path = ATTACH_DIR / filename
            
            if not file_path.exists():
                st.error(f"{filename}: Not found")
                continue
            
            file_size = file_path.stat().st_size
            size_valid, size_error = validate_attachment_size(file_size)
            type_valid, type_error = validate_attachment_type(filename)
            
            if not size_valid:
                st.error(f"{filename}: {size_error}")
            elif not type_valid:
                st.warning(f"{filename}: {type_error}")
            else:
                total_size += file_size
                valid_attachments.append(file_path)
                st.caption(f"✓ {filename} ({file_size / 1024:.1f} KB)")
                
        except Exception as e:
            st.error(f"{filename}: {str(e)}")
    
    if total_size > MAX_ATTACHMENT_SIZE_MB * 1024 * 1024:
        st.error(f"Total exceeds {MAX_ATTACHMENT_SIZE_MB}MB")
        return []
    
    return valid_attachments


def render_preview(html_content: str, template_name: str):
    try:
        template_path = get_template_path(template_name)
        builder = MessageBuilder(str(template_path))
        
        preview_content = html_content or "<p style='color:#888;font-style:italic;text-align:center;padding:40px;'>Your content will appear here...</p>"
        final_html = builder.inject_content(preview_content)
        
        st.components.v1.html(final_html, height=920, scrolling=True)
        
    except FileNotFoundError as e:
        st.error(f"Template not found: {e}")
    except Exception as e:
        st.error(f"Preview error: {str(e)}")


def validate_form(
    sender_email: str,
    app_password: str,
    to_emails: str,
    subject: str,
    template_name: str
) -> tuple[bool, list[str]]:
    errors = []
    
    # Credentials
    if not sender_email:
        errors.append("Sender email not configured in sender_config.py")
    elif not is_valid_email(sender_email):
        errors.append("Invalid sender email format")
    
    if not app_password:
        errors.append("App password not configured in sender_config.py")
    elif len(app_password.replace(" ", "")) < 16:
        errors.append("App password appears invalid (should be 16 characters)")
    
    # Recipients
    if not to_emails or not to_emails.strip():
        errors.append("At least one recipient is required")
    else:
        valid_emails, invalid_msg = parse_email_input(sanitize_email_input(to_emails))
        if invalid_msg:
            errors.append(invalid_msg)
        elif not valid_emails:
            errors.append("No valid recipient email addresses")
    
    # Subject
    if not subject or not subject.strip():
        errors.append("Subject is required")
    elif len(subject) > 998:  # RFC 5322 limit
        errors.append("Subject too long (max 998 characters)")
    
    # Template
    try:
        get_template_path(template_name)
    except FileNotFoundError:
        errors.append(f"Template '{template_name}' not found")
    
    return not errors, errors


def check_network_connectivity() -> bool:
    try:
        socket.create_connection(("smtp.gmail.com", 587), timeout=5)
        return True
    except (socket.timeout, socket.error, OSError):
        return False


def send_email_robust(
    sender_email: str,
    app_password: str,
    to_emails: str,
    cc_emails: str,
    bcc_emails: str,
    subject: str,
    html_content: str,
    template_name: str,
    attachments: list,
    max_retries: int = 2
) -> tuple[bool, str]:  # sourcery skip: low-code-quality
    if not check_network_connectivity():
        return False, "Network error: Cannot connect to Gmail SMTP server. Check your internet connection."
    
    try:
        to_list, _ = parse_email_input(sanitize_email_input(to_emails))
        cc_list, _ = parse_email_input(sanitize_email_input(cc_emails)) if cc_emails else ([], None)
        bcc_list, _ = parse_email_input(sanitize_email_input(bcc_emails)) if bcc_emails else ([], None)
        
        if not to_list:
            return False, "No valid recipients found"
        
        recipients = EmailRecipients(to=to_list, cc=cc_list, bcc=bcc_list)
        
    except Exception as e:
        return False, f"Failed to parse recipients: {str(e)}"
    
    try:
        template_path = get_template_path(template_name)
        builder = MessageBuilder(str(template_path))
        
        attachment_objects = []
        for file_path in attachments:
            try:
                if not file_path.exists():
                    return False, f"Attachment not found: {file_path.name}"
                
                content = file_path.read_bytes()
                attachment_objects.append(Attachment(
                    filename=file_path.name,
                    content=content
                ))
            except PermissionError:
                return False, f"Cannot read attachment: {file_path.name}"
            except Exception as e:
                return False, f"Error reading {file_path.name}: {str(e)}"
        
        content = html_content or ""
        
        message = builder.build(
            sender=sender_email,
            recipients=recipients,
            subject=subject,
            html_content=content,
            attachments=attachment_objects or None
        )
        
    except MessageBuilderError as e:
        return False, f"Message build error: {str(e)}"
    except Exception as e:
        return False, f"Failed to build message: {str(e)}"
    
    # Send with retries
    last_error = ""
    clean_password = app_password.replace(" ", "")
    
    for attempt in range(max_retries + 1):
        try:
            with SMTPClient(sender_email, clean_password) as client:
                result = client.send(message, recipients.all_recipients())
            
            if result["success"]:
                recipient_count = len(recipients.all_recipients())
                return True, f"Email sent successfully to {recipient_count} recipient(s)"
            else:
                last_error = result.get("message", "Unknown error")
                
        except SMTPClientError as e:
            last_error = str(e)
            if "Authentication failed" in last_error:
                # Don't retry auth failures
                return False, last_error
                
        except Exception as e:
            last_error = str(e)
        
        # Wait before retry
        if attempt < max_retries:
            time.sleep(1)
    
    return False, f"Failed after {max_retries + 1} attempts: {last_error}"


def main():
    inject_custom_css()

    # === SIDEBAR (Configuration) ===
    with st.sidebar:
        st.markdown('<div class="sidebar-header">⚙️ Configuration</div>', unsafe_allow_html=True)

        sender_email, app_password = render_credentials_section()
        st.markdown("---")

        template_name = render_template_section()
        st.markdown("---")

        attachments = render_attachments_section()

        st.markdown("""
        <div class="about-section">
            <h4>📚 About</h4>
            <p><strong>GDG Email Dashboard</strong></p>
            <div class="feature-item">
                <span class="check">✓</span>
                <span>HTML email templates</span>
            </div>
            <div class="feature-item">
                <span class="check">✓</span>
                <span>Multiple recipients (To/CC/BCC)</span>
            </div>
            <div class="feature-item">
                <span class="check">✓</span>
                <span>File attachments</span>
            </div>
            <div class="feature-item">
                <span class="check">✓</span>
                <span>Gmail SMTP integration</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # === MAIN CONTENT ===
    render_header()

    if sender_email and app_password:
        st.markdown('<div class="success-banner">Connected to Gmail SMTP</div>', unsafe_allow_html=True)

    col_form, col_preview = st.columns([1, 1], gap="large")

    with col_form:
        html_content = _panel_email_send(
            sender_email, app_password, template_name, attachments
        )
    with col_preview:
        st.markdown('<div class="section-header"><span class="icon">👁️</span>Live Preview</div>', unsafe_allow_html=True)
        render_preview(html_content, template_name)


def _panel_email_send(sender_email, app_password, template_name, attachments):
    st.markdown('<div class="section-header"><span class="icon">👥</span>Recipients</div>', unsafe_allow_html=True)
    to_emails, cc_emails, bcc_emails = render_recipients_section()

    st.markdown('<div class="section-header"><span class="icon">✉️</span>Email Content</div>', unsafe_allow_html=True)
    subject, result = render_content_section()

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        send_clicked = st.button(
            "🚀 Send Email",
            use_container_width=True,
            type="primary"
        )

    if send_clicked:
        is_valid, errors = validate_form(
            sender_email, app_password, to_emails, subject, template_name
        )

        if not is_valid:
            for error in errors:
                st.markdown(f'<div class="error-box">❌ {html.escape(error)}</div>', unsafe_allow_html=True)
        else:
            with st.spinner("📤 Sending email..."):
                success, message = send_email_robust(
                    sender_email,
                    app_password,
                    to_emails,
                    cc_emails,
                    bcc_emails,
                    subject,
                    result,
                    template_name,
                    attachments,
                )

            if success:
                st.markdown(f'<div class="success-box">✅ {html.escape(message)}</div>', unsafe_allow_html=True)
                st.balloons()
            else:
                st.markdown(f'<div class="error-box">❌ {html.escape(message)}</div>', unsafe_allow_html=True)

    return result


if __name__ == "__main__":
    main()
