import json
import time

# Import lại đồ nghề cũ
from backend.retriever_custom import retrieve  # Dùng lại hàm tìm kiếm xịn sò của bạn
from backend.generator import generate_quiz    # Hàm sinh quiz vừa viết thêm

def make_quiz_pipeline(topic: str, num_questions: int = 3):
    print(f"\n🔎 Đang tìm kiếm các điều luật về: '{topic}'...")
    start_time = time.time()

    # 1. RETRIEVAL (Gọi với raw=True)
    # Lúc này results sẽ là một List các Dictionary
    relevant_chunks = retrieve(topic, k=5, raw=True)

    if not relevant_chunks:
        print("⚠️ Không tìm thấy văn bản luật nào phù hợp!")
        return []

    print(f"✅ Tìm thấy {len(relevant_chunks)} đoạn luật liên quan.")

    # 2. CHUẨN BỊ CONTEXT
    # Cấu trúc của relevant_chunks bây giờ là: [{'props': {...}, 'score': ...}, ...]
    # Nội dung text nằm trong key 'props' -> 'enriched_text'
    
    context_list = []
    for item in relevant_chunks:
        # Lấy phần props (properties)
        props = item.get('props', {})
        # Lấy text
        text = props.get('enriched_text', '')
        if text:
            context_list.append(text)

    if not context_list:
        print("⚠️ Dữ liệu luật tìm thấy bị rỗng!")
        return []

    context_str = "\n\n".join(context_list)

    print("🧠 Đang yêu cầu Gemini sinh câu hỏi...")
    
    # 3. GENERATION
    quiz_json = generate_quiz(context_str, num_questions)
    
    elapsed = time.time() - start_time
    print(f"🎉 Hoàn thành trong {elapsed:.2f} giây!\n")
    
    return quiz_json

# --- Phần chạy thử (Main) ---
if __name__ == "__main__":
    print("="*50)
    print("🤖 HỆ THỐNG SINH ĐỀ THI TRẮC NGHIỆM PHÁP LUẬT")
    print("="*50)

    while True:
        user_topic = input("\nNhập chủ đề muốn tạo câu hỏi (hoặc 'exit' để thoát): ")
        if user_topic.lower() in ["exit", "quit"]:
            break
            
        # Chạy pipeline
        questions = make_quiz_pipeline(user_topic, num_questions=3)

        # In kết quả đẹp mắt
        if questions:
            for i, q in enumerate(questions, 1):
                print(f"\n--- Câu hỏi {i}: {q.get('question')} ---")
                options = q.get('options', {})
                for key, value in options.items():
                    print(f"   {key}. {value}")
                print(f"   👉 ĐÁP ÁN ĐÚNG: {q.get('correct_answer')}")
                print(f"   ℹ️ Giải thích: {q.get('explanation')}")
        else:
            print("Không tạo được câu hỏi nào.")