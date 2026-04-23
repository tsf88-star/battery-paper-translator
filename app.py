import re
from datetime import datetime
from io import BytesIO
import streamlit as st
from deep_translator import GoogleTranslator
from docx import Document
from docx.shared import Pt

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

    # ── Colloquial / non-academic phrases → formal equivalents
    (r'\bthanks to\b',              'Owing to',           re.IGNORECASE),
    (r'\bAs a result of this\b',    'Consequently',       re.IGNORECASE),
    (r'\bIn addition to this,\b',   'Furthermore,',       re.IGNORECASE),
    (r'\bSo,\b',                    'Therefore,',         0),
    (r'\bso,\b',                    'therefore,',         0),
    (r'\bgot\b',                    'obtained',           re.IGNORECASE),
    (r'\bgets\b',                   'is obtained',        re.IGNORECASE),

    # ── Academic register (corpus frequency preference)
    (r'\busually\b',                'typically',               re.IGNORECASE),
    (r'\bmainstream\b',             'predominant',             re.IGNORECASE),
    (r'\btakes advantage of\b',     'leverages',               re.IGNORECASE),
    (r'\bunder realistic\b',        'under practical',         re.IGNORECASE),
    (r'\bfundamentally limits\b',   'fundamentally constrains', re.IGNORECASE),

    # ── Battery / materials science technical terms
    (r'\bfast-charging performance\b', 'fast-charging capability', re.IGNORECASE),
    (r'\bfast charging\b',          'fast-charging',           re.IGNORECASE),
    (r'\binherent problems\b',      'intrinsic challenges',    re.IGNORECASE),
    (r'\blow cycle life\b',         'poor cyclability',        re.IGNORECASE),
    (r'\bshort cycle life\b',       'limited cyclability',     re.IGNORECASE),
    (r'\blong lifespan\b',          'long cycle life',         re.IGNORECASE),
    (r'\blong service life\b',      'long cycle life',         re.IGNORECASE),
    (r'\bstructural stability\b',   'structural integrity',    re.IGNORECASE),
    (r'\bpoor conductivity\b',      'low electrical conductivity', re.IGNORECASE),
    (r'\belectrical resistance\b',  'internal resistance',     re.IGNORECASE),
]


# ── Compound-modifier hyphenation ("Si based" → "Si-based") ──────────────────
# Skips predicative forms: "is based on", "are based on", etc.
_SKIP_BASED = frozenset({'is', 'are', 'was', 'were', 'be', 'being', 'been', 'not'})


def fix_hyphenation(text: str) -> str:
    def _repl(m):
        word = m.group(1)
        return m.group(0) if word.lower() in _SKIP_BASED else f'{word}-based'
    return re.sub(r'\b(\w+)\s+based(?!\s+on)\b', _repl, text, flags=re.IGNORECASE)


# ── Serial-predicate splitter ─────────────────────────────────────────────────
# Detects "Subj V1 O1, V2 O2, and V3 O3." and converts to
# "Subj V1 O1 and V2 O2. It also V3 O3."
# Only fires when both the comma-preceding clause and the "and" clause
# start with an academic action verb.

_AV = (
    r'(?:(?:effectively|significantly|greatly|markedly|substantially|'
    r'considerably|directly|largely|successfully)\s+)?'
    r'(?:suppress|accommodate|alleviate|improve|enhance|reduce|increase|'
    r'provide|enable|prevent|facilitate|allow|promote|inhibit|maintain|'
    r'retain|achieve|generate|produce|form|stabilize|strengthen|mitigate|'
    r'minimize|maximize|demonstrate|exhibit|show|offer|deliver|create|'
    r'modify|restrict|extend|limit|accelerate|buffer|absorb|distribute|'
    r'transfer|conduct|store|release|trap|anchor|bind|coat|protect|'
    r'diffuse|migrate|deposit|dissolve|expand|contract|crack|fracture|'
    r'initiate|propagate|intercalate|grow|shrink|contribute|lead|'
    r'affect|influence|control|determine|govern|activate|deactivate|'
    r'degrade|boost|lower|raise|elevate|eliminate|induce|trigger|'
    r'decrease|prevent|promote)[a-z]*'
)
_AND_VERB = re.compile(r',\s+and\s+(' + _AV + r')(.*?)([.!?])$', re.IGNORECASE)
_COMMA_VERB = re.compile(_AV, re.IGNORECASE)


def _fix_triple_predicate(sent: str) -> str:
    m = _AND_VERB.search(sent)
    if not m:
        return sent
    before_and = sent[:m.start()]
    last_comma = before_and.rfind(',')
    if last_comma < 0:
        return sent
    after_last_comma = before_and[last_comma + 1:].lstrip()
    if not _COMMA_VERB.match(after_last_comma):
        return sent
    first_part = before_and[:last_comma] + ' and ' + after_last_comma
    third_clause = m.group(1) + m.group(2)
    end = m.group(3)
    return first_part.rstrip() + end + ' It also ' + third_clause.strip() + end


def fix_serial_predicates(text: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return ' '.join(_fix_triple_predicate(s) for s in sentences)


def apply_style_rules(text: str) -> str:
    for pattern, repl, flags in RULES:
        if flags:
            text = re.sub(pattern, repl, text, flags=flags)
        else:
            text = re.sub(pattern, repl, text)
    text = re.sub(r'  +', ' ', text)
    text = fix_hyphenation(text)
    text = fix_serial_predicates(text)
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


# ── Word export with superscript formatting ───────────────────────────────────
# Detects two superscript patterns:
#   1) Citation numbers right after sentence-end punctuation: "conditions.1, 2"
#   2) Unit exponents after a letter: "g–1", "cm–2", "mA g–1"
_SUP_PAT = re.compile(
    r'(?<=[.!?])(\d+(?:[,\s\-–−]\s*\d+)*)'  # citations: ".1, 2" or ".9-11"
    r'|(?<=[A-Za-z])([-–−]\d+)',              # exponents: "g–1", "cm–2"
)


def build_docx(text: str) -> bytes:
    doc = Document()
    for block in text.split('\n\n'):
        block = block.strip().replace('\n', ' ')
        if not block:
            continue
        p = doc.add_paragraph()
        pos = 0
        for m in _SUP_PAT.finditer(block):
            if m.start() > pos:
                _run(p, block[pos:m.start()])
            _run(p, m.group(), superscript=True)
            pos = m.end()
        if pos < len(block):
            _run(p, block[pos:])
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _run(paragraph, text, superscript=False):
    run = paragraph.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(11)
    if superscript:
        run.font.superscript = True
    return run


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
if "history" not in st.session_state:
    st.session_state.history = []

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
                    st.session_state.history.insert(0, {
                        "korean": korean_input,
                        "english": result,
                        "time": datetime.now().strftime("%m/%d %H:%M"),
                    })
                    st.session_state.history = st.session_state.history[:20]
                except Exception as e:
                    st.error(f"번역 오류: {e}")

    if st.session_state.translation:
        st.download_button(
            "Word 파일 다운로드 (.docx)",
            data=build_docx(st.session_state.translation),
            file_name="translated_paper.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
        st.markdown(st.session_state.translation)
    elif not clicked:
        st.info("왼쪽에 한국어 텍스트를 입력하고 '번역 →' 버튼을 누르세요.")

# ── 번역 내역 사이드바 ────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("번역 내역")
    if st.session_state.history:
        if st.button("내역 전체 삭제", use_container_width=True):
            st.session_state.history = []
            st.rerun()
        st.divider()
        for i, item in enumerate(st.session_state.history):
            preview = item["korean"].replace("\n", " ")[:35]
            with st.expander(f"{item['time']} · {preview}…"):
                st.caption("한국어 원문")
                st.text(item["korean"])
                st.caption("영어 번역")
                st.text(item["english"])
    else:
        st.caption("번역하면 여기에 내역이 표시됩니다.")

