
# generator.py
# -*- coding: utf-8 -*-
"""
Legal Answer Generator for Vietnamese Law QA (Gemini)
- Nhận context từ retriever
- Gọi Gemini 2.5 Flash để sinh câu trả lời
- Format:
    1) Trả lời trực tiếp, ngắn gọn, rõ ràng
    2) Nếu có mức phạt → liệt kê theo từng loại đối tượng/phương tiện
    3) Cuối cùng luôn có dòng: "Căn cứ pháp lý: ..." (liệt kê Điều/Khoản/Điểm, không trích nguyên văn)
"""

import os
import re
from typing import List, Tuple

import google.generativeai as genai
from dotenv import load_dotenv


# ===================== ENV & MODEL CONFIG =====================
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY không được thiết lập. Hãy export GEMINI_API_KEY=your_api_key")

genai.configure(api_key=api_key)

# Có thể đổi sang "gemini-2.5-pro" nếu cần chất lượng cao hơn
MODEL_NAME = "gemini-2.5-flash"

GEN_CONFIG = {
    "temperature": 0.1,   # trả lời ổn định, ít bịa
    "top_p": 0.9,
    "top_k": 40,
    "candidate_count": 1,
}
global_model = genai.GenerativeModel(MODEL_NAME)

# ===================== PROMPTS (OPTION B) =====================
SYSTEM_INSTRUCTION = """
Bạn là trợ lý pháp lý tiếng Việt cho lĩnh vực giao thông đường bộ.
Bạn phải trả lời CHÍNH XÁC tuyệt đối dựa trên các đoạn luật được cung cấp trong context.

Quy tắc bắt buộc:
1) Trả lời trực tiếp, ngắn gọn, rõ ràng, dễ hiểu.
2) Nếu liên quan đến mức phạt hoặc nghĩa vụ:
   - Liệt kê rõ theo từng loại đối tượng/phương tiện (nếu có).
   - Ghi rõ khoảng tiền phạt, hình thức xử phạt (nếu context có).
3) Ở cuối câu trả lời, luôn ghi một dòng:
   "Căn cứ pháp lý: ..."
   và liệt kê các căn cứ dạng ngắn gọn:
   - điểm ... khoản ... Điều ... Nghị định ...
   - khoản ... Điều ... Luật ...
   Không trích nguyên văn nội dung luật trong phần "Căn cứ pháp lý".
4) Tuyệt đối KHÔNG bịa thêm điều luật, điều khoản hay mức phạt không xuất hiện trong context.
5) Không đưa lời khuyên pháp lý chủ quan, chỉ diễn giải và hệ thống hóa nội dung từ luật.
6) Nếu trong context KHÔNG có thông tin đủ rõ để trả lời câu hỏi, bạn PHẢI trả lời: 
   "Trong các trích dẫn luật được cung cấp, không có đủ thông tin để trả lời chính xác câu hỏi này."
   và KHÔNG được suy luận thêm ngoài nội dung context.
7) Nếu người dùng hỏi ngoài phạm vi giao thông đường bộ, hãy nói rõ rằng hệ thống chỉ được huấn luyện trên luật giao thông đường bộ và từ chối trả lời.
Mục tiêu: câu trả lời ngắn gọn – chính xác – dùng được ngay.
"""

USER_PROMPT_TMPL = """\
Câu hỏi của người dùng:
{question}

Các đoạn luật (trích từ văn bản pháp luật, bạn PHẢI bám sát):
{context}

Yêu cầu:
- Trước hết hãy trả lời trực tiếp câu hỏi, trình bày mạch lạc, dễ hiểu.
- Nếu câu hỏi có dạng trắc nghiệm (A/B/C/D hoặc 1/2/3/4), bạn PHẢI trả lời theo đúng mẫu:
   "Đáp án đúng: <chỉ 1 ký tự A/B/C/D>"
  và sau đó giải thích ngắn 1–2 câu.
- Nếu câu hỏi liên quan đến mức phạt, trách nhiệm, nghĩa vụ thì hãy liệt kê rõ theo từng trường hợp liên quan trong context (ví dụ: theo loại xe, đối tượng vi phạm, hành vi...).
- Ở cuối câu trả lời, thêm một dòng riêng:
  "Căn cứ pháp lý: ..." 
  và liệt kê gạch đầu dòng các căn cứ pháp lý dựa trên thông tin trong dòng [Căn cứ: ...] ở đầu mỗi đoạn luật.
  Ví dụ: nếu thấy "[Căn cứ: khoản 4 Điều 2 Luật số 35/2024/QH15]" thì ghi "khoản 4 Điều 2 Luật số 35/2024/QH15".
- Không được viện dẫn bất kỳ căn cứ nào không có trong các đoạn luật ở trên.
"""


# ===================== UTILS =====================
def _dedupe_sources(sources: List[str]) -> List[str]:
    """Loại bỏ trùng citation, giữ thứ tự xuất hiện đầu tiên."""
    seen = set()
    out: List[str] = []
    for s in sources:
        key = re.sub(r"\s+", " ", s.strip().lower())
        if key and key not in seen:
            out.append(s)
            seen.add(key)
    return out


def _truncate_context(ctx: str, max_chars: int = 20000) -> str:
    """Giới hạn độ dài context để tránh quá token."""
    if len(ctx) <= max_chars:
        return ctx
    return ctx[:max_chars] + "\n… (đã cắt ngắn context do quá dài)"


def _build_prompt(question: str, context: str) -> str:
    return USER_PROMPT_TMPL.format(question=question.strip(), context=context.strip())


# ===================== CORE FUNCTION =====================
def generate_answer(question: str, context: str, sources: List[str] = None) -> Tuple[str, List[str]]:
    """
    Generate answer from question and context using Gemini
    
    Args:
        question: User question
        context: Retrieved context text
        sources: List of source citations
    
    Returns:
        (answer_text, sources_list)
    """
    import time

    # Validate context
    if not context.strip() or len(context) < 300:
        return "Trong các trích dẫn luật được cung cấp, không có đủ thông tin để trả lời chính xác câu hỏi này.", []

    truncated_context = _truncate_context(context, max_chars=20000)
    sources = _dedupe_sources(sources or [])

    # Generate answer with Gemini
    qa_model = genai.GenerativeModel(
        MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
        generation_config=GEN_CONFIG,
    )
    prompt = _build_prompt(question, truncated_context)

    try:
        t0 = time.time()
        resp = qa_model.generate_content(prompt)
        print(f"⏱️  Gemini API time: {time.time() - t0:.2f}s")
        text = (resp.text or "").strip()
        if not text:
            text = "Không tìm thấy đủ thông tin trong các văn bản luật đã được lập chỉ mục để trả lời câu hỏi này."
    except Exception as e:
        text = f"Lỗi khi gọi Gemini API: {e}"
    # # =========================
    # # FIX format "Căn cứ pháp lý" (Đã sửa)
    # # =========================
    # m = re.search(r"Căn cứ pháp lý:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
    # if m:
    #     raw = m.group(1).strip() # Lấy toàn bộ phần căn cứ bị hỏng

    #     # Bước 1: Dọn dẹp, loại bỏ các dấu gạch đầu dòng và xuống dòng không cần thiết
    #     # Biến tất cả thành một chuỗi duy nhất, ngăn cách bằng dấu cách
    #     cleaned_raw = re.sub(r"[\n-]", " ", raw)
    #     cleaned_raw = re.sub(r"\s+", " ", cleaned_raw).strip()
        
    #     # cleaned_raw bây giờ sẽ là:
    #     # "điểm g khoản 2 Điều 7 Nghị định số 168/2024/NĐ-CP khoản 1 Điều 33 Luật số 36/2024/QH15 điểm a ..."

    #     # Bước 2: Tách chuỗi đã dọn dẹp dựa trên các từ khóa bắt đầu một căn cứ
    #     # (sử dụng positive lookahead '(?=...)' để giữ lại từ khóa)
    #     refs = re.split(r"(?=(điểm|khoản|Điều)\s)", cleaned_raw, flags=re.IGNORECASE)

    #     # refs bâyB giờ sẽ là:
    #     # ['', 'điểm g khoản 2 Điều 7 Nghị định số 168/2024/NĐ-CP ', 'khoản 1 Điều 33 Luật số 36/2024/QH15 ', ...]

    #     # Bước 3: Định dạng lại danh sách
    #     formatted_refs = []
    #     for r in refs:
    #         cleaned_ref = r.strip()
    #         if cleaned_ref: # Bỏ qua các chuỗi rỗng
    #             # Chuẩn hóa (viết thường chữ cái đầu)
    #             cleaned_ref = cleaned_ref[0].lower() + cleaned_ref[1:]
    #             formatted_refs.append(f"- {cleaned_ref}")

    #     # Bước 4: Thay thế đoạn text cũ bằng đoạn đã định dạng
    #     if formatted_refs:
    #         formatted = "Căn cứ pháp lý:\n" + "\n".join(formatted_refs)
    #         text = re.sub(r"Căn cứ pháp lý:.*", formatted, text, flags=re.IGNORECASE | re.DOTALL)
    # Return: answer + sources
    return text, sources
# --- Phần thêm mới cho Quiz ---
import json
from backend.prompts import QUIZ_PROMPT
def generate_quiz(context_text: str, num_questions: int = 5):
    """
    Sinh câu hỏi trắc nghiệm từ context.
    Sử dụng 'global_model' đã khai báo ở trên.
    """
    try:
        # 1. Tạo prompt từ template
        final_prompt = QUIZ_PROMPT.format(
            num_questions=num_questions,
            context=context_text
        )

        # 2. Gọi Gemini (Sử dụng global_model)
        # Ép kiểu trả về JSON để code dễ xử lý
        response = global_model.generate_content(
            final_prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # 3. Parse JSON
        quiz_data = json.loads(response.text)
        return quiz_data

    except Exception as e:
        print(f"❌ Lỗi khi sinh Quiz: {e}")
        return []