import streamlit as st
import os
import asyncio
import tempfile
import requests
from bs4 import BeautifulSoup
import subprocess
import sys
import re

st.set_page_config(page_title="Tạo Video Review Sản Phẩm Tự Động", page_icon="🛍️", layout="centered")

# CSS giao diện đẹp mắt
st.markdown("""
<style>
    .block-container {padding-top: 2rem; max-width: 800px;}
    div.stButton > button {width: 100%; background-color: #FF4B4B; color: white; font-weight: bold; height: 3rem;}
</style>
""", unsafe_allow_html=True)

st.title("🛍️ Tạo Video Review Sản Phẩm Tự Động")
st.write("Nhập link sản phẩm hoặc tự upload hình ảnh để tạo video review ngắn (dạng dọc 16:9 TikTok/Shorts) kèm giọng thuyết minh AI cực chất.")

# Khởi tạo session_state cho API Key nếu chưa có
if "saved_gemini_api_key" not in st.session_state:
    st.session_state["saved_gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "")

# --- CẤU HÌNH AI (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Cấu hình AI viết kịch bản")
    
    # Nhập và lưu API Key vào session_state
    gemini_api_key = st.text_input(
        "Gemini API Key:",
        type="password",
        value=st.session_state["saved_gemini_api_key"],
        help="Lấy API Key tại Google AI Studio (https://aistudio.google.com/). "
             "Key sẽ được lưu tự động trong phiên làm việc này."
    )
    if gemini_api_key != st.session_state["saved_gemini_api_key"]:
        st.session_state["saved_gemini_api_key"] = gemini_api_key

    ai_model = st.selectbox(
        "Model AI:",
        options=["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
        help="gemini-2.5-flash: Cực kỳ nhanh, phản hồi tức thì và tiết kiệm chi phí. gemini-2.5-pro: Dành cho kịch bản có tính sáng tạo cao hơn."
    )
    num_script_lines = st.slider("Số câu thoại trong kịch bản:", min_value=3, max_value=7, value=5)

# --- CÁC HÀM XỬ LÝ PHỤ TRỢ ---

def scrape_product_info(url):
    """Cào thông tin cơ bản của sản phẩm từ URL với Headers giả lập trình duyệt (Hỗ trợ TikTok Shop)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Cache-Control": "max-age=0"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        title = "Sản phẩm review"
        og_title = soup.find("meta", property="og:title") or soup.find("meta", name="twitter:title")
        
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        else:
            title_tag = soup.find("h1") or soup.find("title")
            if title_tag:
                title = title_tag.text.strip()
                
        title = title.replace("\n", "").replace("\r", "").strip()
        images = []
        
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img_url = og_image["content"]
            if img_url.startswith("http"):
                images.append(img_url)

        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("key") or img.get("file")
            if src and (src.startswith("http://") or src.startswith("https://")):
                if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                    if "icon" not in src.lower() and "logo" not in src.lower() and src not in images:
                        images.append(src)
                        if len(images) >= 5:
                            break
                        
        return {"title": title, "images": images}
    except Exception as e:
        st.warning(f"Không thể tự động cào do cơ chế bảo mật nghiêm ngặt của trang web. Bạn hãy chuyển sang chế độ Nhập Thủ Công bên dưới nhé!")
        return None

def generate_review_script(title, num_lines=5):
    """Tạo kịch bản review mẫu ngắn gọn kèm emoji sinh động (dự phòng khi không dùng AI hoặc AI lỗi)"""
    clean_title = title[:50] + "..." if len(title) > 50 else title
    script_steps = [
        f"🔥 Chào các bạn! Hôm nay mình sẽ review nhanh siêu phẩm {clean_title} này nhé.",
        "✨ Ấn tượng đầu tiên là thiết kế vô cùng sang xịn mịn và cực kỳ bắt mắt luôn đó.",
        "💎 Trải nghiệm thực tế sử dụng cho hiệu năng vô cùng ổn định và mượt mà ngoài mong đợi.",
        "🤑 Trong tầm giá này thì đây chắc chắn là một sự lựa chọn cực kỳ hời cho các bạn.",
        "🛒 Chi tiết thông tin sản phẩm mình để ở phần mô tả, nhanh tay bấm vào giỏ hàng sở hữu ngay nha!"
    ]
    return script_steps[:num_lines] if num_lines <= len(script_steps) else script_steps

def generate_review_script_ai(title, api_key, model="gemini-2.5-flash", num_lines=5):
    """Dùng Google Gemini API để viết kịch bản thuyết minh video review hấp dẫn CÓ CHỨA EMOJI"""
    if not api_key:
        st.warning("⚠️ Chưa nhập Gemini API Key ở thanh bên trái, đang dùng kịch bản mẫu có sẵn.")
        return generate_review_script(title, num_lines)

    try:
        from google import genai
    except ImportError:
        st.warning("⚠️ Chưa cài thư viện `google-genai` (chạy: pip install google-genai). Đang dùng kịch bản mẫu có sẵn.")
        return generate_review_script(title, num_lines)

    try:
        client = genai.Client(api_key=api_key)

        prompt = f"""Bạn là một chuyên gia bán hàng livestream TikTok Shop / Shopee cực kỳ có duyên, giàu kinh nghiệm chốt đơn.

Hãy viết kịch bản thuyết minh cho video review ngắn (dạng dọc, TikTok/Shorts) cho sản phẩm sau:
"{title}"

YÊU CẦU BẮT BUỘC:
1. Viết đúng {num_lines} câu thoại, mỗi câu MỘT dòng riêng biệt, không đánh số, không markdown.
2. Hãy chèn các EMOJI sinh động, phù hợp xu hướng giới trẻ (ví dụ: 🔥, ✨, 😍, 🛒, 💯) vào mỗi câu để làm kịch bản hấp dẫn hơn.
3. Câu 1: chào hỏi + giới thiệu sản phẩm sao cho gây chú ý ngay lập tức, đúng chất mở đầu video bán hàng.
4. Các câu ở giữa: PHẢI nêu rõ ít nhất 2-3 ƯU ĐIỂM/TÍNH NĂNG CỤ THỂ của sản phẩm (suy luận hợp lý dựa trên tên và loại sản phẩm, ví dụ: chất liệu, công dụng, độ bền, tiện lợi, hiệu quả, thiết kế, công nghệ...). TUYỆT ĐỐI không nói chung chung kiểu "chất lượng tốt", "rất đẹp" mà không giải thích vì sao — phải gắn với LỢI ÍCH thực tế người dùng nhận được.
5. Văn phong: nhiệt huyết, gần gũi, tự nhiên như đang nói trực tiếp với khách xem livestream, có thể dùng cách so sánh để làm nổi bật "hời" (so với giá, so với sản phẩm cùng loại).
6. Câu cuối: lời kêu gọi hành động (CTA) mạnh mẽ, tạo cảm giác cấp bách/khan hiếm hợp lý để thúc đẩy chốt đơn ngay (không nói dối, không cam kết sai sự thật).
7. Mỗi câu dài khoảng 15-25 từ, dễ đọc thành lời, phù hợp để lồng giọng đọc AI (text-to-speech).
8. CHỈ trả về đúng {num_lines} dòng kịch bản, KHÔNG thêm lời dẫn, giải thích, tiêu đề hay bất kỳ nội dung nào khác."""

        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        raw_text = response.text.strip()
        lines = [l.strip(" -•\t") for l in raw_text.split("\n") if l.strip()]

        if len(lines) == 0:
            raise ValueError("AI không trả về nội dung hợp lệ.")

        if len(lines) > num_lines:
            lines = lines[:num_lines]

        return lines

    except Exception as e:
        st.warning(f"⚠️ Không thể tạo kịch bản bằng AI ({e}). Đang dùng kịch bản mẫu có sẵn.")
        return generate_review_script(title, num_lines)

async def text_to_speech(text, out_path):
    """Tạo giọng đọc AI thuyết minh bằng edge-tts"""
    import edge_tts
    # Loại bỏ emoji trước khi chuyển sang giọng nói để tránh lỗi phát âm ký tự lạ
    clean_text = "".join(c for c in text if c.isalnum() or c.isspace() or c in ".,!?-_:")
    communicate = edge_tts.Communicate(clean_text, voice="vi-VN-HoaiMyNeural", rate="+3%")
    await communicate.save(out_path)

def create_slide_video(image_path, audio_path, script_text, title, output_video):
    """Dựng một đoạn video ngắn từ 1 ảnh + 1 file audio kèm theo Layout Frame Tiêu đề & Logo chuẩn chỉnh"""
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    duration = float(subprocess.check_output(probe_cmd).strip())
    
    img_clean = image_path.replace("\\", "/")
    aud_clean = audio_path.replace("\\", "/")
    out_clean = output_video.replace("\\", "/")
    
    # Loại bỏ các ký tự đặc biệt nguy hiểm làm lỗi lệnh bộ lọc ffmpeg
    safe_title = re.sub(r"[':\"\\\(\)\[\]\{\}]", "", title).strip().upper()
    
    # Xử lý cắt dòng tiêu đề nếu quá dài để hiển thị đẹp trên 2 dòng
    if len(safe_title) > 22:
        words = safe_title.split()
        mid = len(words) // 2
        title_line1 = " ".join(words[:mid])
        title_line2 = " ".join(words[mid:])
    else:
        title_line1 = safe_title
        title_line2 = ""

    # Đường dẫn font hệ thống mặc định phù hợp cho cả Windows và Linux
    font_path = "C\\\\:/Windows/Fonts/Arial.ttf" if os.name == 'nt' else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    # --- ĐOẠN MÃ NÂNG CẤP BỘ LỌC FFMPEG TẠO KHUNG ĐỒNG BỘ MÀU HỒNG ---
    # 1. Thu gọn hình ảnh nằm gọn ở giữa khung đứng 1080x1920
    # 2. Tạo phần khung Header phía trên và Footer phía dưới đều phủ ĐỒNG BỘ NỀN MÀU HỒNG (#FFF5F5)
    # 3. Vẽ 3 đường vạch highlight màu hồng sẫm (#D96B78) ngăn cách bố cục sang trọng
    # 4. In trực tiếp Tên sản phẩm do người dùng nhập lên khung trên
    # 5. Loại bỏ hoàn toàn logo và tên thương hiệu cũ ở phần dưới
    vf_filter = (
        f"scale=1080:1200:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
        f"drawbox=y=0:w=1080:h=400:color=#FFF5F5:t=fill," # Khung trên màu hồng nhạt
        f"drawbox=y=1520:w=1080:h=400:color=#FFF5F5:t=fill," # Khung dưới màu hồng nhạt đồng bộ
        f"drawbox=y=130:w=1080:h=8:color=#D96B78:t=fill," # Vạch viền trang trí trên
        f"drawbox=y=392:w=1080:h=8:color=#D96B78:t=fill," # Vạch chia khung trên
        f"drawbox=y=1520:w=1080:h=8:color=#D96B78:t=fill," # Vạch chia khung dưới
        f"drawtext=fontfile='{font_path}':text='{title_line1}':fontcolor=black:fontsize=48:x=(w-tw)/2:y=210:box=1:boxcolor=#FFF5F5"
    )
    
    if title_line2:
        vf_filter += f",drawtext=fontfile='{font_path}':text='{title_line2}':fontcolor=#D96B78:fontsize=42:x=(w-tw)/2:y=295:box=1:boxcolor=#FFF5F5"
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_clean,
        "-i", aud_clean,
        "-vf", vf_filter,
        "-c:v", "libx264", "-preset", "ultrafast", "-t", str(duration), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        out_clean
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

# --- THIẾT LẬP GIAO DIỆN CHÍNH ---

tab1, tab2 = st.tabs(["🔗 Sử dụng Link sản phẩm", "📤 Nhập thủ công (Khuyên dùng)"])

product_title = ""
product_images = []

# TAB 1: CÀO TỰ ĐỘNG
with tab1:
    product_url = st.text_input("Dán link sản phẩm tại đây (Shopee, TikTok Shop, Tiki, Lazada...):", placeholder="https://v.tiktok.com/... hoặc https://shopee.vn/...", key="url_input")
    if product_url:
        with st.spinner("🕵️ Đang phân tích dữ liệu trang web..."):
            data = scrape_product_info(product_url)
            if data and (data["images"] or data["title"] != "Sản phẩm review"):
                product_title = data["title"]
                product_images = data["images"]
                st.success("Nhận diện thông tin thành công! Hãy kiểm tra kịch bản phía dưới.")
            else:
                st.error("Không thể tự động tải dữ liệu từ link này do lớp bảo mật. Hãy chuyển sang tab 'Nhập thủ công' để tạo video ngay nhé!")

# TAB 2: NHẬP THỦ CÔNG 
with tab2:
    manual_title = st.text_input("Tên sản phẩm muốn review:", value="Loa Bluetooth Siêu Trầm Mini", key="manual_title_input")
    uploaded_files = st.file_uploader("Tải lên hình ảnh sản phẩm (Từ 1 đến 5 ảnh):", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True, key="file_uploader_input")
    
    if manual_title and not product_title:
        product_title = manual_title
    if uploaded_files:
        product_images = uploaded_files

# --- PHẦN XỬ LÝ DỰNG VIDEO CHUNG ---
if product_title:
    st.write("---")
    
    image_container = st.container()
    tmp_dir = tempfile.mkdtemp(prefix="prod_review_")
    local_images_paths = []

    if product_images:
        with image_container:
            st.subheader("📸 Cấu hình hình ảnh sản phẩm:")
            cols = st.columns(min(len(product_images), 5))
            for idx, img_obj in enumerate(product_images[:5]):
                cols[idx].image(img_obj, use_container_width=True)
                
                temp_img_path = os.path.join(tmp_dir, f"img_{idx}.jpg")
                if isinstance(img_obj, str):
                    try:
                        res = requests.get(img_obj, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                        if res.status_code == 200:
                            with open(temp_img_path, "wb") as f:
                                f.write(res.content)
                            local_images_paths.append(temp_img_path)
                    except:
                        continue
                else:
                    with open(temp_img_path, "wb") as f:
                        f.write(img_obj.getbuffer())
                    local_images_paths.append(temp_img_path)

    st.subheader("📝 Kịch bản thuyết minh (Có thể sửa lại theo ý bạn):")

    col_ai1, col_ai2 = st.columns([3, 1])
    with col_ai1:
        use_ai_script = st.checkbox(
            "✨ Dùng AI viết kịch bản bán hàng siêu thuyết phục (có chèn emoji)",
            value=True,
            key="use_ai_checkbox"
        )
    with col_ai2:
        regenerate_ai = st.button("🔄 Viết lại bằng AI", key="regen_ai_btn", use_container_width=True)

    ai_cache_key = f"ai_script::{product_title}::{num_script_lines}::{ai_model}"

    if use_ai_script:
        if ai_cache_key not in st.session_state or regenerate_ai:
            with st.spinner("🤖 AI đang phân tích sản phẩm và viết kịch bản bán hàng sinh động..."):
                st.session_state[ai_cache_key] = generate_review_script_ai(
                    product_title,
                    api_key=st.session_state["saved_gemini_api_key"],
                    model=ai_model,
                    num_lines=num_script_lines
                )
        scripts = st.session_state[ai_cache_key]
    else:
        scripts = generate_review_script(product_title, num_script_lines)

    edited_scripts = []
    for idx, step in enumerate(scripts):
        edited_txt = st.text_input(f"Câu thoại {idx + 1}:", value=step, key=f"script_input_{idx}_{ai_cache_key}")
        edited_scripts.append(edited_txt)

    st.write("---")
    
    if st.button("🎬 Bắt đầu dựng và xuất video ngay", use_container_width=True, key="submit_btn"):
        if not local_images_paths:
            st.error("Lỗi: Không tìm thấy hoặc không thể tải bất kỳ hình ảnh sản phẩm hợp lệ nào để dựng video. Vui lòng chuyển sang tab 'Nhập thủ công' và tải trực tiếp file ảnh từ máy của bạn lên nhé!")
            st.stop()
            
        video_clips = []
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        try:
            progress_text.write("⏳ Bước 1: Đang khởi tạo giọng đọc AI thuyết minh...")
            for idx, text in enumerate(edited_scripts):
                img_path = local_images_paths[idx % len(local_images_paths)]
                audio_path = os.path.join(tmp_dir, f"audio_{idx}.mp3")
                clip_path = os.path.join(tmp_dir, f"clip_{idx}.mp4")
                
                try:
                    asyncio.run(text_to_speech(text, audio_path))
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(text_to_speech(text, audio_path))
                
                create_slide_video(img_path, audio_path, text, product_title, clip_path)
                video_clips.append(clip_path)
                
            progress_bar.progress(40)
            
            progress_text.write("⏳ Bước 2: Đang ghép nối các phân đoạn slide thành video dọc...")
            concat_list_path = os.path.join(tmp_dir, "concat_list.txt")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for clip in video_clips:
                    f.write(f"file '{clip.replace('\\', '/')}'\n")
            
            output_video_path = os.path.join(tmp_dir, "review_final_output.mp4")
            concat_cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list_path, "-c", "copy", output_video_path
            ]
            subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            progress_bar.progress(100)
            progress_text.write("🎉 **Chúc mừng! Dựng video thành công.**")
            
            st.video(output_video_path)
            
            with open(output_video_path, "rb") as f:
                st.download_button(
                    label="📥 Tải video review về máy",
                    data=f,
                    file_name="video_review_san_pham.mp4",
                    mime="video/mp4",
                    key="download_btn"
                )
                
        except Exception as e:
            st.error(f"Đã xảy ra lỗi trong quá trình xử lý video: {e}")
