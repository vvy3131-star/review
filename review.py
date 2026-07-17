import streamlit as st
import os
import asyncio
import tempfile
import requests
from bs4 import BeautifulSoup
import subprocess
import sys

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

# --- CÁC HÀM XỬ LÝ PHỤ TRỢ ---

def get_system_font():
    """Tìm font chữ phù hợp hỗ trợ tiếng Việt trên cả Windows và Linux"""
    if sys.platform.startswith("win"):
        paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "C:/Windows/Fonts/calibri.ttf"
        ]
    else:
        # Đường dẫn phổ biến trên Linux (Streamlit Cloud)
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
        ]
    
    for path in paths:
        if os.path.exists(path):
            return path
    return None

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
        
        # Chiến lược lấy tiêu đề tối ưu (Đặc biệt hiệu quả với thẻ meta chia sẻ của TikTok Shop)
        title = "Sản phẩm review"
        og_title = soup.find("meta", property="og:title") or soup.find("meta", name="twitter:title")
        
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        else:
            title_tag = soup.find("h1") or soup.find("title")
            if title_tag:
                title = title_tag.text.strip()
                
        # Làm sạch tiêu đề khỏi các ký tự xuống dòng
        title = title.replace("\n", "").replace("\r", "").strip()
        
        # Tìm các link hình ảnh (.jpg, .png, .webp) xuất hiện trong trang
        images = []
        
        # Ưu tiên lấy ảnh chất lượng cao từ thẻ meta trước (TikTok Shop thường chứa ảnh đẹp ở đây)
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img_url = og_image["content"]
            if img_url.startswith("http"):
                images.append(img_url)

        # Cào tiếp các thẻ img thông thường nếu chưa đủ 5 ảnh
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("key") or img.get("file")
            if src and (src.startswith("http://") or src.startswith("https://")):
                if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                    # Loại bỏ các thành phần giao diện nhỏ lẻ (icon, logo)
                    if "icon" not in src.lower() and "logo" not in src.lower() and src not in images:
                        images.append(src)
                        if len(images) >= 5:  # Lấy tối đa 5 ảnh để làm slide
                            break
                        
        return {"title": title, "images": images}
    except Exception as e:
        st.warning(f"Không thể tự động cào do cơ chế bảo mật nghiêm ngặt của trang web. Bạn hãy chuyển sang chế độ Nhập Thủ Công bên dưới nhé!")
        return None

def download_images(image_urls, tmp_dir):
    """Tải các ảnh sản phẩm về thư mục tạm"""
    local_paths = []
    for i, url in enumerate(image_urls):
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                path = os.path.join(tmp_dir, f"img_{i}.jpg")
                with open(path, "wb") as f:
                    f.write(res.content)
                local_paths.append(path)
        except:
            continue
    return local_paths

def generate_review_script(title):
    """Tạo kịch bản review mẫu ngắn gọn"""
    clean_title = title[:50] + "..." if len(title) > 50 else title
    script_steps = [
        f"Chào các bạn! Hôm nay mình sẽ review nhanh sản phẩm {clean_title}.",
        "Ấn tượng đầu tiên là thiết kế vô cùng sang xịn mịn và cực kỳ bắt mắt.",
        "Trải nghiệm thực tế sử dụng cho hiệu năng vô cùng ổn định và mượt mà.",
        "Trong tầm giá này thì đây chắc chắn là một sự lựa chọn cực kỳ hời cho các bạn.",
        "Chi tiết thông tin sản phẩm mình để ở phần mô tả, nhanh tay sở hữu ngay nhé!"
    ]
    return script_steps

async def text_to_speech(text, out_path):
    """Tạo giọng đọc AI thuyết minh bằng edge-tts"""
    import edge_tts
    # Sử dụng Hoài My (vi-VN-HoaiMyNeural) giọng đọc truyền cảm cực hợp làm review
    communicate = edge_tts.Communicate(text, voice="vi-VN-HoaiMyNeural", rate="+3%")
    await communicate.save(out_path)

def create_slide_video(image_path, audio_path, output_video, text, font_size=32):
    """Dựng một đoạn video ngắn từ 1 ảnh + 1 file audio + chữ đè lên"""
    # Lấy thời lượng chính xác của file audio thuyết minh
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    duration = float(subprocess.check_output(probe_cmd).strip())
    
    # Định dạng lại văn bản để không bị tràn màn hình video dọc
    wrapped_text = ""
    words = text.split()
    temp_line = ""
    for word in words:
        if len(temp_line + " " + word) < 28:
            temp_line += " " + word if temp_line else word
        else:
            wrapped_text += temp_line + "\n"
            temp_line = word
    wrapped_text += temp_line
    
    # Xử lý font chữ và dấu gạch chéo đường dẫn trên Windows
    font_path = get_system_font()
    img_clean = image_path.replace("\\", "/")
    aud_clean = audio_path.replace("\\", "/")
    out_clean = output_video.replace("\\", "/")
    
    # Xây dựng filter vẽ chữ (Drawtext filter)
    drawtext_filter = f"drawtext=text='{wrapped_text}':fontcolor=white:fontsize={font_size}:box=1:boxcolor=black@0.6:boxborderw=15:x=(w-text_w)/2:y=h-350"
    if font_path:
        # Nếu tìm thấy font hệ thống, thêm vào để tránh lỗi hiển thị tiếng Việt
        font_clean = font_path.replace("\\", "/").replace(":", "\\:")
        drawtext_filter = f"drawtext=fontfile='{font_clean}':" + drawtext_filter

    # Render video từ ảnh tĩnh khớp với thời lượng tiếng, chuyển khung hình về 1080x1920 (9:16 dọc)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_clean,
        "-i", aud_clean,
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,{drawtext_filter}",
        "-c:v", "libx264", "-preset", "ultrafast", "-t", str(duration), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        out_clean
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

# --- THIẾT LẬP GIAO DIỆN CHÍNH ---

tab1, tab2 = st.tabs(["🔗 Sử dụng Link sản phẩm", "📤 Nhập thủ công (Khuyên dùng)"])

product_title = ""
product_images = []

# TAB 1: CÀO TỰ ĐỘNG (HỖ TRỢ THÊM TIKTOK SHOP)
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
    
    # Chỉ gán giá trị thủ công nếu người dùng thực sự đang thao tác ở tab này
    if manual_title and not product_title:
        product_title = manual_title
    if uploaded_files:
        product_images = uploaded_files

# --- PHẦN XỬ LÝ DỰNG VIDEO CHUNG (Đã tối ưu tránh lỗi DOM) ---
if product_title:
    st.write("---")
    
    # Sử dụng container cố định để render ảnh, tránh lỗi React removeChild
    image_container = st.container()
    
    # Tạo thư mục tạm để quản lý file ảnh
    tmp_dir = tempfile.mkdtemp(prefix="prod_review_")
    local_images_paths = []

    if product_images:
        with image_container:
            st.subheader("📸 Cấu hình hình ảnh sản phẩm:")
            cols = st.columns(min(len(product_images), 5))
            for idx, img_obj in enumerate(product_images[:5]):
                cols[idx].image(img_obj, use_container_width=True)
                
                # Lưu file ảnh vào bộ nhớ tạm để ffmpeg xử lý
                temp_img_path = os.path.join(tmp_dir, f"img_{idx}.jpg")
                if isinstance(img_obj, str):
                    try:
                        res = requests.get(img_obj, timeout=5)
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

    # Sinh kịch bản mẫu dựa trên tên sản phẩm
    st.subheader("📝 Kịch bản thuyết minh (Có thể sửa lại theo ý bạn):")
    scripts = generate_review_script(product_title)
    edited_scripts = []
    
    for idx, step in enumerate(scripts):
        edited_txt = st.text_input(f"Câu thoại {idx + 1}:", value=step, key=f"script_input_{idx}")
        edited_scripts.append(edited_txt)

    st.write("---")
    
    # Nút bấm bắt đầu dựng video chính
    if st.button("🎬 Bắt đầu dựng và xuất video ngay", use_container_width=True, key="submit_btn"):
        if not local_images_paths:
            st.error("Lỗi: Không tìm thấy ảnh sản phẩm hợp lệ nào để dựng video. Hãy thêm ảnh ở tab Nhập thủ công nếu link cào bị chặn ảnh.")
            st.stop()
            
        video_clips = []
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        try:
            # Bước 1: Tạo tiếng & video cho từng phân đoạn
            progress_text.write("⏳ Bước 1: Đang khởi tạo giọng đọc AI thuyết minh tiếng Việt...")
            for idx, text in enumerate(edited_scripts):
                img_path = local_images_paths[idx % len(local_images_paths)]
                audio_path = os.path.join(tmp_dir, f"audio_{idx}.mp3")
                clip_path = os.path.join(tmp_dir, f"clip_{idx}.mp4")
                
                # Tạo giọng nói bất đồng bộ
                try:
                    asyncio.run(text_to_speech(text, audio_path))
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(text_to_speech(text, audio_path))
                
                # Tạo slide clip
                create_slide_video(img_path, audio_path, clip_path, text)
                video_clips.append(clip_path)
                
            progress_bar.progress(50)
            
            # Bước 2: Ghép các phân đoạn thành video hoàn chỉnh
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
            
            # Hiển thị kết quả video trực quan
            st.video(output_video_path)
            
            # Cho phép người dùng tải về máy
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
