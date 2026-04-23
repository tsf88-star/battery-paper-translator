import re
from datetime import datetime
from io import BytesIO
import streamlit as st
from deep_translator import GoogleTranslator
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# ── 스타일 및 번역 규칙 ───────────────────────────────────────────────────────
RULES = [
    (r'\bdeterioration\b', 'degradation', re.IGNORECASE),
    (r'\bdeteriorates\b', 'degrades', re.IGNORECASE),
    (r'\bdeteriorated\b', 'degraded', re.IGNORECASE),
    (r'\bdeteriorating\b', 'degrading', re.IGNORECASE),
    (r'\bdeteriorate\b', 'degrade', re.IGNORECASE),
    (r'\bdecayed\b', 'degraded', re.IGNORECASE),
    (r'\bdecays\b', 'degrades', re.IGNORECASE),
    (r'\bdecay\b(?!\s+rate)', 'degrade', re.IGNORECASE),
    (r'\bcoulombic efficiency\b', 'Coulombic efficiency', re.IGNORECASE),
    (r'\binitial coulombic efficiency\b', 'initial Coulombic efficiency', re.IGNORECASE),
    (r'\bcapacity maintenance\b', 'capacity retention', re.IGNORECASE),
    (r'\bcycling performance\b', 'cycling stability', re.IGNORECASE),
    (r'\brate performance\b', 'rate capability', re.IGNORECASE),
    (r'\bnegative electrode\b', 'anode', re.IGNORECASE),
    (r'\bpositive electrode\b', 'cathode', re.IGNORECASE),
    (r'\bsolid electrolyte interface\b', 'solid electrolyte interphase', re.IGNORECASE),
    (r'\bSEI interface\b', 'SEI layer', 0),
    (r'\bvolumetric swelling\b', 'volume expansion', re.IGNORECASE),
    (r'\bparticle pulverization\b', 'pulverization', re.IGNORECASE),
    (r'\bparticle cracking\b', 'cracking', re.IGNORECASE),
    (r'\bdemonstrates a\b', 'shows a', re.IGNORECASE),
    (r'\bis due to\b', 'is attributed to', re.IGNORECASE),
    (r'\bfig\.\s*(\d)', r'Figure \1', 0),
    (r'\bIn this paper,\b', 'In this work,', 0),
    (r'\bthanks to\b', 'Owing to', re.IGNORECASE),
]

def apply_style_rules(text: str) -> str:
    for pattern, repl, flags in RULES:
        text = re.sub(pattern, repl, text, flags=flags) if flags else re.sub(pattern, repl, text)
    return text

def translate(korean_text: str) -> str:
    translator = GoogleTranslator(source='ko', target='en')
    paras = [p.strip() for p in korean_text.split('\n\n') if p.strip()]
    translated_parts = [apply_style_rules(translator.translate(p)) for p in paras]
    return '\n\n'.join(translated_parts)

# ── 화학식 및 첨자 처리 ───────────────────────────────────────────────────────
_SUP_SUB_PAT = re.compile(
    r'(?<=[.!?])(\d+(?:[,\s\-–−]\s*\d+)*)'  # 1. 인용 (윗첨자)
    r'|(?<=[A-Za-z])([-–−]\d+)'              # 2. 지수 (윗첨자)
    r'|(Li\+)'                               # 3. 리튬 이온
    r'|(?<=[A-Za-z])(\d+)'                   # 4. 화학식 숫자 (아래첨자)
)

def build_docx(text: str) -> bytes:
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)
    style._element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')

    for block in text.split('\n\n'):
        if not block.strip(): continue
        p = doc.add_paragraph()
        
        # 1. 양쪽 맞춤 (Justify)
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        # 2. 줄간격 2.0 (Double)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
        # 3. 첫 줄 들여쓰기: 12pt 글자 기준 2글자 = 24pt
        p.paragraph_format.first_line_indent = Pt(24)
        # 4. 단락 후 간격
        p.paragraph_format.space_after = Pt(12)
        
        pos = 0
        for m in _SUP_SUB_PAT.finditer(block):
            if m.start() > pos:
                _run(p, block[pos:m.start()])
            m1, m2, m3, m4 = m.groups()
            if m1: _run(p, m1, sup=True)
            elif m2: _run(p, m2.replace('-', '–').replace('−', '–'), sup=True)
            elif m3:
                _run(p, "Li")
                _run(p, "+", sup=True)
            elif m4: _run(p, m4, sub=True)
            pos = m.end()
        
        if pos < len(block):
            _run(p, block[pos:])
            
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()

def _run(paragraph, text, sup=False, sub=False):
    run = paragraph.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    if sup: run.font.superscript = True
    if sub: run.font.subscript = True
    return run

def web_display_format(text: str) -> str:
    sup_map = str.maketrans("0123456789+-–−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻⁻")
    sub_map = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    def _repl(m):
        m1, m2, m3, m4 = m.groups()
        if m1: return m1.translate(sup_map)
        if m2: return m2.replace('-', '–').replace('−', '–').translate(sup_map)
        if m3: return "Li⁺"
        if m4: return m4.translate(sub_map)
        return m.group()
    return _SUP_SUB_PAT.sub(_repl, text)

# ── Streamlit UI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="배터리 논문 번역기", page_icon="🔋", layout="wide")
st.title("🔋 배터리 논문 전문 번역기")

if "translation" not in st.session_state: st.session_state.translation = ""

col_left, col_right = st.columns(2)
with col_left:
    korean_input = st.text_area("🇰🇷 한국어 입력", height=500)
    if st.button("번역하기", type="primary", use_container_width=True):
        if korean_input:
            with st.spinner("전문 번역 중..."):
                st.session_state.translation = translate(korean_input)

with col_right:
    if st.session_state.translation:
        st.download_button("📥 Word 다운로드 (12pt, 양쪽맞춤, 2글자들여쓰기)", 
                           data=build_docx(st.session_state.translation), 
                           file_name="translated_paper.docx",
                           use_container_width=True)
        st.markdown(f'<div style="font-family:serif; font-size:1.2rem; text-align:justify; line-height:2.0; padding:20px; background-color:#f9f9f9; border-radius:10px;">'
                    f'{web_display_format(st.session_state.translation).replace("\n", "<br>")}'
                    f'</div>', unsafe_allow_html=True)
    else:
        st.info("번역 결과가 여기에 표시됩니다.")
