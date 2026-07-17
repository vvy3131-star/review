import streamlit as st
import os
import asyncio
import tempfile
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import subprocess

st.set_page_config(page_title="Tạo Video Review Sản Phẩm Tự Động", page_icon="🛍️", layout="centered")

# CSS giao diện
st.markdown("""
<style>
    .block-container {padding-top: 2rem; max-width: 800px;}
    div.stButton > button {width: 100%; background-color: #FF4B4B; color: white; font-weight: bold;}
</style>
""", unsafe_allow_html=True)

st.title("🛍️ Tạo Video Review Sản Phẩm Tự Động")
st.write("Dán link sản phẩm (Shopee, Tiki, Lazada, Amazon...) để tự động cào ảnh, tạo giọng đọc thuyết minh và dựng thành video review.")

# --- CÁC HÀM XỬ LÝ PHỤ TRỢ (BACKGROUND FUNCTIONS) ---

def scrape_product_info(url):
    """Cào thông tin cơ bản của sản phẩm từ URL"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Thử lấy tiêu đề sản phẩm
        title_tag = soup.find("title") or soup.find("h1")
        title = title_tag.text.strip() if title_tag else "Sản phẩm chất lượng cao"
        
        # Tìm các link hình ảnh (.jpg, .png) xuất hiện trong trang
        images = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and (src.startswith("http://") or src.startswith("https://")):
                if any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png"]):
                    images.append(src)
                    if len(images) >= 5:  # Lấy tối đa 5 ảnh để làm slide
                        break
                        
        return {"title": title, "images": images}
    except Exception as e:
        st.error(f"Lỗi khi cào link sản phẩm: {e}")
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
    """Tạo kịch bản review ngắn dựa trên tên sản phẩm"""
    # Bạn có thể kết nối API Gemini/GPT tại đây để viết kịch bản hay hơn.
    # Bản mẫu dưới đây tự động điền tên sản phẩm vào form chuẩn:
    script_steps = [
        f"Chào các bạn! Hôm nay mình sẽ review nhanh sản phẩm {title[:60]}...",
        "Điểm cộng đầu tiên là thiết kế vô cùng hiện đại, trẻ trung và bắt mắt.",
        "Trải nghiệm thực tế cho thấy sản phẩm cực kỳ bền bỉ và đáng tiền.",
        "Nếu bạn đang tìm kiếm một giải pháp tối ưu thì đây chính là lựa chọn hoàn hảo.",
        "Bấm ngay vào link bên dưới để mua hàng với giá ưu đãi tốt nhất hôm nay nhé!"
    ]
    return script_steps

async def text_to_speech(text, out_path):
    """Tạo giọng đọc AI thuyết minh bằng edge-tts"""
    import edge_tts
    # Sử dụng giọng đọc chuẩn tiếng Việt của Microsoft Hoài My
    communicate = edge_tts.Communicate(text, voice="vi-VN-HoaiMyNeural", rate="+0%")
    await communicate.save(out_path)

def create_slide_video(image_path, audio_path, output_video, text, font_size=24):
    """Dựng một đoạn video ngắn từ 1 ảnh + 1 file audio + chữ đè lên"""
    # Lấy thời lượng chính xác của file audio thuyết minh
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    duration = float(subprocess.check_output(probe_cmd).strip())
    
    # Định dạng bộ lọc để vẽ chữ (drawtext) đè lên hình ảnh
    # Chia nhỏ text thành các dòng ngắn nếu quá dài
    wrapped_text = "\n".join([text[i:i+35] for i in range(0, len(text), 35)])
    
    # Chuyển đổi đường dẫn cho tương thích trên Windows/Linux
    img_clean = image_path.replace("\\", "/")
    aud_clean = audio_path.replace("\\", "/")
    out_clean = output_video.replace("\\", "/")
    
    # Render video từ ảnh tĩnh có thời lượng khớp với tiếng nói, chèn sub vào chính giữa dưới
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", img_clean,
        "-i", aud_clean,
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,drawtext=text='{wrapped_text}':fontcolor=white:fontsize={font_size}:box=1:boxcolor=black@0.6:boxborderw=10:x=(w-text_w)/2:y=h-250",
        "-c:v", "libx264", "-t", str(duration), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        out_clean
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

# --- THIẾT LẬP GIAO DIỆN CHÍNH ---

product_url = st.text_input("🔗 Nhập link sản phẩm của bạn:", placeholder="https://shopee.vn/ten-san-pham...")

if product_url:
    with st.spinner("🕵️ Đang cào dữ liệu và phân tích sản phẩm..."):
        data = scrape_product_info(product_url)
        
    if data and data["images"]:
        st.success(f"Tìm thấy sản phẩm: **{data['title']}**")
        st.write(f"Tìm thấy {len(data['images'])} hình ảnh hợp lệ.")
        
        # Hiển thị ảnh mẫu
        cols = st.columns(len(data["images"]))
        for idx, img_url in enumerate(data["images"]):
            cols[idx].image(img_url, use_container_width=True)
            
        # Cho phép chỉnh sửa lại kịch bản review nếu muốn
        st.subheader("📝 Kịch bản Review (Bạn có thể tự sửa lại từng câu):")
        scripts = generate_review_script(data["title"])
        edited_scripts = []
        for idx, step in enumerate(scripts):
            edited_txt = st.text_input(f"Đoạn {idx + 1}:", value=step)
            edited_scripts.append(edited_txt)
            
        # Nút dựng video
        if st.button("🎬 Bắt đầu xuất video Review"):
            tmp_dir = tempfile.mkdtemp(prefix="prod_review_")
            video_clips = []
            
            progress_text = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # 1. Tải hình ảnh
                progress_text.write("⏳ 1. Đang tải hình ảnh sản phẩm...")
                local_imgs = download_images(data["images"], tmp_dir)
                progress_bar.progress(20)
                
                if not local_imgs:
                    st.error("Không tải được hình ảnh nào từ trang web.")
                    st.stop()
                
                # 2. Tạo tiếng & dựng từng clip nhỏ (Slide)
                progress_text.write("⏳ 2. Đang chuyển ngữ và tạo giọng thuyết minh AI...")
                for idx, text in enumerate(edited_scripts):
                    # Đảm bảo ảnh lặp lại tuần hoàn nếu kịch bản nhiều dòng hơn số ảnh
                    img_path = local_imgs[idx % len(local_imgs)]
                    audio_path = os.path.join(tmp_dir, f"audio_{idx}.mp3")
                    clip_path = os.path.join(tmp_dir, f"clip_{idx}.mp4")
                    
                    # Tạo file giọng thuyết minh
                    asyncio.run(text_to_speech(text, audio_path))
                    
                    # Ghép thành video nhỏ
                    create_slide_video(img_path, audio_path, clip_path, text)
                    video_clips.append(clip_path)
                    
                progress_bar.progress(60)
                
                # 3. Nối các phân cảnh thành video TikTok/Shorts hoàn chỉnh (Khung hình đứng 1080x1920)
                progress_text.write("⏳ 3. Đang ghép nối các phân đoạn clip thành video hoàn chỉnh...")
                concat_list_path = os.path.join(tmp_dir, "concat_list.txt")
                with open(concat_list_path, "w") as f:
                    for clip in video_clips:
                        # Ffmpeg yêu cầu đường dẫn tuyệt đối với dấu gạch chéo xuôi
                        f.write(f"file '{clip.replace('\\', '/')}'\n")
                
                output_video_path = "review_product_output.mp4"
                concat_cmd = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", concat_list_path, "-c", "copy", output_video_path
                ]
                subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
                progress_bar.progress(100)
                progress_text.write("🎉 **Xuất video thành công!**")
                
                # Hiển thị video kết quả
                st.video(output_video_path)
                
                with open(output_video_path, "rb") as f:
                    st.download_button("📥 Tải video review về máy", f, file_name="review_san_pham.mp4", mime="video/mp4")
                    
            except Exception as e:
                st.error(f"Đã xảy ra lỗi khi render video: {e}")
    else:
        st.warning("Không thể tự động cào thông tin hoặc hình ảnh từ liên kết này. Hãy thử sử dụng một liên kết sản phẩm khác nhé.")