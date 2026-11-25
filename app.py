import random
import streamlit as st

st.set_page_config(page_title="Jeopardy!", page_icon="❓", layout="wide")

# ----------------------------------------------------------------------------
# Game data: edit this to make your own board. 5 values per category.
# Each clue is (clue, response).
# ----------------------------------------------------------------------------
VALUES = [200, 400, 600, 800, 1000]

BOARD = {
    "Python": [
        ("This keyword is used to define a function in Python.", "What is def?"),
        ("This built-in function returns the number of items in a list.", "What is len()?"),
        ("Python's package installer, whose name is a recursive acronym.", "What is pip?"),
        ("This data structure stores key-value pairs inside curly braces.", "What is a dictionary?"),
        ("Python is named after this British comedy troupe.", "Who are Monty Python?"),
    ],
    "Geography": [
        ("This city on the Seine is the capital of France.", "What is Paris?"),
        ("The longest river in Africa.", "What is the Nile?"),
        ("This South American country is the largest by land area.", "What is Brazil?"),
        ("The smallest country in the world by area.", "What is Vatican City?"),
        ("Earth's highest mountain above sea level.", "What is Mount Everest?"),
    ],
    "Science": [
        ("H2O is the chemical formula for this.", "What is water?"),
        ("This planet is known as the Red Planet.", "What is Mars?"),
        ("This gas makes up about 78% of Earth's atmosphere.", "What is nitrogen?"),
        ("This organelle is called the powerhouse of the cell.", "What are mitochondria?"),
        ("This physicist published the theory of general relativity in 1915.", "Who is Albert Einstein?"),
    ],
    "Movies": [
        ("In this 1997 film, Jack and Rose sail on a doomed ocean liner.", "What is Titanic?"),
        ("This green ogre stars in a DreamWorks animated franchise.", "Who is Shrek?"),
        ("This director made Jaws, E.T., and Jurassic Park.", "Who is Steven Spielberg?"),
        ("'Life is like a box of chocolates' comes from this 1994 film.", "What is Forrest Gump?"),
        ("In this 1999 sci-fi film, Neo takes the red pill.", "What is The Matrix?"),
    ],
    "Food": [
        ("This Italian dish is topped with tomato sauce and mozzarella.", "What is pizza?"),
        ("Sushi rolls are traditionally wrapped in this dried seaweed.", "What is nori?"),
        ("This world's priciest spice by weight comes from crocus flowers.", "What is saffron?"),
        ("This crescent-shaped French pastry is flaky and buttery.", "What is a croissant?"),
        ("This spicy fermented Korean cabbage dish is a staple side.", "What is kimchi?"),
    ],
}

CATEGORIES = list(BOARD.keys())
TOTAL_CLUES = len(CATEGORIES) * len(VALUES)

# ----------------------------------------------------------------------------
# Styling
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .cat-header {
        background: #0b1f8f; color: #fff; text-align: center; font-weight: 800;
        text-transform: uppercase; letter-spacing: .05em; padding: 22px 6px;
        border-radius: 8px; border: 2px solid #000; min-height: 80px;
        display: flex; align-items: center; justify-content: center;
    }
    div[data-testid="stButton"] > button[kind="secondary"] {
        background: #1a35c9; color: #ffd24a; font-size: 2rem; font-weight: 900;
        height: 90px; border: 2px solid #000; border-radius: 8px;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:hover {
        background: #2f4bff; color: #fff; border-color: #ffd24a;
    }
    div[data-testid="stButton"] > button[kind="secondary"]:disabled {
        background: #0a0f3a; color: #0a0f3a; border-color: #0a0f3a; opacity: .5;
    }
    .clue-card {
        background: #0b1f8f; color: #fff; padding: 60px 40px; border-radius: 12px;
        text-align: center; font-size: 2.2rem; font-weight: 700; line-height: 1.3;
        border: 3px solid #000; text-transform: uppercase; margin-bottom: 16px;
    }
    .clue-meta { color: #ffd24a; font-size: 1.1rem; margin-bottom: 8px; }
    .answer-card {
        background: #ffd24a; color: #111; padding: 24px; border-radius: 12px;
        text-align: center; font-size: 1.8rem; font-weight: 800; margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
def init_state(num_teams=2):
    st.session_state.used = set()
    st.session_state.current = None      # (cat_index, value_index)
    st.session_state.show_answer = False
    st.session_state.wager = None
    st.session_state.scores = {i: 0 for i in range(4)}
    st.session_state.daily_double = (
        random.randrange(len(CATEGORIES)),
        random.randrange(1, len(VALUES)),  # not on the cheapest row
    )
    st.session_state.celebrated = False


if "used" not in st.session_state:
    init_state()
    st.session_state.team_names = ["Team 1", "Team 2", "Team 3", "Team 4"]

S = st.session_state

# ----------------------------------------------------------------------------
# Sidebar: teams & scores
# ----------------------------------------------------------------------------
with st.sidebar:
    st.header("Players")
    num_teams = st.slider("Number of teams", 1, 4, 2)
    for i in range(num_teams):
        S.team_names[i] = st.text_input(f"Team {i + 1} name", S.team_names[i], key=f"name_{i}")

    st.divider()
    st.subheader("Scoreboard")
    for i in range(num_teams):
        st.metric(S.team_names[i], f"${S.scores[i]:,}")

    st.divider()
    if st.button("🔄 New game", use_container_width=True):
        init_state()
        st.rerun()


# ----------------------------------------------------------------------------
# Callbacks
# ----------------------------------------------------------------------------
def pick(c, r):
    S.current = (c, r)
    S.show_answer = False
    S.wager = None


def resolve(team, correct):
    c, r = S.current
    value = S.wager if S.wager is not None else VALUES[r]
    if team is not None:
        S.scores[team] += value if correct else -value
    S.used.add((c, r))
    S.current = None
    S.show_answer = False
    S.wager = None


def reveal():
    S.show_answer = True


# ----------------------------------------------------------------------------
# Views
# ----------------------------------------------------------------------------
def show_board():
    st.title("❓ Jeopardy!")
    cols = st.columns(len(CATEGORIES))
    for c, cat in enumerate(CATEGORIES):
        cols[c].markdown(f'<div class="cat-header">{cat}</div>', unsafe_allow_html=True)

    for r, value in enumerate(VALUES):
        cols = st.columns(len(CATEGORIES))
        for c in range(len(CATEGORIES)):
            used = (c, r) in S.used
            cols[c].button(
                "" if used else f"${value}",
                key=f"tile_{c}_{r}",
                disabled=used,
                use_container_width=True,
                on_click=pick,
                args=(c, r),
            )


def show_clue():
    c, r = S.current
    clue, response = BOARD[CATEGORIES[c]][r]
    is_dd = (c, r) == S.daily_double
    value = VALUES[r]

    st.markdown(
        f'<div class="clue-meta">{CATEGORIES[c].upper()} for ${value}'
        f'{" — 🎉 DAILY DOUBLE!" if is_dd else ""}</div>',
        unsafe_allow_html=True,
    )

    # Who is answering?
    team_options = list(range(num_teams))
    team = st.radio(
        "Who's answering?" if not is_dd else "Who found the Daily Double?",
        team_options,
        format_func=lambda i: S.team_names[i],
        horizontal=True,
        key=f"answerer_{c}_{r}",
    )

    # Daily Double wager gate
    if is_dd and S.wager is None:
        max_wager = max(S.scores[team], 1000)
        wager = st.number_input(
            f"Wager (up to ${max_wager:,})", min_value=5, max_value=max_wager,
            value=min(500, max_wager), step=100, key=f"wager_{c}_{r}",
        )
        if st.button("Lock in wager", type="primary"):
            S.wager = int(wager)
            st.rerun()
        return

    st.markdown(f'<div class="clue-card">{clue}</div>', unsafe_allow_html=True)

    if not S.show_answer:
        st.button("👀 Reveal response", on_click=reveal, type="primary", use_container_width=True)
        return

    st.markdown(f'<div class="answer-card">{response}</div>', unsafe_allow_html=True)
    stake = S.wager if S.wager is not None else value
    b1, b2, b3 = st.columns(3)
    b1.button(f"✅ Correct (+${stake:,})", use_container_width=True,
              on_click=resolve, args=(team, True))
    b2.button(f"❌ Incorrect (−${stake:,})", use_container_width=True,
              on_click=resolve, args=(team, False))
    b3.button("⏭️ Nobody got it", use_container_width=True,
              on_click=resolve, args=(None, False))


def show_final():
    st.title("🏆 Game Over!")
    ranking = sorted(range(num_teams), key=lambda i: S.scores[i], reverse=True)
    top = S.scores[ranking[0]]
    winners = [S.team_names[i] for i in ranking if S.scores[i] == top]
    st.header(("Winner: " if len(winners) == 1 else "It's a tie: ") + " & ".join(winners))
    for rank, i in enumerate(ranking, 1):
        st.subheader(f"{rank}. {S.team_names[i]} — ${S.scores[i]:,}")
    if not S.celebrated:
        st.balloons()
        S.celebrated = True


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------
if S.current is not None:
    show_clue()
elif len(S.used) == TOTAL_CLUES:
    show_final()
else:
    show_board()
