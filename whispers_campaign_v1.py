import streamlit as st
import uuid
from datetime import datetime
from urllib.parse import urlencode, urlparse, urlunparse
import os
import traceback

# optional graphing
import networkx as nx
import matplotlib.pyplot as plt

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Whisper Remix Hub", page_icon="🧵", layout="wide")

DEFAULT_BASE_URL = "https://whispersbetav2.streamlit.app/"  # replace with your deployed URL
BASE_URL = st.sidebar.text_input("Base URL", DEFAULT_BASE_URL)

# -------------------------
# Firebase init with graceful fallback
# -------------------------
firestore_available = False

try:
    if not firebase_admin._apps:
        # prefer service account file if present
        if os.path.exists("firebase-key.json"):
            cred = credentials.Certificate("firebase-key.json")
            firebase_admin.initialize_app(cred)
        else:
            # attempt to initialize with Application Default Credentials
            firebase_admin.initialize_app()

    db = firestore.client()
    # quick test read to confirm connectivity (non-expensive)
    _ = list(db.collection("_meta_test").limit(1).stream())
    firestore_available = True
except Exception as e:
    # Log the traceback and show a warning in the app
    tb = traceback.format_exc()
    st.warning("Firestore initialization failed — running in local fallback mode.\n" + str(e))
    st.info("If you intend to use Firestore, make sure firebase-key.json is present or ADC are configured.")
    # Create local fallback store in session_state
    if "local_whispers" not in st.session_state:
        st.session_state.local_whispers = {}

# -------------------------
# Helpers (works with Firestore if available, otherwise session_state fallback)
# -------------------------

def new_id():
    return str(uuid.uuid4())


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def make_link_for_id(base_url, wid):
    parsed = urlparse(base_url)
    query = {"id": wid, "view": "detail"}
    new_query = urlencode(query)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", new_query, ""))


def make_snippet(message, wid, base_url):
    link = make_link_for_id(base_url, wid)
    return f"{message}\nRemix here → {link}"


# storage-aware CRUD helpers

def get_whisper(wid):
    if firestore_available:
        try:
            doc = db.collection("whispers").document(wid).get()
            return doc.to_dict() if doc.exists else None
        except Exception:
            # degrade to local
            _fallback_to_local("get_whisper")
    # local fallback
    return st.session_state.local_whispers.get(wid)


def save_whisper(data):
    if firestore_available:
        try:
            db.collection("whispers").document(data["id"]).set(data)
            return
        except Exception:
            _fallback_to_local("save_whisper")
    st.session_state.local_whispers[data["id"]] = data


def update_children(parent_id, child_id):
    parent = get_whisper(parent_id)
    if not parent:
        return
    children = parent.get("children", []) or []
    if child_id not in children:
        children.append(child_id)
    parent["children"] = children
    # persist updated parent
    if firestore_available:
        try:
            db.collection("whispers").document(parent_id).update({"children": children})
            return
        except Exception:
            _fallback_to_local("update_children")
    st.session_state.local_whispers[parent_id] = parent


def get_all_whispers():
    if firestore_available:
        try:
            docs = db.collection("whispers").stream()
            return {doc.id: doc.to_dict() for doc in docs}
        except Exception:
            _fallback_to_local("get_all_whispers")
    # local fallback
    return dict(st.session_state.local_whispers)


def _fallback_to_local(caller=""):
    """Switch to local fallback and ensure session_state storage exists.
    This is intentionally quiet and idempotent.
    """
    global firestore_available
    firestore_available = False
    if "local_whispers" not in st.session_state:
        st.session_state.local_whispers = {}
    st.warning(f"Firestore unavailable (during {caller}). Using local in-memory store for this session.")

# -------------------------
# Routing
# -------------------------
params = st.experimental_get_query_params()
current_view = params.get("view", ["home"])[0]
current_id = params.get("id", [None])[0]

# -------------------------
# Sidebar Navigation
# -------------------------
st.sidebar.markdown("### Navigation")
if st.sidebar.button("🏠 Home"):
    st.experimental_set_query_params(view="home")
if st.sidebar.button("📜 All Whispers"):
    st.experimental_set_query_params(view="browse")
if st.sidebar.button("🌳 Tree View"):
    st.experimental_set_query_params(view="tree")

# -------------------------
# Views
# -------------------------

def render_home():
    st.title("🧵 Whisper Remix Hub")
    st.markdown("Create immutable whispers, remix them, and explore trails of meaning.")

    st.subheader("Create a new whisper")
    motif = st.text_input("Motif (🌱, 🔥, 🧵)")
    phrase = st.text_input("Message")
    author = st.text_input("Author (optional)")
    if st.button("Create whisper"):
        if not phrase and not motif:
            st.error("Please enter a motif and/or message.")
        else:
            wid = new_id()
            message = f"{motif} {phrase}".strip()
            whisper = {
                "id": wid,
                "message": message,
                "motif": motif,
                "phrase": phrase,
                "parent": None,
                "children": [],
                "author": author or None,
                "timestamp": now_iso(),
            }
            save_whisper(whisper)
            st.success("Whisper created.")
            st.experimental_set_query_params(view="detail", id=wid)

    st.subheader("Recent whispers")
    whispers = get_all_whispers()
    roots = [w for w in whispers.values() if w.get("parent") is None]
    for w in sorted(roots, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]:
        link = make_link_for_id(BASE_URL, w["id"])
        st.markdown(f"- {w['message']} (by {w.get('author') or 'Anonymous'}) → {link}")


def render_detail(wid):
    w = get_whisper(wid)
    if not w:
        st.error("Whisper not found.")
        return

    st.subheader("Whisper detail")
    st.write(f"**Message:** {w['message']}")
    st.write(f"**Author:** {w.get('author') or 'Anonymous'}")
    st.write(f"**Timestamp:** {w.get('timestamp')}")

    share_link = make_link_for_id(BASE_URL, wid)
    snippet = make_snippet(w["message"], wid, BASE_URL)

    st.markdown("#### Share")
    st.code(snippet, language="text")

    st.markdown("#### Remix")
    remix_add = st.text_area("Add your continuation", placeholder="... but community makes it grow.")
    remix_author = st.text_input("Your name (optional)")
    if st.button("Submit remix"):
        if not remix_add.strip():
            st.error("Please add continuation.")
        else:
            new_wid = new_id()
            new_message = f"{w['message']} → {remix_add.strip()}"
            remix = {
                "id": new_wid,
                "message": new_message,
                "motif": w.get("motif"),
                "parent": wid,
                "children": [],
                "author": remix_author or None,
                "timestamp": now_iso(),
            }
            save_whisper(remix)
            update_children(wid, new_wid)
            st.success("Remix created.")
            st.experimental_set_query_params(view="detail", id=new_wid)

    st.markdown("#### Remixes")
    for cid in w.get("children", []) or []:
        child = get_whisper(cid)
        if child:
            st.markdown(f"- {child['message']} (by {child.get('author') or 'Anonymous'})")


def render_browse():
    st.subheader("All whispers")
    whispers = get_all_whispers()
    if not whispers:
        st.info("No whispers yet.")
        return
    for w in sorted(whispers.values(), key=lambda x: x.get("timestamp", ""), reverse=True):
        link = make_link_for_id(BASE_URL, w["id"])
        st.markdown(f"- {w['message']} (by {w.get('author') or 'Anonymous'}) → {link}")


def render_tree():
    st.subheader("Whisper lineage tree")
    whispers = get_all_whispers()
    if not whispers:
        st.info("No whispers yet.")
        return
    G = nx.DiGraph()
    for w in whispers.values():
        G.add_node(w["id"], label=w.get("message", "(no message)"))
        if w.get("parent"):
            G.add_edge(w["parent"], w["id"])
    fig, ax = plt.subplots(figsize=(10, 6))
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, ax=ax, with_labels=False, node_size=600, node_color="#91c9ff")
    labels = {n: G.nodes[n].get("label", "")[:50] for n in G.nodes}
    # limit label length to avoid overlap
    labels = {n: (labels[n][:50] if labels[n] else "") for n in labels}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    st.pyplot(fig)

# -------------------------
# Router
# -------------------------
if current_view == "detail" and current_id:
    render_detail(current_id)
elif current_view == "browse":
    render_browse()
elif current_view == "tree":
    render_tree()
else:
    render_home()
