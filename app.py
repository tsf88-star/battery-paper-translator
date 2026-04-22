import re
import streamlit as st
from deep_translator import GoogleTranslator

# ── Post-processing rules derived from corpus analysis (style_guide.txt) ─────
# Each tuple: (regex_pattern, replacement, re_flags)
# Order matters: apply more specific rules before general ones.

RULES = [
    # ── Degradation vocabulary (degrade 109x >> deteriorate 27x >> decay 19x >> fade 11x)
    (r'\bdeterioration\b',  'degradation',   re.IGNORECASE),
    (r'\bdeteriorates\b',   'degrades',      re.IGNORECASE),
    (r'\bdeteriorated\b',   'degraded',      re.IGNORECASE),
    (r'\bdeteriorates\b',   'degrades',      re.IGNORECASE),
    (r'\bdeteriorating\b',  'degrading',     re.IGNORECASE),
    (r'\bdeteriorate\b',    'degrade',       re.IGNORECASE),
    (r'\bdecayed\b',        'degraded',      re.IGNORECASE),
    (r'\bdecays\b',         'degrades',      re.IGNORECASE),
    (r'\bdecay\b(?!\s+rate)', 'degrade',     re.IGNORECASE),  # keep 'decay rate'

    # ── Capitalization fixes
    (r'\bcoulombic efficiency\b',         'Coulombic efficiency',         re.IGNORECASE),
    (r'\binitial coulombic efficiency\b', 'initial Coulombic efficiency', re.IGNORECASE),

    # ── Preferred technical terms (corpus frequency)
    (r'\bcapacity maintenance\b',          'capacity retention',       re.IGNORECASE),
    (r'\bcapacity keeping\b',              'capacity retention',       re.IGNORECASE),
    (r'\bcapacity preservation\b',         'capacity retention',       re.IGNORECASE),
    (r'\bcycling performance\b',           'cycling stability',        re.IGNORECASE),
    (r'\bcycle performance\b',             'cycling stability',        re.IGNORECASE),
    (r'\bcycle stability\b',               'cycling stability',        re.IGNORECASE),
    (r'\brate performance\b',              'rate capability',          re.IGNORECASE),
    (r'\bnegative electrode\b',            'anode',                    re.IGNORECASE),
    (r'\bpositive electrode\b',            'cathode',                  re.IGNORECASE),
    (r'\bsolid electrolyte interface\b',   'solid electrolyte interphase', re.IGNORECASE),
    (r'\bSEI interface\b',                 'SEI layer',                0),
    (r'\bvolume expansion\b',              'volume expansion',         0),  # keep as-is (preferred)
    (r'\bvolumetric swelling\b',           'volume expansion',         re.IGNORECASE),
    (r'\bparticle pulverization\b',        'pulverization',            re.IGNORECASE),
    (r'\bparticle cracking\b',             'cracking',                 re.IGNORECASE),
    (r'\bparticle fragmentation\b',        'pulverization',            re.IGNORECASE),

    # ── Verb preferences (show/exhibit >> demonstrate; improve >> enhance)
    (r'\bdemonstrates a\b',  'shows a',       re.IGNORECASE),
    (r'\bdemonstrated a\b',  'showed a',      re.IGNORECASE),
    (r'\bpresents a\b(?=.*(?:capacity|performance|stability|efficiency))',
                             'exhibits a',    re.IGNORECASE),

    # ── Causal attribution (corpus: "is attributed to" 203x)
    (r'\bis due to\b',       'is attributed to', re.IGNORECASE),
    (r'\bare due to\b',      'are attributed to', re.IGNORECASE),

    # ── Figure formatting
    (r'\bfig\.\s*(\d)',      r'Figure \1',    0),
    (r'\bfig\s+(\d)',        r'Figure \1',    0),

    # ── Intensifier hierarchy (significantly > substantially > markedly)
    (r'\bvery significantly\b', 'significantly', re.IGNORECASE),
    (r'\bquite significantly\b', 'significantly', re.IGNORECASE),

    # ── Remove informal words
    (r'\breally\b',  '', re.IGNORECASE),
    (r'\bvery\b(?=\s+(?:high|low|good|bad|large|small|fast|slow|stable|unstable))',
                     '', re.IGNORECASE),

    # ── Herein / In this work (intro contribution marker)
    (r'\bIn this paper,\b',  'In this work,', 0),
]


def apply_style_rules(text: str) -> str:
    for pattern, repl, flags in RULES:
        if flags:
            text = re.sub(pattern, repl, text, flags=flags)
        else:
            text = re.sub(pattern, repl, text)
    # Clean up double spaces left by removals
    text = re.sub(r'  +', ' ', text)
    return text


def chunk_text(text: str, max_len: int = 4500) -> list:
    """Split at paragraph boundaries to stay under Google Translate limit."""
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > max_len:
            if current:
                chunks.append(current.strip())
            current = para
        else:
            current = (current + '\n\n' + para) if current else para
    if current:
        chunks.append(current.strip())
    return chunks or [text]


def translate(korean_text: str) -> str:
    translator = GoogleTranslator(source='ko', target='en')
    chunks = chunk_text(korean_text)
    translated_parts = []
    for chunk in chunks:
        raw = translator.translate(chunk)
        styled = apply_style_rules(raw)
        translated_parts.append(styled)
    return '\n\n'.join(translated_parts)


# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="맞춤형 논문 번역기 (무료)",
    page_icon="⚗️",
    layout="wide",
)

st.title("⚗️ 맞춤형 논문 번역기")
st.caption("Google Translate + Style Guide 후처리 · **완전 무료** · API 키 불필요")
st.divider()

if "translation" not in st.session_state:
    st.session_state.translation = ""

col_left, col_mid, col_right = st.columns([5, 1, 5])

with col_left:
    st.subheader("🇰🇷 한국어 입력")
    korean_input = st.text_area(
        "korean_input",
        height=520,
        placeholder="번역할 한국어 논문 텍스트를 여기에 붙여넣으세요...",
        label_visibility="collapsed",
    )

with col_mid:
    st.markdown("<br>" * 9, unsafe_allow_html=True)
    clicked = st.button("번역\n→", use_container_width=True, type="primary")

with col_right:
    st.subheader("🇺🇸 영어 번역 결과")

    if clicked:
        if not korean_input.strip():
            st.warning("번역할 텍스트를 왼쪽 창에 입력하세요.")
        else:
            with st.spinner("번역 중..."):
                try:
                    result = translate(korean_input)
                    st.session_state.translation = result
                except Exception as e:
                    st.error(f"번역 오류: {e}")

    if st.session_state.translation:
        st.markdown(st.session_state.translation)
    elif not clicked:
        st.info("왼쪽에 한국어 텍스트를 입력하고 '번역 →' 버튼을 누르세요.")

# ── Applied rules summary ─────────────────────────────────────────────────────
st.divider()
with st.expander("🔧 적용 중인 후처리 규칙 목록"):
    rule_lines = [
        "**[열화 표현]** deteriorate→degrade, decay→degrade  (corpus: degrade 109x >> deteriorate 27x)",
        "**[대문자]** coulombic → Coulombic efficiency",
        "**[선호 용어]** capacity maintenance→retention, negative electrode→anode, positive electrode→cathode",
        "**[인과 표현]** is due to → is attributed to  (corpus: 203x)",
        "**[도표]** fig. N → Figure N",
        "**[서론 마커]** In this paper → In this work",
        "**[불필요 강조어]** very/really 제거",
    ]
    for line in rule_lines:
        st.markdown(f"- {line}")
