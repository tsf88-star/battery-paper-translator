import re
from io import BytesIO
import streamlit as st
from deep_translator import GoogleTranslator
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# ── 스타일 교정 규칙 (corpus 분석 기반) ──────────────────────────────────────
RULES = [
    # Degradation vocabulary
    (r'\bdeterioration\b',  'degradation',              re.IGNORECASE),
    (r'\bdeteriorates\b',   'degrades',                 re.IGNORECASE),
    (r'\bdeteriorated\b',   'degraded',                 re.IGNORECASE),
    (r'\bdeteriorating\b',  'degrading',                re.IGNORECASE),
    (r'\bdeteriorate\b',    'degrade',                  re.IGNORECASE),
    (r'\bdecayed\b',        'degraded',                 re.IGNORECASE),
    (r'\bdecays\b',         'degrades',                 re.IGNORECASE),
    (r'\bdecay\b(?!\s+rate)', 'degrade',               re.IGNORECASE),
    # Capitalization
    (r'\binitial coulombic efficiency\b', 'initial Coulombic efficiency', re.IGNORECASE),
    (r'\bcoulombic efficiency\b',         'Coulombic efficiency',         re.IGNORECASE),
    # Preferred technical terms
    (r'\bcapacity maintenance\b',   'capacity retention',           re.IGNORECASE),
    (r'\bcapacity keeping\b',       'capacity retention',           re.IGNORECASE),
    (r'\bcapacity preservation\b',  'capacity retention',           re.IGNORECASE),
    (r'\bcycling performance\b',    'cycling stability',            re.IGNORECASE),
    (r'\bcycle performance\b',      'cycling stability',            re.IGNORECASE),
    (r'\bcycle stability\b',        'cycling stability',            re.IGNORECASE),
    (r'\brate performance\b',       'rate capability',              re.IGNORECASE),
    (r'\bnegative electrode\b',     'anode',                        re.IGNORECASE),
    (r'\bpositive electrode\b',     'cathode',                      re.IGNORECASE),
    (r'\bsolid electrolyte interface\b', 'solid electrolyte interphase', re.IGNORECASE),
    (r'\bSEI interface\b',          'SEI layer',                    0),
    (r'\bvolumetric swelling\b',    'volume expansion',             re.IGNORECASE),
    (r'\bparticle pulverization\b', 'pulverization',                re.IGNORECASE),
    (r'\bparticle cracking\b',      'cracking',                     re.IGNORECASE),
    (r'\bparticle fragmentation\b', 'pulverization',                re.IGNORECASE),
    (r'\bstructural stability\b',   'structural integrity',         re.IGNORECASE),
    (r'\blow cycle life\b',         'poor cyclability',             re.IGNORECASE),
    (r'\bshort cycle life\b',       'limited cyclability',          re.IGNORECASE),
    (r'\blong lifespan\b',          'long cycle life',              re.IGNORECASE),
    (r'\bpoor conductivity\b',      'low electrical conductivity',  re.IGNORECASE),
    (r'\bfast charging\b',          'fast-charging',                re.IGNORECASE),
    # Verb preferences
    (r'\bdemonstrates a\b',         'shows a',                      re.IGNORECASE),
    (r'\bdemonstrated a\b',         'showed a',                     re.IGNORECASE),
    # Causal attribution
    (r'\bis due to\b',              'is attributed to',             re.IGNORECASE),
    (r'\bare due to\b',             'are attributed to',            re.IGNORECASE),
    # Figure formatting
    (r'\bfig\.\s*(\d)',             r'Figure \1',                   0),
    (r'\bfig\s+(\d)',               r'Figure \1',                   0),
    # Colloquial → formal
    (r'\bIn this paper,\b',         'In this work,',                0),
    (r'\bthanks to\b',              'Owing to',                     re.IGNORECASE),
    (r'\bAs a result of this\b',    'Consequently',                 re.IGNORECASE),
    (r'\bSo,\b',                    'Therefore,',                   0),
    (r'\bso,\b',                    'therefore,',                   0),
    (r'\bgot\b',                    'obtained',                     re.IGNORECASE),
    (r'\busually\b',                'typically',                    re.IGNORECASE),
    # Intensifiers
    (r'\bvery significantly\b',     'significantly',                re.IGNORECASE),
    (r'\bquite significantly\b',    'significantly',                re.IGNORECASE),
    (r'\breally\b',                 '',                             re.IGNORECASE),
]

# ── 한국어 배터리 용어 선치환 (번역 전) ──────────────────────────────────────
# 길이가 긴 표현을 먼저 처리해야 하위 단어가 덮어쓰이지 않음
_KO_TERMS = [
    ('양극 활물질',      'cathode active material'),
    ('양극활물질',       'cathode active material'),
    ('음극 활물질',      'anode active material'),
    ('음극활물질',       'anode active material'),
    ('양극재',           'cathode material'),
    ('음극재',           'anode material'),
    ('양극',             'cathode'),
    ('음극',             'anode'),
    ('전해질',           'electrolyte'),
    ('집전체',           'current collector'),
    ('바인더',           'binder'),
    ('활물질',           'active material'),
    ('초기 쿨롱 효율',   'initial Coulombic efficiency'),
    ('쿨롱 효율',        'Coulombic efficiency'),
    ('용량유지율',       'capacity retention'),
    ('용량 유지율',      'capacity retention'),
    ('율특성',           'rate capability'),
    ('부피팽창',         'volume expansion'),
    ('부피 팽창',        'volume expansion'),
    ('분쇄',             'pulverization'),
    ('전기화학적',       'electrochemical'),
    ('고체 전해질 계면', 'solid electrolyte interphase'),
    ('SEI막',            'SEI layer'),
    ('SEI 막',           'SEI layer'),
]


def is_korean(text: str) -> bool:
    """텍스트에 한글이 10자 이상 포함돼 있으면 한국어로 판단."""
    korean_chars = sum(1 for c in text if '가' <= c <= '힣' or 'ᄀ' <= c <= 'ᇿ')
    return korean_chars >= 10


def preprocess_korean(text: str) -> str:
    for ko, en in _KO_TERMS:
        text = text.replace(ko, en)
    return text


def apply_style_rules(text: str) -> str:
    for pattern, repl, flags in RULES:
        text = re.sub(pattern, repl, text, flags=flags) if flags else re.sub(pattern, repl, text)
    text = re.sub(r'  +', ' ', text)
    return text


def process(input_text: str) -> tuple[str, str]:
    """
    Returns (result_text, mode) where mode is 'translate' or 'edit'.
    Korean input → translate + style correction.
    English input → style correction only.
    """
    if is_korean(input_text):
        preprocessed = preprocess_korean(input_text)
        translator = GoogleTranslator(source='ko', target='en')
        paras = [p.strip() for p in preprocessed.split('\n\n') if p.strip()]
        result = '\n\n'.join(apply_style_rules(translator.translate(p)) for p in paras)
        return result, 'translate'
    else:
        paras = [p.strip() for p in input_text.split('\n\n') if p.strip()]
        result = '\n\n'.join(apply_style_rules(p) for p in paras)
        return result, 'edit'


# ── 첨자 패턴 ────────────────────────────────────────────────────────────────
_SUP_SUB_PAT = re.compile(
    r'(?<=[.!?])(\d+(?:[,\s\-–−]\s*\d+)*)'
    r'|(?<=[A-Za-z])([-–−]\d+)'
    r'|(Li\+)'
    r'|(?<=[A-Za-z])(\d+)'
)


def _run(paragraph, text, sup=False, sub=False):
    run = paragraph.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    if sup: run.font.superscript = True
    if sub: run.font.subscript = True
    return run


def build_docx(text: str) -> bytes:
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)
    style._element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')

    for block in text.split('\n\n'):
        if not block.strip():
            continue
        p = doc.add_paragraph()
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
        p.paragraph_format.first_line_indent = Pt(24)
        p.paragraph_format.space_after = Pt(12)

        pos = 0
        for m in _SUP_SUB_PAT.finditer(block):
            if m.start() > pos:
                _run(p, block[pos:m.start()])
            m1, m2, m3, m4 = m.groups()
            if m1:   _run(p, m1, sup=True)
            elif m2: _run(p, m2.replace('-', '–').replace('−', '–'), sup=True)
            elif m3: _run(p, 'Li'); _run(p, '+', sup=True)
            elif m4: _run(p, m4, sub=True)
            pos = m.end()
        if pos < len(block):
            _run(p, block[pos:])

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def web_display_format(text: str) -> str:
    sup_map = str.maketrans('0123456789+-–−', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻')
    sub_map = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
    def _repl(m):
        m1, m2, m3, m4 = m.groups()
        if m1: return m1.translate(sup_map)
        if m2: return m2.replace('-', '–').replace('−', '–').translate(sup_map)
        if m3: return 'Li⁺'
        if m4: return m4.translate(sub_map)
        return m.group()
    return _SUP_SUB_PAT.sub(_repl, text)


# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="배터리 논문 번역기", page_icon="🔋", layout="wide")
st.title("🔋 배터리 논문 전문 번역기")
st.caption("한국어 → 번역 + 스타일 교정 · 영어 → 스타일 교정만 · 완전 무료")

if 'result' not in st.session_state:
    st.session_state.result = ''
if 'mode' not in st.session_state:
    st.session_state.mode = ''

col_left, col_right = st.columns(2)

with col_left:
    user_input = st.text_area(
        "입력 (한국어 또는 영어)",
        height=500,
        placeholder="한국어: 번역 후 스타일 교정\n영어: 스타일 교정만 적용\n\n텍스트를 붙여넣고 버튼을 누르세요.",
    )

    # 입력 감지해서 버튼 라벨 동적으로 변경
    if user_input and is_korean(user_input):
        btn_label = "번역 + 교정하기 🇰🇷→🇺🇸"
    elif user_input:
        btn_label = "영어 교정하기 ✏️"
    else:
        btn_label = "번역 / 교정하기"

    if st.button(btn_label, type="primary", use_container_width=True):
        if user_input.strip():
            with st.spinner("처리 중..."):
                try:
                    result, mode = process(user_input)
                    st.session_state.result = result
                    st.session_state.mode = mode
                except Exception as e:
                    st.error(f"오류: {e}")

with col_right:
    if st.session_state.result:
        # 모드 뱃지
        if st.session_state.mode == 'translate':
            st.success("번역 완료 (한국어 → 영어 + 스타일 교정)")
        else:
            st.info("교정 완료 (영어 스타일 교정)")

        st.download_button(
            "📥 Word 다운로드 (12pt, 양쪽맞춤, 2칸 들여쓰기)",
            data=build_docx(st.session_state.result),
            file_name="paper_output.docx",
            use_container_width=True,
        )
        st.markdown(
            f'<div style="font-family:serif; font-size:1.1rem; text-align:justify; '
            f'line-height:2.0; padding:20px; background-color:#f9f9f9; border-radius:10px;">'
            f'{web_display_format(st.session_state.result).replace(chr(10), "<br>")}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.info("결과가 여기에 표시됩니다.")
