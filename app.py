import contextlib
import html
import socket
import time

import streamlit as st
from pathlib import Path

from email_service import SMTPClient, MessageBuilder
from email_service.smtp_client import SMTPClientError
from email_service.message_builder import EmailRecipients, Attachment, MessageBuilderError
from utils.validators import parse_email_input, is_valid_email, sanitize_email_input
from utils.config import (
    TEMPLATES_DIR, CONTENTS_DIR, ATTACH_DIR,
    validate_attachment_size, validate_attachment_type, MAX_ATTACHMENT_SIZE_MB,
)

st.set_page_config(
    page_title="GDG Email Dashboard",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=3600)
def get_predefined_accounts() -> dict[str, dict[str, str]]:
    try:
        raw = st.secrets.get("accounts", {})
        return {
            k: {
                "label": raw[k].get("label", k),
                "sender_email": raw[k].get("sender_email", ""),
                "app_password": raw[k].get("app_password", ""),
            }
            for k in raw
        }
    except (FileNotFoundError, KeyError, AttributeError):
        return {}


def get_available_templates() -> list[str]:
    if TEMPLATES_DIR.exists():
        t = [f.stem for f in TEMPLATES_DIR.iterdir() if f.is_file() and f.suffix == ".html"]
        if t:
            return sorted(t)
    return ["base"]


def get_content_path(name: str) -> Path:
    return CONTENTS_DIR / f"{name}_content.html"


def get_template_path(name: str) -> Path:
    p = TEMPLATES_DIR / f"{name}.html"
    if p.exists():
        return p
    raise FileNotFoundError(f"Template '{name}' not found")


def inject_custom_css():
    st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=Roboto:wght@400;500;700&display=swap');
* { font-family: 'Google Sans', 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

.stApp {
    background: linear-gradient(180deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    min-height: 100vh;
}

[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e1e4e8;
    --text-color: #1a1a1a;
    --secondary-text-color: #57606a;
    --background-color: #ffffff;
    --secondary-background-color: #f6f8fa;
    --border-color: #d0d7de;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 2rem; }
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] { display: none !important; visibility: hidden !important; }

section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown strong,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] .stCaption {
    color: #1a1a1a !important;
}

section[data-testid="stSidebar"] .stTextInput > label,
section[data-testid="stSidebar"] .stTextArea > label,
section[data-testid="stSidebar"] .stSelectbox > label,
section[data-testid="stSidebar"] .stMultiSelect > label {
    color: #1a1a1a !important;
    -webkit-text-fill-color: #1a1a1a !important;
}

section[data-testid="stSidebar"] .stTextInput > div > div > input,
section[data-testid="stSidebar"] .stTextInput > div > div > input:disabled,
section[data-testid="stSidebar"] .stTextInput > div > div > input[disabled],
section[data-testid="stSidebar"] .stTextArea > div > div > textarea {
    background: #f6f8fa !important;
    color: #1a1a1a !important;
    border: 1px solid #d0d7de !important;
    -webkit-text-fill-color: #1a1a1a !important;
    opacity: 1 !important;
}

section[data-testid="stSidebar"] .stTextInput > div > div > input:focus,
section[data-testid="stSidebar"] .stTextArea > div > div > textarea:focus {
    border-color: #1f6feb !important;
    box-shadow: 0 0 0 3px rgba(31,111,235,0.15) !important;
    background: #ffffff !important;
}

section[data-testid="stSidebar"] .stTextInput > div > div > input::placeholder,
section[data-testid="stSidebar"] .stTextArea > div > div > textarea::placeholder {
    color: #8b949e !important;
    -webkit-text-fill-color: #8b949e !important;
}

section[data-testid="stSidebar"] .stSelectbox > div > div {
    background: #f6f8fa !important;
    border: 1px solid #d0d7de !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] .stSelectbox > div > div:hover {
    border-color: #1f6feb !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] { background-color: #f6f8fa !important; }
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background-color: #f6f8fa !important;
    border-color: #d0d7de !important;
    color: #1a1a1a !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] span { color: #1a1a1a !important; }
section[data-testid="stSidebar"] [data-baseweb="tag"] { background-color: #238636 !important; }
section[data-testid="stSidebar"] [data-baseweb="tag"] span { color: #ffffff !important; }
section[data-testid="stSidebar"] hr { border-color: #d0d7de !important; }
section[data-testid="stSidebar"] .stAlert p { color: #1a1a1a !important; }

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
.main-header .emoji { font-size: 36px; }
.main-subtitle { color: #8b949e; font-size: 16px; margin-bottom: 24px; }

.info-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    border-left: 4px solid #3fb950;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.info-card-blue { border-left-color: #58a6ff; }
.info-card-yellow { border-left-color: #d29922; }
.info-card h3 {
    color: #24292f;
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 8px 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.info-card .value { color: #24292f; font-size: 28px; font-weight: 700; }
.info-card .subtitle { color: #3fb950; font-size: 13px; margin-top: 4px; }

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
.section-header .icon { font-size: 24px; }

.stMarkdown h3 { color: #c9d1d9 !important; font-size: 15px !important; font-weight: 600 !important; margin-bottom: 12px !important; }
.stMarkdown h4 { color: #8b949e !important; font-size: 13px !important; font-weight: 500 !important; }

section.main .stTextInput > div > div > input,
section.main .stTextArea > div > div > textarea {
    background: #0d1117 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #c9d1d9 !important;
    font-size: 14px !important;
    padding: 12px 16px !important;
    transition: all 0.2s ease !important;
}
section.main .stTextInput > div > div > input:focus,
section.main .stTextArea > div > div > textarea:focus {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 3px rgba(88,166,255,0.15) !important;
    background: #0d1117 !important;
}
section.main .stTextInput > div > div > input::placeholder,
section.main .stTextArea > div > div > textarea::placeholder {
    color: #484f58 !important;
}

section.main .stTextInput > label,
section.main .stTextArea > label,
section.main .stSelectbox > label,
section.main .stMultiSelect > label {
    color: #8b949e !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}

section.main .stSelectbox > div > div {
    background: #0d1117 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
}
section.main .stSelectbox > div > div:hover { border-color: #58a6ff !important; }

section.main .stMultiSelect > div > div {
    background: #0d1117 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
}

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
.stButton > button:active { transform: translateY(0) !important; }

[data-testid="stSidebar"] .stButton > button {
    background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%) !important;
    box-shadow: 0 4px 12px rgba(31,111,235,0.3) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: linear-gradient(135deg, #388bfd 0%, #58a6ff 100%) !important;
    box-shadow: 0 6px 16px rgba(31,111,235,0.4) !important;
}

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

.metrics-row { display: flex; gap: 16px; margin: 20px 0; }
.metric-card {
    flex: 1;
    background: #ffffff;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    border-left: 4px solid #58a6ff;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.metric-card.green { border-left-color: #3fb950; }
.metric-card.yellow { border-left-color: #d29922; }
.metric-card .label {
    color: #57606a;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}
.metric-card .value { color: #24292f; font-size: 24px; font-weight: 700; }

.section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, #30363d 50%, transparent 100%);
    margin: 24px 0;
}

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
.preview-header span { color: #c9d1d9; font-weight: 600; font-size: 14px; }

.stCaption { color: #8b949e !important; font-size: 12px !important; }

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
.about-section p { color: #1a1a1a !important; font-size: 13px; margin: 8px 0; line-height: 1.5; }
.about-section p strong { color: #1a1a1a !important; }
.feature-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin: 8px 0;
    color: #1a1a1a !important;
    font-size: 13px;
}
.feature-item span { color: #1a1a1a !important; }
.feature-item .check { color: #1a7f37 !important; font-size: 14px; }

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #0d1117; border-radius: 4px; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #484f58; }

.stAlert { background: #21262d !important; border-radius: 8px !important; border: 1px solid #30363d !important; }
</style>""", unsafe_allow_html=True)


def render_header():
    st.markdown("""
    <div class="main-header">
        <span class="emoji">📧</span>
        <h1>GDG Email Dashboard</h1>
    </div>
    <p class="main-subtitle">Send professional HTML emails with Gmail SMTP</p>
    """, unsafe_allow_html=True)


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "Not configured"
    local, domain = email.split("@", 1)
    v = min(3, len(local))
    return f"{local[:v]}{'•' * max(1, len(local) - v)}@{domain}"


def render_credentials_section() -> tuple[str, str]:
    accounts = get_predefined_accounts()
    options = [a["label"] for a in accounts.values()]
    keys = list(accounts.keys())
    options.append("✏️ Custom")

    if "selected_account_idx" not in st.session_state:
        st.session_state.selected_account_idx = 0
    if "custom_email" not in st.session_state:
        st.session_state.custom_email = ""
    if "custom_password" not in st.session_state:
        st.session_state.custom_password = ""

    idx = st.selectbox(
        "👤 Account",
        range(len(options)),
        index=st.session_state.selected_account_idx,
        format_func=lambda i: options[i],
        key="account_selector",
    )
    st.session_state.selected_account_idx = idx
    is_custom = idx == len(keys)

    if is_custom:
        email = st.text_input(
            "📧 Gmail Address",
            value=st.session_state.custom_email,
            placeholder="you@gmail.com",
            key="custom_email_input",
        )
        pwd = st.text_input(
            "🔒 App Password",
            value=st.session_state.custom_password,
            type="password",
            placeholder="xxxx xxxx xxxx xxxx",
            key="custom_password_input",
        )
        st.session_state.custom_email = email
        st.session_state.custom_password = pwd
        if email and pwd:
            st.caption("✅ Using custom credentials")
        else:
            st.warning("⚠️ Enter email and app password")
        return email or "", pwd or ""

    k = keys[idx]
    sender_email = accounts[k]["sender_email"]
    app_password = accounts[k]["app_password"]
    st.markdown(f"""
    <div style="margin-bottom:12px;">
        <label style="color:#1a1a1a;font-size:13px;font-weight:500;display:block;margin-bottom:6px;">📧 GDG Email</label>
        <div style="background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;padding:10px 14px;color:#1a1a1a;font-size:14px;">{_mask_email(sender_email)}</div>
    </div>
    <div style="margin-bottom:12px;">
        <label style="color:#1a1a1a;font-size:13px;font-weight:500;display:block;margin-bottom:6px;">🔒 App Password</label>
        <div style="background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;padding:10px 14px;color:#1a1a1a;font-size:14px;">{"•" * 16}</div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("✅ Loaded from secrets.toml")
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
        format_func=lambda x: x.replace("_", " ").title(),
    )


def render_recipients_section() -> tuple[str, str, str]:
    to = st.text_area(
        "To (required)",
        placeholder="email1@example.com, email2@example.com",
        height=100,
        key="field_to_emails",
    )
    c1, c2 = st.columns(2)
    with c1:
        cc = st.text_input("CC", placeholder="cc@example.com", key="field_cc_emails")
    with c2:
        bcc = st.text_input("BCC", placeholder="bcc@example.com", key="field_bcc_emails")

    if to.strip():
        valid, invalid = parse_email_input(sanitize_email_input(to))
        if invalid:
            st.error(f"❌ {invalid}")
        elif valid:
            st.success(f"✓ {len(valid)} recipient(s)")

    return to, cc, bcc


def load_default_content(name: str = "") -> str:
    if name:
        p = get_content_path(name)
        if p.exists():
            with contextlib.suppress(Exception):
                return p.read_text(encoding="utf-8")
    return ""


def render_content_section(template_name: str = "") -> tuple[str, str]:
    if "current_template" not in st.session_state:
        st.session_state.current_template = ""

    if template_name and template_name != st.session_state.current_template:
        st.session_state.current_template = template_name
        st.session_state.field_html_content = load_default_content(template_name)
        st.rerun()

    if "field_html_content" not in st.session_state:
        st.session_state.field_html_content = load_default_content(template_name)

    subject = st.text_input(
        "Subject",
        placeholder="Enter email subject line",
        key="field_subject",
    )
    st.caption("💡 HTML content is injected into {{CONTENT}} in your template")
    body = st.text_area("HTML Body", height=500, key="field_html_content")
    return subject, body


def render_attachments_section() -> list:
    st.markdown("**📎 Attachments**")
    if not ATTACH_DIR.exists():
        st.caption("Create attach/ folder")
        return []

    try:
        files = [f.name for f in ATTACH_DIR.iterdir() if f.is_file()]
    except PermissionError:
        st.error("Cannot access attach/")
        return []

    if not files:
        st.caption("No files available")
        return []

    selected = st.multiselect(
        "Select files",
        options=files,
        help=f"Max {MAX_ATTACHMENT_SIZE_MB}MB per file",
    )

    valid = []
    total = 0
    for name in selected:
        try:
            fp = ATTACH_DIR / name
            if not fp.exists():
                st.error(f"{name}: Not found")
                continue
            sz = fp.stat().st_size
            ok_sz, err_sz = validate_attachment_size(sz)
            ok_tp, err_tp = validate_attachment_type(name)
            if not ok_sz:
                st.error(f"{name}: {err_sz}")
            elif not ok_tp:
                st.warning(f"{name}: {err_tp}")
            else:
                total += sz
                valid.append(fp)
                st.caption(f"✓ {name} ({sz / 1024:.1f} KB)")
        except Exception as e:
            st.error(f"{name}: {e}")

    if total > MAX_ATTACHMENT_SIZE_MB * 1024 * 1024:
        st.error(f"Total exceeds {MAX_ATTACHMENT_SIZE_MB}MB")
        return []
    return valid


def render_preview(content: str, template_name: str):
    try:
        builder = MessageBuilder(str(get_template_path(template_name)))
        preview = content or "<p style='color:#888;font-style:italic;text-align:center;padding:40px;'>Your content will appear here...</p>"
        st.components.v1.html(builder.inject_content(preview), height=920, scrolling=True)
    except FileNotFoundError as e:
        st.error(f"Template not found: {e}")
    except Exception as e:
        st.error(f"Preview error: {e}")


def validate_form(email: str, pwd: str, to: str, subject: str, template: str) -> tuple[bool, list[str]]:
    errors = []
    if not email:
        errors.append("Sender email is required")
    elif not is_valid_email(email):
        errors.append("Invalid sender email format")
    if not pwd:
        errors.append("App password is required")
    elif len(pwd.replace(" ", "")) < 16:
        errors.append("App password appears invalid (should be 16 characters)")
    if not to or not to.strip():
        errors.append("At least one recipient is required")
    else:
        v, inv = parse_email_input(sanitize_email_input(to))
        if inv:
            errors.append(inv)
        elif not v:
            errors.append("No valid recipient email addresses")
    if not subject or not subject.strip():
        errors.append("Subject is required")
    elif len(subject) > 998:
        errors.append("Subject too long (max 998 characters)")
    try:
        get_template_path(template)
    except FileNotFoundError:
        errors.append(f"Template '{template}' not found")
    return not errors, errors


def check_network() -> bool:
    try:
        socket.create_connection(("smtp.gmail.com", 587), timeout=5)
        return True
    except (socket.timeout, socket.error, OSError):
        return False


def send_email_robust(
    sender: str, pwd: str, to: str, cc: str, bcc: str,
    subject: str, content: str, template: str, attachments: list,
    retries: int = 2,
) -> tuple[bool, str]:
    if not check_network():
        return False, "Network error: Cannot connect to Gmail SMTP server. Check your internet connection."

    try:
        to_list, _ = parse_email_input(sanitize_email_input(to))
        cc_list, _ = parse_email_input(sanitize_email_input(cc)) if cc else ([], None)
        bcc_list, _ = parse_email_input(sanitize_email_input(bcc)) if bcc else ([], None)
        if not to_list:
            return False, "No valid recipients found"
        recipients = EmailRecipients(to=to_list, cc=cc_list, bcc=bcc_list)
    except Exception as e:
        return False, f"Failed to parse recipients: {e}"

    try:
        builder = MessageBuilder(str(get_template_path(template)))
        att_objs = []
        for fp in attachments:
            if not fp.exists():
                return False, f"Attachment not found: {fp.name}"
            try:
                att_objs.append(Attachment(filename=fp.name, content=fp.read_bytes()))
            except PermissionError:
                return False, f"Cannot read attachment: {fp.name}"
            except Exception as e:
                return False, f"Error reading {fp.name}: {e}"
        message = builder.build(
            sender=sender,
            recipients=recipients,
            subject=subject,
            html_content=content or "",
            attachments=att_objs or None,
        )
    except MessageBuilderError as e:
        return False, f"Message build error: {e}"
    except Exception as e:
        return False, f"Failed to build message: {e}"

    last_err = ""
    clean_pwd = pwd.replace(" ", "")
    for attempt in range(retries + 1):
        try:
            with SMTPClient(sender, clean_pwd) as client:
                result = client.send(message, recipients.all_recipients())
            if result["success"]:
                return True, f"Email sent successfully to {len(recipients.all_recipients())} recipient(s)"
            last_err = result.get("message", "Unknown error")
        except SMTPClientError as e:
            last_err = str(e)
            if "Authentication failed" in last_err:
                return False, last_err
        except Exception as e:
            last_err = str(e)
        if attempt < retries:
            time.sleep(1)

    return False, f"Failed after {retries + 1} attempts: {last_err}"


def _panel_email_send(sender, pwd, template, attachments):
    st.markdown('<div class="section-header"><span class="icon">👥</span>Recipients</div>', unsafe_allow_html=True)
    to, cc, bcc = render_recipients_section()

    st.markdown('<div class="section-header"><span class="icon">✉️</span>Email Content</div>', unsafe_allow_html=True)
    subject, body = render_content_section(template)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    _, c, _ = st.columns([1, 2, 1])
    with c:
        clicked = st.button("🚀 Send Email", use_container_width=True, type="primary")

    if clicked:
        ok, errors = validate_form(sender, pwd, to, subject, template)
        if not ok:
            for e in errors:
                st.markdown(f'<div class="error-box">❌ {html.escape(e)}</div>', unsafe_allow_html=True)
        else:
            with st.spinner("📤 Sending email..."):
                success, msg = send_email_robust(sender, pwd, to, cc, bcc, subject, body, template, attachments)
            if success:
                st.markdown(f'<div class="success-box">✅ {html.escape(msg)}</div>', unsafe_allow_html=True)
                st.balloons()
            else:
                st.markdown(f'<div class="error-box">❌ {html.escape(msg)}</div>', unsafe_allow_html=True)

    return body


def main():
    inject_custom_css()

    with st.sidebar:
        st.markdown('<div class="sidebar-header">⚙️ Configuration</div>', unsafe_allow_html=True)
        sender, pwd = render_credentials_section()
        st.markdown("---")
        template = render_template_section()
        st.markdown("---")
        attachments = render_attachments_section()
        st.markdown("""
        <div class="about-section">
            <h4>📚 About</h4>
            <p><strong>GDG Email Dashboard</strong></p>
            <div class="feature-item"><span class="check">✓</span><span>HTML email templates</span></div>
            <div class="feature-item"><span class="check">✓</span><span>Multiple recipients (To/CC/BCC)</span></div>
            <div class="feature-item"><span class="check">✓</span><span>File attachments</span></div>
            <div class="feature-item"><span class="check">✓</span><span>Gmail SMTP integration</span></div>
        </div>
        """, unsafe_allow_html=True)

    render_header()
    if sender and pwd:
        st.markdown('<div class="success-banner">Connected to Gmail SMTP</div>', unsafe_allow_html=True)

    col_form, col_preview = st.columns([1, 1], gap="large")
    with col_form:
        body = _panel_email_send(sender, pwd, template, attachments)
    with col_preview:
        st.markdown('<div class="section-header"><span class="icon">👁️</span>Live Preview</div>', unsafe_allow_html=True)
        render_preview(body, template)


if __name__ == "__main__":
    main()
