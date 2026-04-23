import re
from datetime import datetime
from io import BytesIO
import streamlit as st
from deep_translator import GoogleTranslator
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# ── [고강도] GPT 냄새 제거 및 배터리 논문 스타일 교정 규칙 ──────────────────────
# 스타일 파일(merged_corpus)과 교수님 피드백을 반영한 강제 치환 목록
RULES = [
    # 1. GPT 특유의 화려한 미사여구 제거 (Battery Paper Style로 교체)
    (r'\bunprecedented demands\b', 'stringent requirements', re.IGNORECASE),
    (r'\bremarkable capacity\b', 'outstanding specific capacity', re.IGNORECASE),
    (r'\bplaced unprecedented demands on\b', 'imposed stringent requirements on', re.IGNORECASE),
    (r'\bpaving the way for\b', 'providing a pathway for', re.IGNORECASE),
    (r'\bundermines its practical deployment\b', 'limits its practical viability', re.IGNORECASE),
    (r'\bculminating in\b', 'resulting in', re.IGNORECASE),
    (r'\bunderscore the need\b', 'highlight the necessity', re.IGNORECASE),
    (r'\bAt a loading of only\b', 'With a trace loading of', re.IGNORECASE),
    (r'\bdisproportionate set of\b', 'significant', re.IGNORECASE),
    
    # 2. 교수님 절대 선호 어휘 (degrade, exhibit, attribute)
    (r'\bfading\b', 'degradation', re.IGNORECASE), # capacity fading -> capacity degradation
    (r'\bdeteriorat\w*\b', 'degrad', re.IGNORECASE),
    (r'\bdecay\w*\b', 'degrad', re.IGNORECASE),
    (r'\bfad(e|es|ed|ing)\b', 'degrad$1', re.IGNORECASE),
    (r'\bdemonstrate(s|d)?\b', 'exhibit$1', re.IGNORECASE),
    (r'\bshow(s|ed)?\b', 'exhibit$1', re.IGNORECASE),
    (r'\brepresent(s|ed)?\b', 'act$1 as', re.IGNORECASE),
    
    # 3. 인과관계 및 원인 귀속 (is attributed to)
    (r'\b(?:is|are) due to\b', 'is attributed to', re.IGNORECASE),
    (r'\b(?:is|are) caused by\b', 'is attributed to', re.IGNORECASE),
    (r'\bowing to\b', 'attributed to', re.IGNORECASE),
    (r'\bthanks to\b', 'owing to', re.IGNORECASE),
    (r'\bgive(s)? rise to\b', 'lead$1 to', re.IGNORECASE),
    
    # 4. 성능 관련 (enhance 선호)
    (r'\bimprove(s|d)?\b', 'enhance$1', re.IGNORECASE),
    (r'\bboost(s|ed)?\b', 'enhance$1', re.IGNORECASE),
    
    # 5. 문장 연결 및 접속사 (학술적 권장)
    (r'\bYet\b', 'However,', re.IGNORECASE),
    (r'\bAlso,\b', 'Furthermore,', 0),
    (r'\bBut,\b', 'However,', 0),
    (r'\bIn this paper\b', 'In this work', re.IGNORECASE),
    (r'\bfig\.\b', 'Figure', re.IGNORECASE),
    
    # 6. 배터리 전문 용어
    (r'\bnegative electrode\b', 'anode', re.IGNORECASE),
    (r'\bpositive electrode\b', 'cathode', re.IGNORECASE),
    (r'\bcoulombic efficiency\b', 'Coulombic efficiency', 0),
    (r'\bice\b(?=\s+is)', 'initial Coulombic efficiency (ICE)', re.IGNORECASE),
]

def apply_academic_refinement(text: str) -> str:
    # 1. 고강도 규칙 적용
    for pattern, repl, flags in RULES:
        text = re.sub(pattern, repl, text, flags=flags) if flags else re.sub(pattern, repl, text)
    
    # 2. Si-based 등 하이픈 자동 교정
    text = re.sub(r'\b(\w+)\s+based(?!\s+on)\b', r'\1-based', text, flags=re.IGNORECASE)
    
    # 3. 중복 공백 및 문장 마침표 처리
    text = re.sub(r'  +', ' ', text)
    return text

def translate(korean_text: str) -> str:
    # 한국어 입력 시 번역 + 교정
    if any(ord(c) > 128 for c in korean_text[:100]):
        translator = GoogleTranslator(source='ko', target='en')
        paras = [p.strip() for p in korean_text.split('\n\n') if p.strip()]
        return '\n\n'.join([apply_academic_refinement(translator.translate(p)) for p in paras])
    # 영어 입력 시 'GPT 냄새 제거' 전용 교정 모드
    else:
        paras = [p.strip() for p in korean_text.split('\n\n') if p.strip()]
        return '\n\n'.join([apply_academic_refinement(p) for p in paras])

# ── Word & UI 로직 (12pt, 양쪽맞춤, 2글자들여쓰기 강제) ─────────────────────
_SUP_SUB_PAT = re.compile(r'(?<=[.!?])(\d+(?:[,\s\-–−]\s*\d+)*)|(?<=[A-Za-z])([-–−]\d+)|(Li\+)|(?<=[A-Za-z])(\d+)')

def build_docx(text: str) -> bytes:
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)
    style._element.rPr.rFonts.set(qn('w:eastAsia'), 'Times New Roman')
    for block in text.split('\n\n'):
        if not block.strip(): continue
        p = doc.add_paragraph()
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
        p.paragraph_format.first_line_indent = Pt(24) # 2글자 들여쓰기
        p.paragraph_format.space_after = Pt(12)
        pos = 0
        for m in _SUP_SUB_PAT.finditer(block):
            if m.start() > pos: _run(p, block[pos:m.start()])
            m1, m2, m3, m4 = m.groups()
            if m1: _run(p, m1, sup=True)
            elif m2: _run(p, m2.replace('-', '–').replace('−', '–'), sup=True)
            elif m3:
                _run(p, "Li")
                _run(p, "+", sup=True)
            elif m4: _run(p, m4, sub=True)
            pos = m.end()
        if pos < len(block): _run(p, block[pos:])
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

# ── Streamlit UI ──────────────────────────────────────────────────────────
st.set_page_config(page_title="논문 스타일 교정기", page_icon="🔋", layout="wide")
st.title("🔋 배터리 논문 스타일 교정 및 번역")
st.markdown("입력된 텍스트에서 **GPT 특유의 미사여구를 제거**하고 **교수님 선호 문체**로 강제 교정합니다.")

if "translation" not in st.session_state: st.session_state.translation = ""

col_left, col_right = st.columns(2)
with col_left:
    user_input = st.text_area("텍스트 입력 (한글: 번역+교정 / 영어: 스타일 교정)", height=550)
    if st.button("스타일 교정 및 번역 실행", type="primary", use_container_width=True):
        if user_input:
            with st.spinner("GPT 냄새 제거 및 스타일 교정 중..."):
                st.session_state.translation = translate(user_input)

with col_right:
    if st.session_state.translation:
        st.download_button("📥 Word 다운로드 (12pt, 양쪽맞춤, 2글자들여쓰기)", 
                           data=build_docx(st.session_state.translation), 
                           file_name="battery_paper_style.docx",
                           use_container_width=True)
        st.markdown(f'<div style="font-family:serif; font-size:1.15rem; text-align:justify; line-height:2.0; padding:25px; background-color:#ffffff; border:1px solid #ddd; border-radius:10px; color:#111;">'
                    f'{web_display_format(st.session_state.translation).replace("\n", "<br>")}'
                    f'</div>', unsafe_allow_html=True)
    else: st.info("교정 결과가 여기에 표시됩니다.")
