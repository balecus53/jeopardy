import base64
import copy
import html
import io
import json
import random
import uuid
from pathlib import Path

from PIL import Image, ImageOps
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Jeopardy!", page_icon="❓", layout="wide")

MAX_CATEGORIES = 6
MIN_ROWS, MAX_ROWS = 1, 7
SAVE_PATH = Path(__file__).with_name("jeopardy_board.json")
TEAM_COLORS = ["#ff6b6b", "#4dd0ff", "#7dff9b", "#ffb84d"]

S = st.session_state


# ----------------------------------------------------------------------------
# Board data helpers
# ----------------------------------------------------------------------------
def blank_clue(q="", a=""):
    # img = base64 data URL (optional photo), zoom = starting zoom level,
    # fx/fy = focus point in %, ar = image aspect ratio (width / height)
    return {"q": q, "a": a, "img": "", "zoom": 4.0, "fx": 50, "fy": 50, "ar": 1.5}


def _num(value, default, lo, hi):
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def clean_clue(x):
    return {
        "q": str(x.get("q", "")),
        "a": str(x.get("a", "")),
        "img": str(x.get("img", "")),
        "zoom": _num(x.get("zoom"), 4.0, 1.5, 12.0),
        "fx": int(_num(x.get("fx"), 50, 0, 100)),
        "fy": int(_num(x.get("fy"), 50, 0, 100)),
        "ar": _num(x.get("ar"), 1.5, 0.2, 5.0),
    }


def has_content(clue):
    return bool(clue["q"].strip() or clue.get("img"))


def clean_final(f):
    f = f if isinstance(f, dict) else {}
    return {
        "enabled": bool(f.get("enabled", False)),
        "category": str(f.get("category", "")),
        "q": str(f.get("q", "")),
        "a": str(f.get("a", "")),
    }


def new_category(name="New category", rows=5, clues=None):
    clues = clues or [("", "")] * rows
    return {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "clues": [blank_clue(q, a) for q, a in clues],
    }


def default_board():
    return {
        "base": 200,
        "categories": [
            new_category("Python", clues=[
                ("This keyword is used to define a function in Python.", "What is def?"),
                ("This built-in function returns the number of items in a list.", "What is len()?"),
                ("Python's package installer, whose name is a recursive acronym.", "What is pip?"),
                ("This data structure stores key-value pairs inside curly braces.", "What is a dictionary?"),
                ("Python is named after this British comedy troupe.", "Who are Monty Python?"),
            ]),
            new_category("Geography", clues=[
                ("This city on the Seine is the capital of France.", "What is Paris?"),
                ("The longest river in Africa.", "What is the Nile?"),
                ("This South American country is the largest by land area.", "What is Brazil?"),
                ("The smallest country in the world by area.", "What is Vatican City?"),
                ("Earth's highest mountain above sea level.", "What is Mount Everest?"),
            ]),
            new_category("Science", clues=[
                ("H2O is the chemical formula for this.", "What is water?"),
                ("This planet is known as the Red Planet.", "What is Mars?"),
                ("This gas makes up about 78% of Earth's atmosphere.", "What is nitrogen?"),
                ("This organelle is called the powerhouse of the cell.", "What are mitochondria?"),
                ("This physicist published general relativity in 1915.", "Who is Albert Einstein?"),
            ]),
            new_category("Movies", clues=[
                ("In this 1997 film, Jack and Rose sail on a doomed ocean liner.", "What is Titanic?"),
                ("This green ogre stars in a DreamWorks animated franchise.", "Who is Shrek?"),
                ("This director made Jaws, E.T., and Jurassic Park.", "Who is Steven Spielberg?"),
                ("'Life is like a box of chocolates' comes from this 1994 film.", "What is Forrest Gump?"),
                ("In this 1999 sci-fi film, Neo takes the red pill.", "What is The Matrix?"),
            ]),
            new_category("Food", clues=[
                ("This Italian dish is topped with tomato sauce and mozzarella.", "What is pizza?"),
                ("Sushi rolls are traditionally wrapped in this dried seaweed.", "What is nori?"),
                ("The world's priciest spice by weight comes from crocus flowers.", "What is saffron?"),
                ("This crescent-shaped French pastry is flaky and buttery.", "What is a croissant?"),
                ("This spicy fermented Korean cabbage dish is a staple side.", "What is kimchi?"),
            ]),
        ],
        "final": {
            "enabled": True,
            "category": "World Capitals",
            "q": "Located on the Danube, this capital was formed in 1873 by merging Buda, Pest and Óbuda.",
            "a": "What is Budapest?",
        },
    }


def normalize(b):
    """Make sure a board (e.g. from an uploaded file) is well-formed."""
    try:
        base = max(50, int(b.get("base", 200)))
    except (TypeError, ValueError):
        base = 200
    cats = []
    for c in (b.get("categories") or [])[:MAX_CATEGORIES]:
        cats.append({
            "id": c.get("id") or uuid.uuid4().hex[:8],
            "name": str(c.get("name", "")),
            "clues": [clean_clue(x) for x in c.get("clues", [])],
        })
    if not cats:
        cats = [new_category()]
    rows = max(MIN_ROWS, min(MAX_ROWS, max(len(c["clues"]) for c in cats)))
    for c in cats:
        c["clues"] = (c["clues"][:rows] + [blank_clue() for _ in range(rows)])[:rows]
    return {"base": base, "categories": cats, "final": clean_final(b.get("final"))}


def load_board():
    if SAVE_PATH.exists():
        try:
            return normalize(json.loads(SAVE_PATH.read_text()))
        except Exception:
            pass
    return default_board()


def n_rows():
    return len(S.board["categories"][0]["clues"])


def values():
    return [S.board["base"] * (i + 1) for i in range(n_rows())]


def esc(text):
    return html.escape(text).replace("\n", "<br>")


def encode_image(data, max_side=1400):
    """Shrink an uploaded photo and return (data URL, aspect ratio)."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    w, h = img.size
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(), round(w / h, 4)


def photo_html(clue, scale, reveal=False, maxh=520):
    """A photo cropped by zooming in on the clue's focus point."""
    src = clue.get("img", "")
    if not src.startswith("data:image/"):
        return ""
    cls = "photo-img reveal" if reveal else "photo-img"
    return (
        f'<div class="photo-frame" style="--ar:{clue["ar"]};--maxh:{maxh}px">'
        f'<img class="{cls}" src="{html.escape(src, quote=True)}" '
        f'style="--z:{scale};transform-origin:{clue["fx"]}% {clue["fy"]}%"></div>'
    )


WIDGET_PREFIXES = ("final_", "catname_", "q_", "a_", "zoom_", "fx_", "fy_", "img_", "imgid_", "base_input")


def clear_clue_keys(cid, r):
    for k in list(S.keys()):
        if isinstance(k, str) and (
            k in (f"q_{cid}_{r}", f"a_{cid}_{r}", f"zoom_{cid}_{r}", f"fx_{cid}_{r}",
                  f"fy_{cid}_{r}", f"imgid_{cid}_{r}")
            or k.startswith(f"img_{cid}_{r}_")
        ):
            del S[k]
    S.upl_ver.pop(f"{cid}_{r}", None)


def set_board(new):
    """Replace the board and clear stale editor widget state."""
    for k in list(S.keys()):
        if isinstance(k, str) and k.startswith(WIDGET_PREFIXES):
            del S[k]
    S.upl_ver = {}
    S.board = normalize(new)


# ----------------------------------------------------------------------------
# Game state
# ----------------------------------------------------------------------------
def new_game():
    S.used = set()
    S.current = None
    S.show_answer = False
    S.wager = None
    S.turn = 0
    S.scores = {i: 0 for i in range(4)}
    n_c, r = len(S.board["categories"]), n_rows()
    S.daily_double = (random.randrange(n_c), random.randrange(1, r) if r > 1 else 0)
    S.celebrated = False
    S.zoom_step = 0
    S.final_stage = "intro"      # intro -> wager -> clue -> reveal -> done
    S.final_wagers = {}
    for k in list(S.keys()):
        if isinstance(k, str) and k.startswith(("fw_", "fr_")):
            del S[k]
    S.game_snapshot = json.dumps(S.board, sort_keys=True)


if "board" not in S:
    S.board = load_board()
    S.team_names = ["Team 1", "Team 2", "Team 3", "Team 4"]
    S.num_teams = 2
    S.upl_ver = {}
    new_game()


# ----------------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------------
def pick(c, r):
    S.current = (c, r)
    S.show_answer = False
    S.wager = None
    S.zoom_step = 0


def reveal():
    S.show_answer = True


def zoom_out():
    S.zoom_step = min(3, S.zoom_step + 1)


def cancel_clue():
    S.current = None
    S.show_answer = False
    S.wager = None
    S.zoom_step = 0


def resolve(team, correct):
    c, r = S.current
    value = S.wager if S.wager is not None else values()[r]
    if team is not None:
        delta = value if correct else -value
        S.scores[team] += delta
        st.toast(f"{S.team_names[team]}: {'+' if delta > 0 else '−'}${abs(delta):,}",
                 icon="✅" if correct else "❌")
    if S.get("turn_rule") == "Winner keeps control" and team is not None and correct:
        S.turn = team
    else:
        S.turn = (S.turn + 1) % S.num_teams
    S.used.add((c, r))
    S.current = None
    S.show_answer = False
    S.wager = None
    S.zoom_step = 0


def add_row():
    if n_rows() < MAX_ROWS:
        for c in S.board["categories"]:
            c["clues"].append(blank_clue())


def remove_row():
    if n_rows() > MIN_ROWS:
        last = n_rows() - 1
        for c in S.board["categories"]:
            c["clues"].pop()
            clear_clue_keys(c["id"], last)


def add_category():
    if len(S.board["categories"]) < MAX_CATEGORIES:
        S.board["categories"].append(new_category(rows=n_rows()))


def delete_category(cid):
    if len(S.board["categories"]) > 1:
        S.board["categories"] = [c for c in S.board["categories"] if c["id"] != cid]


def move_category(i, step):
    cats = S.board["categories"]
    j = i + step
    if 0 <= j < len(cats):
        cats[i], cats[j] = cats[j], cats[i]


def final_ok():
    f = S.board["final"]
    return f["enabled"] and f["q"].strip() != ""


def eligible_teams():
    """Only teams with a positive score can play Final Jeopardy."""
    return [i for i in range(S.num_teams) if S.scores[i] > 0]


def start_wagers():
    S.final_stage = "wager"


def lock_wagers():
    S.final_wagers = {i: int(S.get(f"fw_{i}", 0) or 0) for i in eligible_teams()}
    S.final_stage = "clue"


def show_final_response():
    S.final_stage = "reveal"


def skip_final():
    S.final_stage = "done"


def finish_final():
    for i, wager in S.final_wagers.items():
        S.scores[i] += wager if S.get(f"fr_{i}") == "✅ Correct" else -wager
    S.final_stage = "done"


def remove_image(cid, r):
    for cat in S.board["categories"]:
        if cat["id"] == cid:
            cat["clues"][r]["img"] = ""
    key = f"{cid}_{r}"
    S.upl_ver[key] = S.upl_ver.get(key, 0) + 1   # fresh, empty uploader
    if f"imgid_{cid}_{r}" in S:
        del S[f"imgid_{cid}_{r}"]


def save_board():
    try:
        SAVE_PATH.write_text(json.dumps(S.board, indent=2))
        st.toast(f"Saved to {SAVE_PATH.name}", icon="💾")
    except OSError as e:
        st.toast(f"Couldn't save: {e}", icon="⚠️")


def reset_to_sample():
    set_board(default_board())


# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;600;700&family=Playfair+Display:wght@700;900&display=swap');

    .stApp {
        background: radial-gradient(ellipse at top, #1a2fb8 0%, #0a1470 45%, #050a38 100%);
        background-attachment: fixed;
    }
    header[data-testid="stHeader"] { background: transparent; }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #050a38, #0a1470);
        border-right: 2px solid rgba(255, 204, 51, .35);
    }

    /* text colours on the dark background */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4,
    [data-testid="stWidgetLabel"] p, [data-testid="stRadio"] p,
    [data-testid="stCaptionContainer"], [data-testid="stExpander"] summary p,
    [data-testid="stMetricLabel"] p, [data-testid="stCheckbox"] p { color: #fff !important; }

    /* inputs: light fields, dark text */
    [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="base-input"] {
        background: #f3f5ff !important; border-radius: 8px !important;
    }
    [data-baseweb="input"] input, [data-baseweb="textarea"] textarea,
    input[type="number"] { color: #0b1250 !important; -webkit-text-fill-color: #0b1250 !important; }

    /* buttons */
    .stApp button[data-testid="stBaseButton-secondary"] {
        background: rgba(255,255,255,.08); color: #fff;
        border: 1px solid rgba(255, 204, 51, .6); border-radius: 10px; font-weight: 600;
        transition: all .15s ease;
    }
    .stApp button[data-testid="stBaseButton-secondary"]:hover {
        background: rgba(255, 204, 51, .18); border-color: #ffcc33; transform: translateY(-1px);
    }
    .stApp button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(180deg, #ffe27a, #ffb700); color: #1a1200;
        border: none; border-radius: 10px; font-weight: 800;
    }
    .stApp button[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.08); transform: translateY(-1px); }
    .stApp button p { color: inherit !important; }

    /* brand + turn pill */
    .brand {
        font-family: 'Anton', Impact, sans-serif; font-size: clamp(2.6rem, 6vw, 4.6rem);
        letter-spacing: .14em; text-align: center; color: #ffcc33; margin: -10px 0 4px;
        text-shadow: 0 4px 0 #8a5a00, 0 8px 18px rgba(0,0,0,.55);
    }
    .turn-wrap { text-align: center; margin-bottom: 18px; }
    .turn-pill {
        display: inline-block; padding: 8px 22px; border-radius: 999px;
        font-family: 'Oswald', sans-serif; font-size: 1.15rem; letter-spacing: .06em;
        color: #ffcc33; border: 2px solid #ffcc33; background: rgba(5,10,56,.6);
        box-shadow: 0 0 18px rgba(255, 204, 51, .35);
    }

    /* board */
    .cat-header {
        height: 96px; display: flex; align-items: center; justify-content: center;
        text-align: center; padding: 6px 10px; border-radius: 10px;
        background: linear-gradient(160deg, #2a46e8, #0d1b9c);
        border: 2px solid #050a38; box-shadow: inset 0 0 0 2px rgba(255,255,255,.12), 0 4px 10px rgba(0,0,0,.4);
        font-family: 'Oswald', sans-serif; font-weight: 700; text-transform: uppercase;
        letter-spacing: .06em; font-size: clamp(.9rem, 1.6vw, 1.45rem); color: #fff;
        text-shadow: 2px 2px 0 rgba(0,0,0,.6);
    }
    .st-key-board button {
        height: 96px; border-radius: 10px !important;
        background: linear-gradient(160deg, #2a46e8, #0f21b0) !important;
        border: 2px solid #050a38 !important; color: #ffcc33 !important;
        box-shadow: inset 0 0 0 2px rgba(255,255,255,.12), 0 4px 10px rgba(0,0,0,.4);
    }
    .st-key-board button p {
        font-family: 'Anton', Impact, sans-serif; font-size: clamp(1.6rem, 3vw, 2.6rem) !important;
        text-shadow: 2px 3px 0 rgba(0,0,0,.6); letter-spacing: .04em;
    }
    .st-key-board button:hover:not(:disabled) {
        transform: translateY(-3px) scale(1.03); filter: brightness(1.25);
        border-color: #ffcc33 !important; box-shadow: 0 0 22px rgba(255, 204, 51, .55);
    }
    .st-key-board button:disabled {
        background: rgba(5, 10, 56, .55) !important; border-color: rgba(255,255,255,.05) !important;
        box-shadow: none; opacity: .5;
    }

    /* clue view */
    .clue-meta { text-align: center; margin-bottom: 10px; }
    .clue-meta span {
        display: inline-block; margin: 0 4px; padding: 6px 16px; border-radius: 999px;
        font-family: 'Oswald', sans-serif; letter-spacing: .08em; text-transform: uppercase;
        background: rgba(5, 10, 56, .65); border: 1px solid rgba(255, 204, 51, .6); color: #ffcc33;
    }
    .clue-meta span.dd {
        background: linear-gradient(180deg, #ffe27a, #ffb700); color: #1a1200; font-weight: 700;
        animation: pulse 1.2s infinite alternate;
    }
    @keyframes pulse { from { box-shadow: 0 0 6px #ffcc33; } to { box-shadow: 0 0 24px #ffcc33; } }
    .clue-card {
        min-height: 320px; display: flex; align-items: center; justify-content: center;
        text-align: center; padding: 40px 48px; margin: 8px 0 18px; border-radius: 16px;
        background: linear-gradient(145deg, #2a46e8, #0a1a8a);
        border: 4px solid #050a38;
        box-shadow: inset 0 0 0 3px rgba(255,255,255,.14), 0 14px 40px rgba(0,0,0,.55);
        font-family: 'Playfair Display', Georgia, serif; font-weight: 900; text-transform: uppercase;
        font-size: clamp(1.5rem, 3.2vw, 2.7rem); line-height: 1.35; color: #fff;
        text-shadow: 3px 3px 0 rgba(0,0,0,.7);
    }
    .answer-card {
        text-align: center; padding: 22px 28px; margin-bottom: 16px; border-radius: 14px;
        background: linear-gradient(180deg, #ffe27a, #ffb700); color: #1a1200;
        font-family: 'Oswald', sans-serif; font-weight: 700; font-size: clamp(1.4rem, 2.6vw, 2.2rem);
        box-shadow: 0 10px 28px rgba(0,0,0,.45);
    }

    /* scoreboard */
    .score-card {
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px 14px; margin-bottom: 10px; border-radius: 12px;
        background: rgba(255,255,255,.07); border-left: 6px solid var(--c);
    }
    .score-card.active {
        background: rgba(255, 204, 51, .16); box-shadow: 0 0 16px rgba(255, 204, 51, .45);
        outline: 1px solid rgba(255, 204, 51, .8);
    }
    .score-name { font-family: 'Oswald', sans-serif; color: #fff; font-size: 1.05rem; letter-spacing: .03em; }
    .score-val { font-family: 'Anton', Impact, sans-serif; color: #ffcc33; font-size: 1.5rem; }
    .score-val.neg { color: #ff8a8a; }

    /* podium */
    .podium {
        display: flex; align-items: center; gap: 18px; padding: 18px 26px; margin-bottom: 12px;
        border-radius: 14px; background: rgba(255,255,255,.08); border-left: 8px solid var(--c);
    }
    .podium.first { background: rgba(255, 204, 51, .18); box-shadow: 0 0 28px rgba(255, 204, 51, .5); }
    .podium .medal { font-size: 2.4rem; }
    .podium .pname { flex: 1; font-family: 'Oswald', sans-serif; font-size: 1.8rem; color: #fff; }
    .podium .pscore { font-family: 'Anton', Impact, sans-serif; font-size: 2.2rem; color: #ffcc33; }

    /* photo clues */
    .photo-frame {
        width: 100%; max-width: calc(var(--maxh) * var(--ar)); aspect-ratio: var(--ar);
        margin: 8px auto 18px; overflow: hidden; border-radius: 16px; background: #000;
        border: 4px solid #050a38; box-shadow: 0 14px 40px rgba(0,0,0,.55), 0 0 0 3px rgba(255,204,51,.45);
    }
    .photo-img {
        display: block; width: 100%; height: 100%; max-width: none;
        transform: scale(var(--z)); transition: transform .6s ease;
    }
    .photo-img.reveal { animation: unzoom 1.6s ease-in-out forwards; }
    @keyframes unzoom { from { transform: scale(var(--z)); } to { transform: scale(1); } }
    .clue-caption {
        text-align: center; margin: 6px 0; color: #fff; font-family: 'Oswald', sans-serif;
        font-size: clamp(1.2rem, 2.2vw, 1.8rem); letter-spacing: .04em; text-transform: uppercase;
        text-shadow: 2px 2px 0 rgba(0,0,0,.6);
    }

    /* editor */
    .page-title {
        font-family: 'Anton', Impact, sans-serif; font-size: 2.6rem; letter-spacing: .1em;
        color: #ffcc33; text-shadow: 0 3px 0 #8a5a00; margin-bottom: 4px;
    }
    .value-chip {
        font-family: 'Anton', Impact, sans-serif; color: #ffcc33; font-size: 1.5rem;
        text-align: center; padding-top: 18px; text-shadow: 2px 2px 0 rgba(0,0,0,.5);
    }
    div[class*="st-key-cat_"] {
        background: rgba(5, 10, 56, .45); border: 1px solid rgba(255, 204, 51, .35);
        border-radius: 14px; padding: 14px;
    }
    .chips span {
        display: inline-block; margin: 2px 4px 2px 0; padding: 3px 12px; border-radius: 999px;
        background: rgba(255,204,51,.15); border: 1px solid rgba(255,204,51,.5); color: #ffcc33;
        font-family: 'Oswald', sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="page-title" style="font-size:2rem">JEOPARDY!</div>', unsafe_allow_html=True)
    mode = st.radio("Mode", ["🎮 Play", "✏️ Edit board"], key="mode", horizontal=True,
                    label_visibility="collapsed")

    with st.expander("👥 Teams", expanded=True):
        st.slider("Number of teams", 1, 4, key="num_teams")
        for i in range(S.num_teams):
            S.team_names[i] = st.text_input(f"Team {i + 1} name", S.team_names[i], key=f"tname_{i}")
        st.radio("Who picks next?", ["Rotate every clue", "Winner keeps control"], key="turn_rule")
    S.turn %= S.num_teams

    st.markdown("#### Scoreboard")
    for i in range(S.num_teams):
        score = S.scores[i]
        active = "active" if i == S.turn else ""
        neg = "neg" if score < 0 else ""
        sign = "−" if score < 0 else ""
        st.markdown(
            f'<div class="score-card {active}" style="--c:{TEAM_COLORS[i]}">'
            f'<span class="score-name">{"👉 " if active else ""}{esc(S.team_names[i])}</span>'
            f'<span class="score-val {neg}">{sign}${abs(score):,}</span></div>',
            unsafe_allow_html=True,
        )
    st.button("🔄 New game", use_container_width=True, on_click=new_game)


# ----------------------------------------------------------------------------
# Play views
# ----------------------------------------------------------------------------
def playable_set():
    return {(c, r)
            for c, cat in enumerate(S.board["categories"])
            for r, clue in enumerate(cat["clues"]) if has_content(clue)}


def board_view():
    cats, vals = S.board["categories"], values()
    st.markdown('<div class="brand">JEOPARDY!</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="turn-wrap"><span class="turn-pill">🎯 {esc(S.team_names[S.turn])}, pick a clue</span></div>',
        unsafe_allow_html=True,
    )
    with st.container(key="board"):
        cols = st.columns(len(cats))
        for c, cat in enumerate(cats):
            cols[c].markdown(f'<div class="cat-header">{esc(cat["name"].strip() or "—")}</div>',
                             unsafe_allow_html=True)
        for r, v in enumerate(vals):
            cols = st.columns(len(cats))
            for c, cat in enumerate(cats):
                gone = (c, r) in S.used or not has_content(cat["clues"][r])
                cols[c].button("\u00a0" if gone else f"${v:,}", key=f"tile_{c}_{r}",
                               disabled=gone, use_container_width=True,
                               on_click=pick, args=(c, r))


def clue_view():
    c, r = S.current
    cat = S.board["categories"][c]
    clue = cat["clues"][r]
    value = values()[r]
    is_dd = (c, r) == S.daily_double

    st.markdown(
        f'<div class="clue-meta"><span>{esc(cat["name"])}</span><span>${value:,}</span>'
        f'{"<span class=dd>⭐ Daily Double!</span>" if is_dd else ""}</div>',
        unsafe_allow_html=True,
    )

    team = st.radio(
        "Who found the Daily Double?" if is_dd else "Who's answering?",
        list(range(S.num_teams)), format_func=lambda i: S.team_names[i],
        horizontal=True, index=S.turn % S.num_teams, key=f"answerer_{c}_{r}",
    )

    if is_dd and S.wager is None:
        max_wager = max(S.scores[team], max(values()))
        wager = st.number_input(f"Wager (up to ${max_wager:,})", min_value=5, max_value=max_wager,
                                value=min(500, max_wager), step=100, key=f"wager_{c}_{r}")
        b1, b2 = st.columns(2)
        if b1.button("Lock in wager", type="primary", use_container_width=True):
            S.wager = int(wager)
            st.rerun()
        b2.button("↩ Back to board", use_container_width=True, on_click=cancel_clue)
        return

    has_img = bool(clue.get("img"))
    if has_img:
        z_cur = 1 + (clue["zoom"] - 1) * (1 - S.zoom_step / 3)
        if clue["q"].strip():
            st.markdown(f'<div class="clue-caption">{esc(clue["q"])}</div>', unsafe_allow_html=True)
        st.markdown(photo_html(clue, round(z_cur, 3), reveal=S.show_answer), unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="clue-card">{esc(clue["q"])}</div>', unsafe_allow_html=True)

    if not S.show_answer:
        if has_img:
            b1, b2, b3 = st.columns([3, 1.6, 1])
            b1.button("👀 Reveal response", type="primary", use_container_width=True, on_click=reveal)
            b2.button("🔍 Zoom out a bit", use_container_width=True, on_click=zoom_out,
                      disabled=S.zoom_step >= 3)
            b3.button("↩ Back", use_container_width=True, on_click=cancel_clue)
        else:
            b1, b2 = st.columns([3, 1])
            b1.button("👀 Reveal response", type="primary", use_container_width=True, on_click=reveal)
            b2.button("↩ Back", use_container_width=True, on_click=cancel_clue)
        return

    st.markdown(f'<div class="answer-card">{esc(clue["a"] or "—")}</div>', unsafe_allow_html=True)
    stake = S.wager if S.wager is not None else value
    b1, b2, b3 = st.columns(3)
    b1.button(f"✅ Correct (+${stake:,})", use_container_width=True, on_click=resolve, args=(team, True))
    b2.button(f"❌ Incorrect (−${stake:,})", use_container_width=True, on_click=resolve, args=(team, False))
    b3.button("⏭️ Nobody got it", use_container_width=True, on_click=resolve, args=(None, False))


def final_view():
    st.markdown('<div class="brand">GAME OVER</div>', unsafe_allow_html=True)
    ranking = sorted(range(S.num_teams), key=lambda i: S.scores[i], reverse=True)
    top = S.scores[ranking[0]]
    medals = ["🥇", "🥈", "🥉", "🎖️"]
    for rank, i in enumerate(ranking):
        score = S.scores[i]
        first = "first" if score == top else ""
        sign = "−" if score < 0 else ""
        st.markdown(
            f'<div class="podium {first}" style="--c:{TEAM_COLORS[i]}">'
            f'<span class="medal">{medals[rank]}</span><span class="pname">{esc(S.team_names[i])}</span>'
            f'<span class="pscore">{sign}${abs(score):,}</span></div>',
            unsafe_allow_html=True,
        )
    if not S.celebrated:
        st.balloons()
        S.celebrated = True


COUNTDOWN_HTML = """
<div style="font-family:Impact,'Anton',sans-serif;text-align:center;color:#fff">
  <div id="t" style="font-size:68px;color:#ffcc33;text-shadow:0 4px 0 #8a5a00">30</div>
  <button id="b" onclick="go()" style="font-size:16px;padding:10px 22px;border-radius:10px;cursor:pointer;
     border:1px solid #ffcc33;background:rgba(255,255,255,.1);color:#fff;font-weight:600">
     ⏱️ Start 30-second timer</button>
</div>
<script>
let n = 30, h = null;
function go() {
  if (h) return;
  document.getElementById('b').style.display = 'none';
  h = setInterval(() => {
    n--;
    const t = document.getElementById('t');
    t.textContent = n;
    if (n <= 10) t.style.color = '#ff6b6b';
    if (n <= 0) { clearInterval(h); t.textContent = "TIME!"; }
  }, 1000);
}
</script>
"""


def final_jeopardy_view():
    fj = S.board["final"]
    stage = S.final_stage
    eligible = eligible_teams()
    cat = esc(fj["category"].strip() or "Final Jeopardy")

    st.markdown('<div class="brand">FINAL JEOPARDY!</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="clue-meta"><span>{cat}</span></div>', unsafe_allow_html=True)

    if stage == "intro":
        st.markdown(f'<div class="clue-card">{cat}</div>', unsafe_allow_html=True)
        if not eligible:
            st.warning("No team has a positive score, so nobody can play Final Jeopardy.")
            st.button("See final results", type="primary", use_container_width=True, on_click=skip_final)
        else:
            names = ", ".join(S.team_names[i] for i in eligible)
            st.markdown(f'<div class="clue-caption">Playing: {esc(names)}</div>', unsafe_allow_html=True)
            st.button("✍️ Start wagering", type="primary", use_container_width=True, on_click=start_wagers)
        return

    if stage == "wager":
        st.markdown(f'<div class="clue-card" style="min-height:160px">{cat}</div>', unsafe_allow_html=True)
        st.caption("Each team wagers up to its score. Keep the screen hidden from other teams while they type!")
        cols = st.columns(len(eligible))
        for col, i in zip(cols, eligible):
            col.number_input(f"{S.team_names[i]} (max ${S.scores[i]:,})", min_value=0,
                             max_value=S.scores[i], value=0, step=100, key=f"fw_{i}")
        st.button("🔒 Lock in wagers & show clue", type="primary", use_container_width=True,
                  on_click=lock_wagers)
        return

    st.markdown(f'<div class="clue-card">{esc(fj["q"])}</div>', unsafe_allow_html=True)

    if stage == "clue":
        components.html(COUNTDOWN_HTML, height=130)
        st.button("👀 Reveal response", type="primary", use_container_width=True,
                  on_click=show_final_response)
        return

    # stage == "reveal"
    st.markdown(f'<div class="answer-card">{esc(fj["a"] or "—")}</div>', unsafe_allow_html=True)
    st.markdown("#### Who got it right?")
    cols = st.columns(len(S.final_wagers))
    for col, (i, wager) in zip(cols, S.final_wagers.items()):
        col.radio(f"{S.team_names[i]} (wagered ${wager:,})", ["✅ Correct", "❌ Incorrect"],
                  index=None, key=f"fr_{i}")
    ready = all(S.get(f"fr_{i}") for i in S.final_wagers)
    st.button("🏁 Finish game", type="primary", use_container_width=True,
              disabled=not ready, on_click=finish_final)


def play_page():
    if json.dumps(S.board, sort_keys=True) != S.game_snapshot:
        new_game()
        st.info("The board was edited, so a fresh game was started.")

    playable = playable_set()
    if not playable:
        st.warning("There are no clues yet. Switch to **✏️ Edit board** to add some.")
        return
    if len(playable) < sum(len(c["clues"]) for c in S.board["categories"]):
        st.caption("Some clue slots are empty and are greyed out on the board.")

    if S.current is not None:
        clue_view()
    elif playable <= S.used:
        if final_ok() and S.final_stage != "done":
            final_jeopardy_view()
        else:
            final_view()
    else:
        board_view()


# ----------------------------------------------------------------------------
# Edit view
# ----------------------------------------------------------------------------
def edit_page():
    st.markdown('<div class="page-title">✏️ Board Editor</div>', unsafe_allow_html=True)
    st.caption("Changes apply instantly. Starting a game after editing resets the scores.")

    # --- save / load -------------------------------------------------------
    with st.expander("💾 Save, load & reset"):
        c1, c2 = st.columns(2)
        c1.button("Save board to file", use_container_width=True, on_click=save_board)
        c1.download_button("⬇️ Download as JSON", json.dumps(S.board, indent=2),
                           file_name="jeopardy_board.json", mime="application/json",
                           use_container_width=True)
        up = c2.file_uploader("Load a board (JSON)", type="json")
        if up is not None and S.get("last_upload") != up.file_id:
            S.last_upload = up.file_id
            try:
                set_board(json.loads(up.getvalue().decode("utf-8")))
                st.toast("Board loaded", icon="📂")
            except Exception:
                st.error("That file isn't a valid board.")
        c2.button("Reset to sample board", use_container_width=True, on_click=reset_to_sample)

    # --- board settings ----------------------------------------------------
    cats = S.board["categories"]
    s1, s2, s3, s4 = st.columns([1.3, 1, 1, 1])
    S.board["base"] = s1.number_input("Value step ($)", min_value=50, max_value=2000, step=50,
                                      value=S.board["base"], key="base_input")
    s2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    s2.button("➕ Add row", use_container_width=True, on_click=add_row, disabled=n_rows() >= MAX_ROWS)
    s3.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    s3.button("➖ Remove last row", use_container_width=True, on_click=remove_row,
              disabled=n_rows() <= MIN_ROWS)
    s4.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    s4.button("➕ Add category", use_container_width=True, on_click=add_category,
              disabled=len(cats) >= MAX_CATEGORIES)

    chips = "".join(f"<span>${v:,}</span>" for v in values())
    st.markdown(f'<div class="chips">Row values: {chips}</div>', unsafe_allow_html=True)
    st.write("")

    # --- categories --------------------------------------------------------
    vals = values()
    for i, cat in enumerate(list(cats)):
        cid = cat["id"]
        with st.container(key=f"cat_{cid}"):
            h = st.columns([6, 0.6, 0.6, 0.6])
            cat["name"] = h[0].text_input("Category name", cat["name"], key=f"catname_{cid}",
                                          placeholder="Category name", label_visibility="collapsed")
            h[1].button("◀", key=f"left_{cid}", help="Move left", disabled=i == 0,
                        on_click=move_category, args=(i, -1))
            h[2].button("▶", key=f"right_{cid}", help="Move right", disabled=i == len(cats) - 1,
                        on_click=move_category, args=(i, 1))
            h[3].button("🗑️", key=f"del_{cid}", help="Delete category", disabled=len(cats) == 1,
                        on_click=delete_category, args=(cid,))

            for r, clue in enumerate(cat["clues"]):
                cols = st.columns([0.9, 4, 2.4])
                cols[0].markdown(f'<div class="value-chip">${vals[r]:,}</div>', unsafe_allow_html=True)
                clue["q"] = cols[1].text_area("Clue", clue["q"], key=f"q_{cid}_{r}", height=80,
                                              placeholder="The clue (optional if you add a photo)…",
                                              label_visibility="collapsed")
                clue["a"] = cols[2].text_area("Response", clue["a"], key=f"a_{cid}_{r}", height=80,
                                              placeholder="What is …?",
                                              label_visibility="collapsed")

                with st.expander("🖼️ Photo clue" + (" ✓" if clue.get("img") else "")):
                    left, right = st.columns(2)
                    ver = S.upl_ver.get(f"{cid}_{r}", 0)
                    up = left.file_uploader("Upload a photo", type=["png", "jpg", "jpeg", "webp"],
                                            key=f"img_{cid}_{r}_{ver}")
                    if up is not None and S.get(f"imgid_{cid}_{r}") != up.file_id:
                        S[f"imgid_{cid}_{r}"] = up.file_id
                        try:
                            clue["img"], clue["ar"] = encode_image(up.getvalue())
                        except Exception:
                            st.error("Couldn't read that image.")
                    if clue.get("img"):
                        clue["zoom"] = left.slider("Starting zoom", 1.5, 12.0, value=float(clue["zoom"]),
                                                   step=0.5, key=f"zoom_{cid}_{r}")
                        clue["fx"] = left.slider("Zoom spot: left ↔ right (%)", 0, 100, value=int(clue["fx"]),
                                                 key=f"fx_{cid}_{r}")
                        clue["fy"] = left.slider("Zoom spot: top ↕ bottom (%)", 0, 100, value=int(clue["fy"]),
                                                 key=f"fy_{cid}_{r}")
                        left.button("🗑️ Remove photo", key=f"rmimg_{cid}_{r}",
                                    on_click=remove_image, args=(cid, r))
                        right.caption("What players see first")
                        right.markdown(photo_html(clue, clue["zoom"], maxh=200), unsafe_allow_html=True)
                        right.caption("Full photo (shown on reveal)")
                        right.markdown(photo_html(clue, 1.0, maxh=200), unsafe_allow_html=True)
                    else:
                        right.caption("Upload a photo, then pick how far to zoom in and which spot to focus on. "
                                      "Players guess from the zoomed view; the host can zoom out in steps "
                                      "or reveal the whole photo.")

    # --- Final Jeopardy ----------------------------------------------------
    st.markdown("### 🏆 Final Jeopardy")
    fj = S.board["final"]
    with st.container(key="cat_final"):
        fj["enabled"] = st.checkbox("Include a Final Jeopardy round", value=fj["enabled"], key="final_on")
        fj["category"] = st.text_input("Final category", fj["category"], key="final_cat",
                                       placeholder="Category")
        fj["q"] = st.text_area("Final clue", fj["q"], key="final_q", height=90,
                               placeholder="The final clue…")
        fj["a"] = st.text_input("Final response", fj["a"], key="final_a", placeholder="What is …?")


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------
if mode.startswith("🎮"):
    play_page()
else:
    edit_page()
