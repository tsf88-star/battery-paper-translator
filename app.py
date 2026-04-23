import re
from datetime import datetime
from io import BytesIO
import streamlit as st
from deep_translator import GoogleTranslator
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# ── [고강도] 스타일 교정 규칙 및 설명 ──────────────────────────────────────────
# (패턴, 교체어, 설명)
RULES = [
    (r'\bunprecedented demands\b', 'stringent requirements', 'GPT 미사여구 제거 (unprecedented -> stringent)'),
    (r'\bremarkable capacity\b', 'outstanding specific capacity', 'GPT 미사여구 제거 (remarkable -> outstanding)'),
    (r'\bplaced unprecedented demands on\b', 'imposed stringent requirements on', 'GPT 미사여구 제거'),
    (r'\bpaving the way for\b', 'providing a pathway for', '학술적 표현으로 교정'),
    (r'\bundermines its practical deployment\b', 'limits its practical viability', '학술적 표현으로 교정'),
    (r'\bculminating in\b', 'resulting in', 'GPT 냄새 제거 (culminating -> resulting)'),
    (r'\bunderscore the need\b', 'highlight the necessity', '학술적 동사로 교체'),
    (r'\bAt a loading of only\b', 'With a trace loading of', '표현 고도화'),
    (r'\bdisproportionate set of\b', 'significant', '불필요한 수식어 압축'),
    (r'\bfading\b', 'degradation', '교수님 선호 (fading -> degradation)'),
    (r'\bdeteriorat\w*\b', 'degrad', '교수님 선호 (deteriorate -> degrade)'),
    (r'\bdecay\w*\b', 'degrad', '교수님 선호 (decay -> degrade)'),
    (r'\bfad(e|es|ed|ing)\b', 'degrad$1', '교수님 선호 (fade -> degrade)'),
    (r'\bdemonstrate(s|d)?\b', 'exhibit$1', '결과 보고 동사 교정 (demonstrate -> exhibit)'),
    (r'\bshow(s|ed)?\b', 'exhibit$1', '결과 보고 동사 교정 (show -> exhibit)'),
    (r'\brepresent(s|ed)?\b', 'act$1 as', '능동적 표현으로 교정 (represent -> act as)'),
    (r'\b(?:is|are) due to\b', 'is attributed to', '원인 귀속 구문 고도화 (due to -> attributed to)'),
    (r'\b(?:is|are) caused by\b', 'is attributed to', '원인 귀속 구문 고도화'),
    (r'\bowing to\b', 'attributed to', '원인 귀속 구문 고도화'),
    (r'\bthanks to\b', 'owing to', '학술적 표현으로 교환'),
    (r'\bgive(s)? rise to\b', 'lead$1 to', '간결한 표현으로 교환'),
    (r'\binduce(s|d)?\b', 'trigger$1', '동사 선택 고도화'),
    (r'\bimprove(s|d)?\b', 'enhance$1', '교수님 선호 (improve -> enhance)'),
    (r'\bboost(s|ed)?\b', 'enhance$1', '교수님 선호 (boost -> enhance)'),
    (r'\bAlso,\b', 'Furthermore,', '문장 연결어 격상'),
    (r'\bBut,\b', 'However,', '문장 연결어 격상'),
    (r'\bYet\b', 'However,', '문장 연결어 격상'),
    (r'\bIn this paper\b', 'In this work', '관례적 표현 교정'),
    (r'\bfig\.\b', 'Figure', '약어 풀어서 표기'),
    (r'\bnegative electrode\b', 'anode', '배터리 전문 용어 고정'),
    (r'\bpositive electrode\b', 'cathode', '배터리 전문 용어 고정'),
]

def refine_with_log(text):
    changes = []
    refined_text = text
    for pattern, repl, desc in RULES:
        if re.search(pattern, refined_text, re.IGNORECASE):
            # 실제 바뀐 단어 확인을 위해 매칭된 부분 저장
            matches = re.findall(pattern, refined_text, re.IGNORECASE)
            if matches:
                changes.append(f"✅ {desc}")
                refined_text = re.sub(pattern, repl, refined_text, flags=re.IGNORECASE)
    
    # 하이픈 규칙 등 자동 교정
    if re.search(r'\b(\w+)\s+based(?!\s+on)\b', refined_text, re.IGNORECASE):
        changes.append("✅ 하이픈 자동 교정 (e.g., Si based -> Si-based)")
        refined_text = re.sub(r'\b(\w+)\s+based(?!\s+on)\b', r'\1-based', refined_text, flags=re.IGNORECASE)
    
    return refined_text, list(set(changes))

def translate(text):
    is_korean = any(ord(c) > 128 for c in text[:100])
    if is_korean:
        raw = GoogleTranslator(source='ko', target='en').translate(text)
    else:
        raw = text
    return refine_with_log(raw)

# ── Word & UI 로직 ──────────────────────────────────────────────────────────
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
        p.paragraph_format.first_line_indent = Pt(24)
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

# ── UI ───────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="논문 스타일 교정기", page_icon="🔋", layout="wide")
st.title("🔋 배터리 논문 스타일 교정 및 번역")

if "translation" not in st.session_state: st.session_state.translation = ""
if "changes" not in st.session_state: st.session_state.changes = []

col_left, col_right = st.columns(2)
with col_left:
    user_input = st.text_area("텍스트 입력 (한글/영어)", height=500)
    if st.button("교정 실행", type="primary", use_container_width=True):
        if user_input:
            with st.spinner("스타일 분석 및 교정 중..."):
                res, logs = translate(user_input)
                st.session_state.translation = res
                st.session_state.changes = logs

with col_right:
    if st.session_state.translation:
        tab1, tab2 = st.tabs(["✨ 교정 완료 본문", "📝 스타일 수정 사항"])
        
        with tab1:
            st.download_button("📥 Word 다운로드", data=build_docx(st.session_state.translation), file_name="refined_paper.docx")
            st.markdown(f'<div style="font-family:serif; font-size:1.15rem; text-align:justify; line-height:2.0; padding:25px; background-color:#ffffff; border:1px solid #ddd; border-radius:10px; color:#111;">'
                        f'{web_display_format(st.session_state.translation).replace("\n", "<br>")}'
                        f'</div>', unsafe_allow_html=True)
        
        with tab2:
            if st.session_state.changes:
                for change in st.session_state.changes:
                    st.info(change)
            else:
                st.success("수정 사항 없음: 이미 완벽한 배터리 논문 스타일입니다!")
    else:
        st.info("결과가 여기에 표시됩니다.")
