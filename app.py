import re
import difflib
from io import BytesIO
import streamlit as st
from deep_translator import GoogleTranslator
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# ── 스타일 교정 규칙 ──────────────────────────────────────────────────────────
RULES = [
    # ── Degradation vocabulary (degrade >> deteriorate >> decay >> fade)
    (r'\bdeterioration\b',          'degradation',                  re.IGNORECASE),
    (r'\bdeteriorates\b',           'degrades',                     re.IGNORECASE),
    (r'\bdeteriorated\b',           'degraded',                     re.IGNORECASE),
    (r'\bdeteriorating\b',          'degrading',                    re.IGNORECASE),
    (r'\bdeteriorate\b',            'degrade',                      re.IGNORECASE),
    (r'\bdecayed\b',                'degraded',                     re.IGNORECASE),
    (r'\bdecays\b',                 'degrades',                     re.IGNORECASE),
    (r'\bdecay\b(?!\s+rate)',        'degrade',                      re.IGNORECASE),
    (r'\bfaded\b(?=.*capacity)',     'degraded',                     re.IGNORECASE),
    # ── Capitalization
    (r'\binitial coulombic efficiency\b', 'initial Coulombic efficiency', re.IGNORECASE),
    (r'\bcoulombic efficiency\b',    'Coulombic efficiency',         re.IGNORECASE),
    # ── Technical terms
    (r'\bcapacity maintenance\b',    'capacity retention',           re.IGNORECASE),
    (r'\bcapacity keeping\b',        'capacity retention',           re.IGNORECASE),
    (r'\bcapacity preservation\b',   'capacity retention',           re.IGNORECASE),
    (r'\bcycling performance\b',     'cycling stability',            re.IGNORECASE),
    (r'\bcycle performance\b',       'cycling stability',            re.IGNORECASE),
    (r'\bcycle stability\b',         'cycling stability',            re.IGNORECASE),
    (r'\brate performance\b',        'rate capability',              re.IGNORECASE),
    (r'\bnegative electrode\b',      'anode',                        re.IGNORECASE),
    (r'\bpositive electrode\b',      'cathode',                      re.IGNORECASE),
    (r'\bsolid electrolyte interface\b', 'solid electrolyte interphase', re.IGNORECASE),
    (r'\bSEI interface\b',           'SEI layer',                    0),
    (r'\bvolumetric swelling\b',     'volume expansion',             re.IGNORECASE),
    (r'\bvolumetric expansion\b',    'volume expansion',             re.IGNORECASE),
    (r'\bparticle pulverization\b',  'pulverization',                re.IGNORECASE),
    (r'\bparticle cracking\b',       'cracking',                     re.IGNORECASE),
    (r'\bparticle fragmentation\b',  'pulverization',                re.IGNORECASE),
    (r'\bstructural stability\b',    'structural integrity',         re.IGNORECASE),
    (r'\blow cycle life\b',          'poor cyclability',             re.IGNORECASE),
    (r'\bshort cycle life\b',        'limited cyclability',          re.IGNORECASE),
    (r'\blong lifespan\b',           'long cycle life',              re.IGNORECASE),
    (r'\bpoor conductivity\b',       'low electrical conductivity',  re.IGNORECASE),
    (r'\bfast charging\b',           'fast-charging',                re.IGNORECASE),
    (r'\bSi based\b',                'Si-based',                     0),
    (r'\bcarbon based\b',            'carbon-based',                 re.IGNORECASE),
    (r'\bgraphene based\b',          'graphene-based',               re.IGNORECASE),
    # ── Verb preferences
    (r'\bdemonstrates a\b',          'shows a',                      re.IGNORECASE),
    (r'\bdemonstrated a\b',          'showed a',                     re.IGNORECASE),
    (r'\bpresents a\b',              'exhibits a',                   re.IGNORECASE),
    # ── Causal attribution
    (r'\bis due to\b',               'is attributed to',             re.IGNORECASE),
    (r'\bare due to\b',              'are attributed to',            re.IGNORECASE),
    (r'\bresulted from\b',           'arose from',                   re.IGNORECASE),
    # ── Figure formatting
    (r'\bfig\.\s*(\d)',              r'Figure \1',                   0),
    (r'\bfig\s+(\d)',                r'Figure \1',                   0),
    # ── Introduction / Conclusion markers (Rules 3 & 4)
    (r'\bIn this paper,',            'In this work,',                0),
    (r'\bin this paper,',            'in this work,',                0),
    (r'\bIn conclusion,',            'In summary,',                  0),
    (r'\bIn conclusions,',           'In summary,',                  0),
    (r'(?m)^But\b',                  'However,',                     0),
    (r'(?<=[.!?] )But\b',            'However,',                     0),
    # ── Self-reference: "the authors" → "we"
    (r'\bthe authors\b',             'we',                           re.IGNORECASE),
    (r'\bthe present authors\b',     'we',                           re.IGNORECASE),
    (r'\bthe present study\b',       'this work',                    re.IGNORECASE),
    # ── Contractions (Rule 10 – no contractions in formal writing)
    (r"\bit's\b",                    'it is',                        re.IGNORECASE),
    (r"\bdon't\b",                   'do not',                       re.IGNORECASE),
    (r"\bcan't\b",                   'cannot',                       re.IGNORECASE),
    (r"\bisn't\b",                   'is not',                       re.IGNORECASE),
    (r"\bwasn't\b",                  'was not',                      re.IGNORECASE),
    (r"\baren't\b",                  'are not',                      re.IGNORECASE),
    (r"\bweren't\b",                 'were not',                     re.IGNORECASE),
    (r"\bwon't\b",                   'will not',                     re.IGNORECASE),
    (r"\bdidn't\b",                  'did not',                      re.IGNORECASE),
    (r"\bhasn't\b",                  'has not',                      re.IGNORECASE),
    (r"\bhaven't\b",                 'have not',                     re.IGNORECASE),
    (r"\bdoesn't\b",                 'does not',                     re.IGNORECASE),
    # ── Informal / weak words (Rule 10)
    (r'\ba lot of\b',                'significant',                  re.IGNORECASE),
    (r'\blots of\b',                 'numerous',                     re.IGNORECASE),
    (r'\bthanks to\b',               'owing to',                     re.IGNORECASE),
    (r'\bSo,\b',                     'Therefore,',                   0),
    (r'\bso,\b',                     'therefore,',                   0),
    (r'\bgot\b',                     'obtained',                     re.IGNORECASE),
    (r'\busually\b',                 'typically',                    re.IGNORECASE),
    (r'\bvery significantly\b',      'significantly',                re.IGNORECASE),
    (r'\bquite\b',                   '',                             re.IGNORECASE),
    (r'\breally\b',                  '',                             re.IGNORECASE),
    (r'\bvery high\b',               'significantly high',           re.IGNORECASE),
    (r'\bvery low\b',                'significantly low',            re.IGNORECASE),
    (r'\bvery large\b',              'substantially large',          re.IGNORECASE),
    (r'\bvery small\b',              'considerably small',           re.IGNORECASE),
    (r'\bvery fast\b',               'markedly fast',                re.IGNORECASE),
    (r'\bvery stable\b',             'highly stable',                re.IGNORECASE),
    (r'\bvery good\b',               'excellent',                    re.IGNORECASE),
    # ── Register / formality
    (r'\bAs a result of this\b',     'Consequently',                 re.IGNORECASE),
    (r'\bIn addition to this,\b',    'Furthermore,',                 re.IGNORECASE),
    (r'\btakes advantage of\b',      'leverages',                    re.IGNORECASE),
    (r'\binherent problems\b',       'intrinsic challenges',         re.IGNORECASE),
    (r'\bmainstream\b',              'predominant',                  re.IGNORECASE),
]


# ── Serial-predicate splitter ─────────────────────────────────────────────────
# "X suppresses A, improves B, and enhances C." →
# "X suppresses A and improves B. It also enhances C."
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
    r'decrease|promote)[a-z]*'
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
        text = re.sub(pattern, repl, text, flags=flags) if flags else re.sub(pattern, repl, text)
    text = re.sub(r'  +', ' ', text)
    text = fix_serial_predicates(text)
    return text


def count_corrections(original: str, corrected: str) -> int:
    """Count approximate number of individual corrections made."""
    matcher = difflib.SequenceMatcher(None, original.split(), corrected.split())
    return sum(1 for op, *_ in matcher.get_opcodes() if op != 'equal')


def highlight_diff_html(original: str, corrected: str) -> str:
    """Character-level diff as HTML with red deletions and green insertions."""
    matcher = difflib.SequenceMatcher(None, original, corrected, autojunk=False)
    parts = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            parts.append(original[i1:i2].replace('\n', '<br>'))
        elif op == 'replace':
            parts.append(
                f'<del style="background:#ffd0d0;color:#a00;text-decoration:line-through;">'
                f'{original[i1:i2].replace(chr(10), "<br>")}</del>'
                f'<ins style="background:#d0ffd0;color:#060;text-decoration:none;font-style:normal;">'
                f'{corrected[j1:j2].replace(chr(10), "<br>")}</ins>'
            )
        elif op == 'delete':
            parts.append(
                f'<del style="background:#ffd0d0;color:#a00;text-decoration:line-through;">'
                f'{original[i1:i2].replace(chr(10), "<br>")}</del>'
            )
        elif op == 'insert':
            parts.append(
                f'<ins style="background:#d0ffd0;color:#060;text-decoration:none;font-style:normal;">'
                f'{corrected[j1:j2].replace(chr(10), "<br>")}</ins>'
            )
    return ''.join(parts)


# ── 한국어 배터리 용어 선치환 ─────────────────────────────────────────────────
_KO_TERMS = [
    ('양극 활물질',       'cathode active material'),
    ('양극활물질',        'cathode active material'),
    ('음극 활물질',       'anode active material'),
    ('음극활물질',        'anode active material'),
    ('양극재',            'cathode material'),
    ('음극재',            'anode material'),
    ('양극',              'cathode'),
    ('음극',              'anode'),
    ('전해질',            'electrolyte'),
    ('집전체',            'current collector'),
    ('바인더',            'binder'),
    ('활물질',            'active material'),
    ('초기 쿨롱 효율',    'initial Coulombic efficiency'),
    ('쿨롱 효율',         'Coulombic efficiency'),
    ('용량유지율',        'capacity retention'),
    ('용량 유지율',       'capacity retention'),
    ('율특성',            'rate capability'),
    ('부피팽창',          'volume expansion'),
    ('부피 팽창',         'volume expansion'),
    ('분쇄',              'pulverization'),
    ('전기화학적',        'electrochemical'),
    ('고체 전해질 계면',  'solid electrolyte interphase'),
    ('SEI막',             'SEI layer'),
    ('SEI 막',            'SEI layer'),
]


def is_korean(text: str) -> bool:
    korean_chars = sum(1 for c in text if '가' <= c <= '힣' or 'ᄀ' <= c <= 'ᇿ')
    return korean_chars >= 10


def preprocess_korean(text: str) -> str:
    for ko, en in _KO_TERMS:
        text = text.replace(ko, en)
    return text


def process(input_text: str):
    """Returns (original_en, corrected, mode)."""
    if is_korean(input_text):
        preprocessed = preprocess_korean(input_text)
        translator = GoogleTranslator(source='ko', target='en')
        paras = [p.strip() for p in preprocessed.split('\n\n') if p.strip()]
        translated = '\n\n'.join(translator.translate(p) for p in paras)
        corrected = apply_style_rules(translated)
        return translated, corrected, 'translate'
    else:
        corrected = apply_style_rules(input_text)
        return input_text, corrected, 'edit'


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

for key in ('original_en', 'corrected', 'mode'):
    if key not in st.session_state:
        st.session_state[key] = ''

col_left, col_right = st.columns(2)

with col_left:
    user_input = st.text_area(
        "입력 (한국어 또는 영어)",
        height=500,
        placeholder="한국어 → 번역 후 스타일 교정\n영어 → 스타일 교정만 적용\n\n텍스트를 붙여넣고 버튼을 누르세요.",
    )

    if st.button("번역 / 교정하기", type="primary", use_container_width=True):
        if user_input.strip():
            with st.spinner("처리 중..."):
                try:
                    orig, corr, mode = process(user_input)
                    st.session_state.original_en = orig
                    st.session_state.corrected = corr
                    st.session_state.mode = mode
                except Exception as e:
                    st.error(f"오류: {e}")

with col_right:
    if st.session_state.corrected:
        orig = st.session_state.original_en
        corr = st.session_state.corrected
        mode = st.session_state.mode
        n_corrections = count_corrections(orig, corr)

        if mode == 'translate':
            st.success(f"번역 완료 · 스타일 교정 {n_corrections}건")
        else:
            if n_corrections == 0:
                st.warning("교정 사항 없음 — 이미 논문 스타일에 맞는 표현입니다.")
            else:
                st.success(f"교정 완료 · {n_corrections}건 수정")

        st.download_button(
            "📥 Word 다운로드",
            data=build_docx(corr),
            file_name="paper_output.docx",
            use_container_width=True,
        )

        # 영어 교정 모드: diff 탭 / 결과만 탭 분리
        if mode == 'edit' and n_corrections > 0:
            tab_diff, tab_clean = st.tabs(["🔍 변경사항 표시", "📄 교정본만 보기"])
            with tab_diff:
                diff_html = highlight_diff_html(orig, corr)
                st.markdown(
                    f'<div style="font-family:serif;font-size:1.05rem;line-height:2.0;'
                    f'padding:20px;background:#fafafa;border-radius:10px;">'
                    f'{diff_html}</div>',
                    unsafe_allow_html=True,
                )
            with tab_clean:
                st.markdown(
                    f'<div style="font-family:serif;font-size:1.05rem;text-align:justify;'
                    f'line-height:2.0;padding:20px;background:#fafafa;border-radius:10px;">'
                    f'{web_display_format(corr).replace(chr(10), "<br>")}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f'<div style="font-family:serif;font-size:1.05rem;text-align:justify;'
                f'line-height:2.0;padding:20px;background:#fafafa;border-radius:10px;">'
                f'{web_display_format(corr).replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("결과가 여기에 표시됩니다.")
