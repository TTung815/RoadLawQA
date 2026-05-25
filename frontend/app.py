#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit Demo App for Vietnamese Law QA System - Chatbot Interface
"""
import os
import sys
from pathlib import Path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
	sys.path.insert(0, ROOT_DIR)
APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"

# pyrefly: ignore [missing-import]
import streamlit as st
import time
# Giả định rằng bạn đã clone repo và các file này nằm trong thư mục 'backend'
# (Nếu file của bạn tên khác, hãy sửa lại đường dẫn import)
from backend.retriever_custom import retrieve
from backend.generator import generate_answer, generate_quiz
# Page config
st.set_page_config(
	page_title="RoadLawQA",
	page_icon="⚖️",
	layout="centered",
	initial_sidebar_state="collapsed"
)

# Custom CSS for chat interface
st.markdown("""
<style>
/* ... (các class .main, .chat-header, .chat-title, .chat-subtitle giữ nguyên) ... */
.main { background-color: #f7f7f8; }
.chat-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 10px; text-align: center; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
.chat-title { font-size: 1.8rem; font-weight: bold; margin: 0; }
.chat-subtitle { font-size: 0.9rem; opacity: 0.9; margin-top: 0.3rem; }

/* Tin nhắn user*/
.user-message {
	background-color: #e5e5ea;
	color: #111;
	padding: 0.6rem 1rem; /* giảm padding trên/dưới */
	border-radius: 18px 18px 4px 18px;
	margin: 0.5rem 0 0.5rem auto;
	white-space: pre-line;
	max-width: 80%;
	width: fit-content;
	box-shadow: 0 2px 4px rgba(0,0,0,0.1);
	word-wrap: break-word;
	animation: fadeInUp 0.3s ease-out;
	text-align: left;
}


/* --- ĐÃ SỬA TỪ ĐÂY --- */

/* 1. Đây là KHUNG BAO NGOÀI MỚI cho toàn bộ phản hồi của Bot */
.bot-response-container {
	margin: 0.5rem auto 0.5rem 0; /* Căn lề trái */
	max-width: 85%;              /* Giới hạn chiều rộng tối đa */
	width: fit-content;          /* Tự co dãn theo nội dung */
	animation: fadeInUp 0.3s ease-out; /* Áp dụng animation cho cả khối */
}

/* 2. Tin nhắn bot (Đã BỎ CÁC THUỘC TÍNH LAYOUT) */
.bot-message {
	background-color: #e5e5ea; /* xám nhạt */
	color: #111;
	padding: 1rem 1.2rem;
	border-radius: 18px 18px 18px 4px;
	box-shadow: 0 2px 4px rgba(0,0,0,0.05);
	word-wrap: break-word;
	/* Đã BỎ: margin, max-width, width, animation */
}

/* 3. Chỉnh expander (Nguồn tham khảo) để nó khớp với style */
.bot-response-container .stExpander {
	border: none;
	box-shadow: none;
	margin-top: 0.5rem;
	border-radius: 10px;
	background-color: #f0f0f0; /* Một màu xám nhạt khác biệt */
}
.bot-response-container .stExpander header {
	padding: 0.5rem 1rem;
	font-size: 0.9rem;
	border-radius: 10px;
}

/* --- KẾT THÚC PHẦN SỬA --- */


/* Bot icon */
.bot-icon {
	display: inline-block;
	background: #4f46e5;
	color: white;
	width: 32px;
	height: 32px;
	border-radius: 50%;
	text-align: center;
	line-height: 32px;
	margin-right: 0.5rem;
	font-weight: bold;
}

/* Nguồn tham khảo */
.source-item {
	background: #fff8dc;
	padding: 0.6rem 0.8rem;
	border-radius: 8px;
	margin: 0.3rem 0;
	border-left: 3px solid #ffc107;
	font-size: 0.85rem;
	color: #555;
}

/* ... (Phần còn lại của CSS giữ nguyên) ... */
.time-badge { background: #e3f2fd; color: #1976d2; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.75rem; display: inline-block; margin-top: 0.5rem; }
.stChatInputContainer { border-top: 2px solid #e0e0e0; background: #f2f2f2; padding: 1rem 0; }
.welcome-card { background: white; padding: 2rem; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; margin: 2rem 0; }
.sample-question { background: #f8f9fa; padding: 0.8rem 1rem; border-radius: 10px; margin: 0.5rem 0; cursor: pointer; border: 1px solid #dee2e6; transition: all 0.3s; }
.sample-question:hover { background: #e9ecef; border-color: #667eea; transform: translateY(-2px); }
.metric-inline { display: inline-block; background: #f0f0f0; padding: 0.3rem 0.8rem; border-radius: 8px; margin: 0.2rem; font-size: 0.8rem; color: #666; }
@keyframes fadeInUp {
	from { opacity: 0; transform: translateY(20px); }
	to { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
	st.session_state.messages = []
if 'running_rag' not in st.session_state:
	st.session_state.running_rag = False
if 'chat_started' not in st.session_state:
	st.session_state.chat_started = False

if 'quiz_data' not in st.session_state: st.session_state.quiz_data = None
if 'quiz_topic' not in st.session_state: st.session_state.quiz_topic = ""
# ===== WELCOME SCREEN (Trang giới thiệu) =====
if not st.session_state.chat_started:
	# Hiển thị HOÀN TOÀN trang giới thiệu
	st.markdown("""
	<div style='text-align: center; padding: 0.5rem 2rem 2rem 2rem;'>
		<h1 style='color: #667eea; font-size: 3rem; margin: 0; font-weight: bold;'>RoadLawQA</h1>
		<h2 style='color: #666; font-size: 1.3rem; margin: 0.8rem 0 1.5rem 0; font-weight: 400;'>Hệ thống Hỏi Đáp về Luật An Toàn Giao Thông Đường Bộ Việt Nam</h2>
	</div>
	""", unsafe_allow_html=True)
	
	# Nút "Bắt đầu trò chuyện" - căn giữa
	col1, col2, col3 = st.columns(3)
	with col2:
		if st.button("🚀 Bắt đầu trò chuyện", use_container_width=True, key="start_chat_btn"):
			st.session_state.chat_started = True
			st.rerun()
	
	# Thêm khoảng trống
	st.markdown("<br>", unsafe_allow_html=True)
	
	# 3 ảnh minh họa với chiều cao cố định
	col1, col2, col3 = st.columns(3, gap="small")
	
	with col1:
		st.image(ASSETS_DIR / "law.png", use_container_width=True)
	
	with col2:
		st.image(ASSETS_DIR / "traffic.png", use_container_width=True)
	
	with col3:
		st.image(ASSETS_DIR / "legal.png", use_container_width=True)
	
	st.stop()  # Dừng execution tại đây, không hiển thị gì khác


# ===== CHAT INTERFACE (Chỉ hiển thị khi đã bấm "Bắt đầu") =====

# Header
st.markdown("""
<div class="chat-header">
	<div class="chat-title">RoadLawQA - Hỏi Đáp Luật An Toàn Giao Thông Đường Bộ</div>
	<div class="chat-subtitle">Hỏi đáp tức thì về Luật Giao Thông Việt Nam</div>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
	st.header("⚙️ Cài đặt")
	
	k_value = st.slider(
		"Số lượng chunks",
		min_value=1,
		max_value=15,
		value=5,
		help="Số đoạn văn bản được tìm kiếm"
	)
	
	st.markdown("---")
	
	st.markdown("""
	**📚 Dữ liệu:**
	- Nghị định 168/2024/NĐ-CP
	- Luật 36/2024/QH15
	- Luật 35/2024/QH15
	""")
	
	st.markdown("---")
	
	if st.button("🗑️ Xóa hội thoại", use_container_width=True):
		st.session_state.messages = []
		st.session_state.chat_started = False
		st.session_state.running_rag = False
		st.rerun()

tab_chat, tab_quiz = st.tabs(["💬 Hỏi Đáp Luật", "📝 Tạo Đề Thi Trắc Nghiệm"])



with tab_chat:

	# 1. KHỞI TẠO BIẾN
	user_input = None
	
	# 2. XỬ LÝ NÚT BẤM CÂU HỎI MẪU (Nằm trên cùng)
	sample_questions = [
		"Kết cấu hạ tầng đường bộ bao gồm những gì?",
		"Người đi xe dàn hàng ba bị xử phạt như thế nào?",
		"Làn đường được định nghĩa là gì?",
		"Xe máy chở 2 người trở lên có bị phạt không?",
	]

	# Chỉ hiển thị gợi ý khi chưa có tin nhắn nào
	if len(st.session_state.messages) == 0:
		st.markdown("""
		<div style='text-align: center; margin: 2rem 0;'>
			<h4 style='color: #666;'>💡 Bạn có thể bắt đầu với các câu hỏi này:</h4>
		</div>
		""", unsafe_allow_html=True)
		
		col1, col2 = st.columns(2)
		for idx, question in enumerate(sample_questions):
			with col1 if idx % 2 == 0 else col2:
				# Nếu bấm nút -> Gán giá trị vào user_input ngay lập tức
				if st.button(f"💡 {question}", key=f"sample_{idx}", use_container_width=True):
					user_input = question

	# 3. HIỂN THỊ LỊCH SỬ TIN NHẮN (MESSAGE LOOP)
	for idx, message in enumerate(st.session_state.messages):
		if message["role"] == "user":
			user_text = message['content'].strip()
			user_text = '\n'.join(line.strip() for line in user_text.split('\n') if line.strip())
			user_text = user_text.replace('<', '&lt;').replace('>', '&gt;')
			user_text = user_text.replace('\n', '<br>')
			st.markdown(f'<div style="text-align: right;"><div class="user-message">{user_text}</div></div>', unsafe_allow_html=True)
		else:
			with st.container():
				st.markdown('<div class="bot-response-container">', unsafe_allow_html=True)
				st.markdown(f"""
					<div class="bot-message">
						<span class="bot-icon">⚖️</span>
						<strong>RoadLawQA</strong><br><br>
						{message['content']}
					</div>
				""", unsafe_allow_html=True)
				
				if 'sources' in message and message['sources']:
					with st.expander("📚 Nguồn tham khảo", expanded=False):
						for i, src in enumerate(message['sources'], 1):
							if src:
								st.markdown(f'<div class="source-item">[{i}] {src}</div>', unsafe_allow_html=True)
				
				if 'metrics' in message:
					m = message['metrics']
					st.markdown(f"""
					<div style='text-align: left; margin-top: 0.5rem;'>
						<span class="metric-inline">⏱️ {m['total']:.2f}s</span>
						<span class="metric-inline">🔍 {m['retrieval']:.2f}s</span>
						<span class="metric-inline">🤖 {m['generation']:.2f}s</span>
						<span class="metric-inline">📄 {m['chunks']} chunks</span>
					</div>
					""", unsafe_allow_html=True)
				st.markdown('</div>', unsafe_allow_html=True)
		
		st.markdown("<br>", unsafe_allow_html=True)

	# 4. LOGIC XỬ LÝ RAG (ĐƯA LÊN TRƯỚC INPUT)
	# Phần này sẽ hiển thị Spinner ngay sau tin nhắn cuối cùng, TRƯỚC khi vẽ thanh input
	if st.session_state.messages and st.session_state.messages[-1]["role"] == "user" and st.session_state.running_rag:
		last_user_question = st.session_state.messages[-1]["content"]
		
		with st.spinner("Đang suy nghĩ..."):
			start_time = time.time()
			try:
				t0 = time.time()
				context, sources = retrieve(last_user_question, k=k_value)
				retrieval_time = time.time() - t0
				
				t1 = time.time()
				answer, sources = generate_answer(last_user_question, context, sources)
				generation_time = time.time() - t1
				
				total_time = time.time() - start_time
				
				st.session_state.messages.append({
					"role": "assistant",
					"content": answer,
					"sources": sources,
					"metrics": {
						"total": total_time,
						"retrieval": retrieval_time,
						"generation": generation_time,
						"chunks": len(sources)
					}
				})
			except Exception as e:
				st.session_state.messages.append({
					"role": "assistant",
					"content": f"❌ Xin lỗi, đã xảy ra lỗi: {str(e)}"
				})
		
		# Xử lý xong -> Tắt cờ chạy -> Rerun để hiển thị kết quả
		st.session_state.running_rag = False
		st.rerun()

	# 5. THANH NHẬP LIỆU (ĐỂ CUỐI CÙNG)
	# Vì để cuối cùng, nó sẽ luôn được vẽ ở dưới đáy, sau Spinner
	chat_input = st.chat_input("Nhập câu hỏi của bạn...")
	if chat_input:
		user_input = chat_input.strip()

	# 6. KÍCH HOẠT QUÁ TRÌNH XỬ LÝ (NẾU CÓ INPUT MỚI)
	# Logic này chỉ chạy để set trạng thái, sau đó rerun ngay
	if user_input and not st.session_state.running_rag:
		st.session_state.running_rag = True 
		st.session_state.messages.append({
			"role": "user",
			"content": user_input.strip()
		})
		st.rerun()

# ==========================================
# TAB 2: QUIZ GENERATOR (CÓ RANDOM MODE)
# ==========================================
with tab_quiz:
	st.markdown("### Luyện Kiến Thức Giao Thông ")
	
	# 1. Chọn chế độ
	quiz_mode = st.radio(
		"Chọn chế độ:",
		["Theo chủ đề", "Ngẫu nhiên"],
		horizontal=True
	)

	# ---- INPUT CHUNG ----
	c_q1, c_q2 = st.columns([3, 1])

	with c_q1:
		if quiz_mode == "Theo chủ đề":
			topic_input = st.text_input(
				"Nhập chủ đề:",
				placeholder="Ví dụ: Nồng độ cồn...",
				value=st.session_state.quiz_topic
			)
		else:
			st.text_input(
				"Chủ đề:",
				value="Ngẫu nhiên toàn bộ luật",
				disabled=True
			)
			topic_input = "Random"

	with c_q2:
		num_q = st.number_input(
			"Số câu hỏi:",
			min_value=1,
			max_value=20,
			value=10 if quiz_mode == "Ngẫu nhiên" else 3
		)

	if quiz_mode == "Ngẫu nhiên":
		st.info("Hệ thống sẽ chọn ngẫu nhiên các câu hỏi từ toàn bộ bộ luật.")

	btn_label = "🎯 Tạo Bộ Câu Hỏi"

	# Nút bấm sinh câu hỏi
	if st.button(btn_label, use_container_width=True):
		# Reset state
		st.session_state.quiz_topic = topic_input
		st.session_state.quiz_data = None
		
		# Kiểm tra input nếu ở chế độ Topic
		if quiz_mode == "Theo chủ đề" and not topic_input:
			st.warning("Vui lòng nhập chủ đề!")
		else:
			with st.status("Đang khởi tạo đề thi...", expanded=True) as status:
				try:
					# --- LOGIC TÌM KIẾM ---
					if quiz_mode == "Theo chủ đề":
						status.write(f" Đang tìm luật về '{topic_input}'...")
						relevant_chunks = retrieve(topic_input, k=5, raw=True)
					else:
						# Gọi hàm Random mới viết ở Backend
						status.write(" Đang chọn ngẫu nhiên các điều luật...")
						# Import hàm mới ngay tại đây để tránh lỗi nếu chưa restart server
						from backend.retriever_custom import retrieve_random
						# Lấy 12 chunk để trừ hao chunk ngắn, chọn ra 10
						relevant_chunks = retrieve_random(k=12)

					if not relevant_chunks:
						st.error("Không tìm thấy dữ liệu.")
						status.update(label="Thất bại", state="error")
					else:
						status.write(" Đang phân tích và soạn câu hỏi...")
						context_list = []
						for item in relevant_chunks:
							if isinstance(item, dict):
								props = item.get('props', {})
								text = props.get('enriched_text', '')
								source = props.get('display_citation', 'Nguồn không xác định')
								if text: 
									full_chunk = f"[Nguồn: {source}]\nNội dung: {text}"
									context_list.append(full_chunk)
						
						full_ctx = "\n\n".join(context_list)
						
						# Gọi Gemini sinh Quiz
						# Lưu ý: Với 10 câu, Gemini có thể mất tầm 10-15s
						new_quiz = generate_quiz(full_ctx, num_questions=num_q)
						
						if not new_quiz:
							st.error("AI không tạo được câu hỏi nào từ dữ liệu này. Hãy thử lại.")
							status.update(label="Lỗi sinh câu hỏi", state="error")
						else:
							# --- LƯU VÀO SESSION STATE ---
							st.session_state.quiz_data = new_quiz
							status.update(label="✅ Hoàn tất!", state="complete", expanded=False)
						
				except Exception as e:
					st.error(f"Lỗi: {str(e)}")
					status.update(label="Lỗi hệ thống", state="error")

	st.markdown("---")

	# --- PHẦN HIỂN THỊ CÂU HỎI (Logic cũ) ---
	if st.session_state.quiz_data:
		# Tính điểm
		score = 0
		total = len(st.session_state.quiz_data)
		
		# Thanh tiến độ làm bài (Optional visual)
		st.caption(f" Bộ câu hỏi gồm {total} câu .")

		for i, q in enumerate(st.session_state.quiz_data, 1):
			with st.container():
				st.markdown(f"""
				<div class="quiz-card">
					<div class="quiz-question">Câu {i}: {q.get('question')}</div>
				</div>
				""", unsafe_allow_html=True)
				
				options = q.get('options', {})
				opt_list = []
				if isinstance(options, dict):
					opt_list = [f"{k}. {v}" for k, v in options.items()]
				
				# Unique key mỗi lần sinh đề mới -> reset lựa chọn cũ
				# Dùng timestamp hoặc hash của câu hỏi để làm key
				unique_key = f"q_{hash(q.get('question'))}"
				
				user_choice = st.radio(f"Chọn đáp án câu {i}:", opt_list, key=unique_key, index=None)
				
				if user_choice:
					selected_opt = user_choice.split(".")[0].strip().upper()
					correct_opt = q.get('correct_answer', '').strip().upper()
					
					if selected_opt == correct_opt:
						st.markdown(f"<div class='right-msg'>✅ Chính xác.</div>", unsafe_allow_html=True)
						score += 1
					else:
						st.markdown(f"<div class='wrong-msg'>❌ Sai. Đáp án là {correct_opt}</div>", unsafe_allow_html=True)
					
					with st.expander(" Xem giải thích"):
						st.info(f"{q.get('explanation')}")
						st.caption(f"📚 {q.get('citation')}")
				
				st.markdown("---")
