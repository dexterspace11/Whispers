#!/usr/bin/env python3
import streamlit as st
import json
from datetime import datetime
import os
import base64
import re

# ----------------------------
# Config / file paths
# ----------------------------
TRAIL_FILE = "whisper_trail.json"
MOTIF_FILE = "motif_library.json"

# ----------------------------
# Utility: safe load & save
# ----------------------------
def safe_load(path, fallback):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return fallback
    return fallback

def safe_save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ----------------------------
# Load existing data
# ----------------------------
trail = safe_load(TRAIL_FILE, [])
motif_dict = safe_load(MOTIF_FILE, {
    "🫧": {"meaning": "fragile truth", "image": None, "format": None},
    "🌱": {"meaning": "growth", "image": None, "format": None},
    "🔥": {"meaning": "urgency", "image": None, "format": None},
    "🧬": {"meaning": "identity", "image": None, "format": None},
    "✨": {"meaning": "hope", "image": None, "format": None},
    "💡": {"meaning": "insight", "image": None, "format": None}, 
    "🪡": {"meaning": "reply", "image": None, "format": None},
    "🧵": {"meaning": "thread", "image": None, "format": None}
})

# ----------------------------
# Helpers: base64 encoding
# ----------------------------
def encode_file_to_base64(file):
    if file is None:
        return None
    try:
        file.seek(0)
    except Exception:
        pass
    data = file.read()
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64encode(data).decode("utf-8")

def decode_b64_to_bytes(b64str):
    if not b64str:
        return None
    return base64.b64decode(b64str)

# ----------------------------
# Auto-repair / normalize motif dict and trail
# ----------------------------
def normalize_motifs(m_dict):
    repaired = {}
    for k, v in m_dict.items():
        if isinstance(v, str):
            repaired[k] = {"meaning": v, "image": None, "format": None}
            continue
        if isinstance(v, dict):
            repaired[k] = {
                "meaning": v.get("meaning", "custom"),
                "image": v.get("image"),
                "format": v.get("format")
            }
            continue
        repaired[k] = {"meaning": "custom", "image": None, "format": None}
    return repaired

def normalize_trail(trail_list, motifs):
    repaired = []
    changed = False
    for w in trail_list:
        if not isinstance(w, dict):
            continue
        fixed = {
            "motif": w.get("motif", "🧵"),
            "message": w.get("message", ""),
            "link": w.get("link", ""),
            "author": w.get("author", "Anonymous"),
            "timestamp": w.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "remix": w.get("remix", "Original"),
            "image": w.get("image"),
            "image_format": w.get("image_format"),
            "image_motif": w.get("image_motif")
        }

        if fixed["motif"] not in motifs:
            motifs[fixed["motif"]] = {"meaning": "restored-motif", "image": None, "format": None}
            changed = True

        if fixed.get("image") and not fixed.get("image_motif"):
            tag = generate_image_motif_tag(motifs)
            motifs[tag] = {
                "meaning": "migrated-image",
                "image": fixed["image"],
                "format": fixed.get("image_format")
            }
            fixed["image_motif"] = tag
            fixed.pop("image", None)
            fixed.pop("image_format", None)
            changed = True

        repaired.append(fixed)

    return repaired, motifs, changed

# ----------------------------
# Generate unique motif tag (camera base)
# ----------------------------
def generate_image_motif_tag(m_dict, base="📷"):
    if base not in m_dict:
        return base
    highest = 1
    for k in m_dict:
        if k == base:
            continue
        if k.startswith(base):
            suffix = k[len(base):]
            if suffix.isdigit():
                try:
                    n = int(suffix)
                    highest = max(highest, n)
                except:
                    pass
    return f"{base}{highest+1}"

# ----------------------------
# Normalize on load
# ----------------------------
motif_dict = normalize_motifs(motif_dict)
trail, motif_dict, trail_changed = normalize_trail(trail, motif_dict)
safe_save(MOTIF_FILE, motif_dict)
if trail_changed:
    safe_save(TRAIL_FILE, trail)

# ----------------------------
# Unicode / Fancy Text Designer (for motif only)
# ----------------------------
FONT_STYLES = {
    "Default": str,
    "Bold": lambda s: ''.join(chr(ord(c)+0x1D400-ord('A')) if 'A'<=c<='Z' else
                                chr(ord(c)+0x1D41A-ord('a')) if 'a'<=c<='z' else c
                                for c in s),
    "Italic": lambda s: ''.join(chr(ord(c)+0x1D434-ord('A')) if 'A'<=c<='Z' else
                                chr(ord(c)+0x1D44E-ord('a')) if 'a'<=c<='z' else c
                                for c in s),
    "Bold Italic": lambda s: ''.join(chr(ord(c)+0x1D468-ord('A')) if 'A'<=c<='Z' else
                                     chr(ord(c)+0x1D482-ord('a')) if 'a'<=c<='z' else c
                                     for c in s),
    "Script": lambda s: ''.join(chr(ord(c)+0x1D49C-ord('A')) if 'A'<=c<='Z' else
                               chr(ord(c)+0x1D4B6-ord('a')) if 'a'<=c<='z' else c
                               for c in s),
    "Fraktur": lambda s: ''.join(chr(ord(c)+0x1D504-ord('A')) if 'A'<=c<='Z' else
                                chr(ord(c)+0x1D51E-ord('a')) if 'a'<=c<='z' else c
                                for c in s),
}

# ----------------------------
# Sidebar: Motif Manager
# ----------------------------
st.sidebar.header("💾 Motif Manager")
st.sidebar.subheader("Create motif")
new_key = st.sidebar.text_input("Tag (emoji or short text)", key="new_key")
new_meaning = st.sidebar.text_input("Meaning / description", key="new_meaning")
new_upload = st.sidebar.file_uploader("Upload motif image (optional)", type=["png","jpg","jpeg","gif"], key="new_upload")
if st.sidebar.button("Save motif", key="save_motif"):
    if not new_key:
        st.sidebar.error("Please provide a motif tag (emoji or short text).")
    else:
        if len(new_key)==1 or new_key.isprintable():
            image_b64 = None
            fmt = None
            if new_upload:
                new_upload.seek(0)
                image_b64 = encode_file_to_base64(new_upload)
                fmt = (new_upload.type.split("/")[-1]) if hasattr(new_upload,"type") else None
            motif_dict[new_key] = {"meaning": new_meaning or "custom", "image": image_b64, "format": fmt}
            safe_save(MOTIF_FILE, motif_dict)
            st.sidebar.success(f"Motif '{new_key}' saved.")
        else:
            st.sidebar.error("Invalid tag. Use a single emoji or short printable text.")

st.sidebar.markdown("---")
st.sidebar.subheader("Existing motifs")
keys = list(motif_dict.keys())
for k in keys:
    v = motif_dict[k]
    col1, col2 = st.sidebar.columns([0.2,0.8])
    with col1:
        if v.get("image"):
            try: st.image(decode_b64_to_bytes(v.get("image")), width=32)
            except: st.write("🖼")
        else:
            st.markdown(f"<div style='font-size:18px'>{k}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"**{k}** — {v.get('meaning','')}")
        btn_key = f"del_{re.sub(r'\\W','_',str(k))}"
        if st.button("Delete", key=btn_key):
            fallback = "🧵"
            for w in trail:
                if w.get("motif")==k: w["motif"]=fallback
                if w.get("image_motif")==k: w["image_motif"]=None
            motif_dict.pop(k,None)
            safe_save(MOTIF_FILE, motif_dict)
            safe_save(TRAIL_FILE, trail)
            st.experimental_rerun()

# ----------------------------
# Main UI - Whisper Generator
# ----------------------------
st.title("🧵 Whisper Generator")
st.markdown("Create and share poetic fragments with symbolic motifs, fancy text, and ambient links.")

with st.form("whisper_form"):
    st.subheader("Compose a Whisper")
    motif_options = []
    for key,data in motif_dict.items():
        suffix = " 🖼️" if data.get("image") else ""
        meaning = data.get("meaning","custom")
        motif_options.append(f"{key}{suffix} — {meaning}")
    selected = st.selectbox("Choose a motif", motif_options)
    motif_selected = selected.split()[0]
    chosen_meaning = motif_dict.get(motif_selected, {}).get("meaning","custom")
    st.caption(f"Motif meaning: {chosen_meaning}")

    # --- Unicode Designer (for motif only) ---
    font_style = st.selectbox("Fancy Font Style", list(FONT_STYLES.keys()))
    spacing = st.slider("Extra spacing between motif characters", 0, 5, 0)

    message = st.text_area("Whisper message", height=100)
    uploaded_image = st.file_uploader("Upload an image (optional) — it will be saved as a motif", type=["png","jpg","jpeg","gif"])
    link = st.text_input("Link (Bitly or full URL)")
    author = st.text_input("Author name or alias", value="Anonymous")
    submitted = st.form_submit_button("Generate & Post")

if submitted and message and link:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    image_motif_tag = None
    if uploaded_image:
        uploaded_image.seek(0)
        image_b64 = encode_file_to_base64(uploaded_image)
        fmt = (uploaded_image.type.split("/")[-1]) if hasattr(uploaded_image,"type") else None
        tag = generate_image_motif_tag(motif_dict)
        motif_dict[tag] = {"meaning":"whisper-image","image":image_b64,"format":fmt}
        image_motif_tag = tag
        safe_save(MOTIF_FILE, motif_dict)

    # Apply fancy style + spacing ONLY to motif
    fancy_func = FONT_STYLES.get(font_style, str)
    styled_motif = fancy_func(motif_selected)
    if spacing > 0:
        styled_motif = (" " * spacing).join(list(styled_motif))

    whisper = {
        "motif": styled_motif,   # styled motif only
        "message": message,       # message remains plain
        "link": link,
        "author": author,
        "timestamp": timestamp,
        "remix": "Original",
        "image_motif": image_motif_tag
    }

    trail.insert(0, whisper)
    safe_save(TRAIL_FILE, trail)
    st.success("Whisper added to the trail!")

    # Output formats
    full_whisper = f"{styled_motif} {message}"
    html_format = f'<a href="{link}" target="_blank">{full_whisper}</a>'
    md_format = f'[{full_whisper}]({link})'
    social_format = f"{full_whisper}\n{link}"

    st.markdown("### 🔗 Whisper Formats")
    st.code(html_format)
    st.code(md_format)
    st.code(social_format)

# ----------------------------
# Display Whisper Trail
# ----------------------------
st.markdown("---")
st.header("📚 Whisper Trail")
if not trail:
    st.info("No whispers yet. Be the first to seed one.")
else:
    for idx,w in enumerate(trail):
        st.markdown("### Motif")
        mtag = w.get("motif","🧵")
        mdata = motif_dict.get(mtag, {"meaning":"custom","image":None})
        if mdata.get("image"):
            try: st.image(decode_b64_to_bytes(mdata.get("image")), width=48)
            except: st.markdown(f"<div style='font-size:18px'>{mtag}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='font-size:1.2em'>{mtag}</span>", unsafe_allow_html=True)

        st.markdown(f"**Message**: {w.get('message','')}")
        link_text = w.get("link","")
        if link_text:
            st.markdown(f"**Link**: [{link_text}]({link_text})")
        st.markdown(f"**Author**: {w.get('author','Anonymous')}  \n**Timestamp**: {w.get('timestamp','')}")
        st.markdown(f"**Remix Lineage**: {w.get('remix','Original')}")
        if mdata.get("meaning"):
            st.caption(f"Motif meaning: {mdata.get('meaning')}")
        if w.get("image_motif"):
            im_tag = w.get("image_motif")
            im_data = motif_dict.get(im_tag)
            if im_data and im_data.get("image"):
                st.image(decode_b64_to_bytes(im_data.get("image")), caption="Attached image", use_container_width=True)
            else:
                st.caption("Attached image motif missing (it may have been deleted).")
        st.markdown("---")
