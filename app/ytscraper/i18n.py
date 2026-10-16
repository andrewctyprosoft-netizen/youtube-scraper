"""Interface text in English and Vietnamese. ``t(key)`` returns the active one."""
from __future__ import annotations

LANGS = {"en": "English", "vi": "Tiếng Việt"}

STRINGS: dict[str, dict[str, str]] = {
    # --- window / tabs
    "app_title": {"en": "YouTube Scraper", "vi": "YouTube Scraper"},
    "app_tagline": {
        "en": "Get transcripts, videos and audio from YouTube — paste links, pick, press Start.",
        "vi": "Lấy phụ đề, video và âm thanh từ YouTube — dán link, chọn, bấm Bắt đầu.",
    },
    "tab_download": {"en": "Download from YouTube", "vi": "Tải từ YouTube"},
    "tab_files": {"en": "Combine my files", "vi": "Gộp file của tôi"},
    "tab_settings": {"en": "Settings", "vi": "Cài đặt"},
    "tab_help": {"en": "Help", "vi": "Hướng dẫn"},
    # --- step 1
    "step1": {"en": "1  Add YouTube links", "vi": "1  Thêm link YouTube"},
    "step1_hint": {
        "en": "Paste one or many links (videos, playlists, channels). Lines that are not links are searched on YouTube.",
        "vi": "Dán một hoặc nhiều link (video, playlist, kênh). Dòng không phải link sẽ được tìm trên YouTube.",
    },
    "add_to_list": {"en": "Add to list", "vi": "Thêm vào danh sách"},
    "paste": {"en": "Paste", "vi": "Dán"},
    "open_txt": {"en": "Open link file…", "vi": "Mở file link…"},
    "clear_box": {"en": "Clear", "vi": "Xóa"},
    "loading_links": {"en": "Reading links…", "vi": "Đang đọc link…"},
    "loading_one": {"en": "Reading {what}…", "vi": "Đang đọc {what}…"},
    "added_n": {"en": "Added {n} videos.", "vi": "Đã thêm {n} video."},
    "nothing_found": {"en": "No YouTube links found in the box.", "vi": "Không tìm thấy link YouTube nào."},
    "list_failed": {"en": "Could not read: {what} ({why})", "vi": "Không đọc được: {what} ({why})"},
    "already_in_list": {"en": "{n} already in the list were skipped.", "vi": "Bỏ qua {n} video đã có trong danh sách."},
    # --- list
    "list_title": {"en": "Videos", "vi": "Danh sách video"},
    "col_title": {"en": "Title", "vi": "Tiêu đề"},
    "col_length": {"en": "Length", "vi": "Thời lượng"},
    "col_from": {"en": "From", "vi": "Nguồn"},
    "col_status": {"en": "Status", "vi": "Trạng thái"},
    "select_all": {"en": "Tick all", "vi": "Chọn hết"},
    "select_none": {"en": "Untick all", "vi": "Bỏ chọn hết"},
    "remove_unticked": {"en": "Remove unticked", "vi": "Xóa mục không chọn"},
    "tick_failed": {"en": "Tick failed only", "vi": "Chỉ chọn mục lỗi"},
    "clear_list": {"en": "Clear list", "vi": "Xóa danh sách"},
    "filter": {"en": "Filter titles…", "vi": "Lọc theo tiêu đề…"},
    "n_selected": {"en": "{sel} of {n} ticked", "vi": "Đã chọn {sel}/{n}"},
    "list_empty": {
        "en": "Your videos will appear here. Click a row's box to tick or untick it.",
        "vi": "Video sẽ hiện ở đây. Bấm vào ô đầu dòng để chọn hoặc bỏ chọn.",
    },
    "menu_open": {"en": "Open in browser", "vi": "Mở trên trình duyệt"},
    "menu_copy": {"en": "Copy link", "vi": "Sao chép link"},
    "menu_remove": {"en": "Remove from list", "vi": "Xóa khỏi danh sách"},
    "menu_tick_sel": {"en": "Tick highlighted rows", "vi": "Chọn các dòng đang tô"},
    "menu_untick_sel": {"en": "Untick highlighted rows", "vi": "Bỏ chọn các dòng đang tô"},
    "export_links": {"en": "Save links…", "vi": "Lưu link…"},
    # --- step 2
    "step2": {"en": "2  What do you want?", "vi": "2  Bạn muốn lấy gì?"},
    "want_transcript": {"en": "Transcript (text)", "vi": "Phụ đề (văn bản)"},
    "want_video": {"en": "Video (MP4)", "vi": "Video (MP4)"},
    "want_audio": {"en": "Audio (MP3)", "vi": "Âm thanh (MP3)"},
    "want_thumbnail": {"en": "Thumbnail picture", "vi": "Ảnh thu nhỏ"},
    "quality": {"en": "Quality", "vi": "Chất lượng"},
    "q_best": {"en": "Best available", "vi": "Cao nhất"},
    "transcript_opts": {"en": "Transcript options", "vi": "Tùy chọn phụ đề"},
    "language": {"en": "Language", "vi": "Ngôn ngữ"},
    "lang_orig": {"en": "Original (as spoken)", "vi": "Ngôn ngữ gốc của video"},
    "lang_other": {"en": "Other code…", "vi": "Mã khác…"},
    "lang_other_prompt": {
        "en": "Type a language code (e.g. pt, ar, zh-Hans):",
        "vi": "Nhập mã ngôn ngữ (vd: pt, ar, zh-Hans):",
    },
    "fallback": {
        "en": "Else use the video's own language",
        "vi": "Nếu không có, dùng ngôn ngữ gốc",
    },
    "fallback_hint": {
        "en": "Recommended. Machine-translated captions are slow and YouTube often blocks them.",
        "vi": "Khuyên dùng. Phụ đề dịch máy chậm và YouTube hay chặn.",
    },
    "allow_auto": {"en": "Allow auto-generated captions", "vi": "Cho phép phụ đề tự động"},
    "layout": {"en": "Layout", "vi": "Trình bày"},
    "layout_paragraphs": {"en": "Paragraphs", "vi": "Đoạn văn"},
    "layout_lines": {"en": "Line by line", "vi": "Từng dòng"},
    "timestamps": {"en": "Add timestamps [mm:ss]", "vi": "Thêm mốc thời gian [mm:ss]"},
    "rm_rolling": {"en": "Remove repeated lines (recommended)", "vi": "Xóa dòng bị lặp (khuyên dùng)"},
    "rm_all": {"en": "Also remove lines repeated anywhere", "vi": "Xóa cả dòng lặp lại ở bất kỳ đâu"},
    "rm_tags": {"en": "Remove [Music], [Applause]…", "vi": "Xóa [Âm nhạc], [Vỗ tay]…"},
    "save_as": {"en": "Save as", "vi": "Lưu thành"},
    "save_docx": {"en": "One Word file with all videos", "vi": "Một file Word gồm tất cả video"},
    "save_docx_files": {"en": "One Word file with all files", "vi": "Một file Word gồm tất cả file"},
    "save_txt": {"en": "A text file for each video", "vi": "Mỗi video một file văn bản"},
    "save_srt": {"en": "Subtitle file (.srt) for each video", "vi": "File phụ đề (.srt) cho mỗi video"},
    "save_combined_txt": {"en": "One text file with all videos", "vi": "Một file văn bản gồm tất cả video"},
    "save_csv": {"en": "Video list for Excel (.csv)", "vi": "Danh sách video cho Excel (.csv)"},
    "word_opts": {"en": "Word file", "vi": "File Word"},
    "doc_contents": {"en": "Clickable contents list", "vi": "Mục lục bấm được"},
    "doc_breaks": {"en": "Each video on a new page", "vi": "Mỗi video một trang mới"},
    "doc_info": {"en": "Show channel, date and link", "vi": "Hiện kênh, ngày đăng và link"},
    "doc_numbered": {"en": "Number the headings", "vi": "Đánh số tiêu đề"},
    # --- step 3
    "step3": {"en": "3  Save to", "vi": "3  Lưu vào"},
    "browse": {"en": "Choose…", "vi": "Chọn…"},
    "open_folder": {"en": "Open folder", "vi": "Mở thư mục"},
    "output_name": {"en": "File name", "vi": "Tên file"},
    "start": {"en": "Start", "vi": "Bắt đầu"},
    "stop": {"en": "Stop", "vi": "Dừng"},
    "nothing_ticked": {"en": "Tick at least one video in the list.", "vi": "Hãy chọn ít nhất một video trong danh sách."},
    "nothing_wanted": {"en": "Choose what to download in step 2.", "vi": "Hãy chọn nội dung cần tải ở bước 2."},
    "no_output_format": {
        "en": "Choose at least one 'Save as' option for the transcript.",
        "vi": "Hãy chọn ít nhất một cách lưu phụ đề.",
    },
    "need_ffmpeg": {
        "en": "Video and MP3 need ffmpeg.exe in the tools folder. It is missing.",
        "vi": "Video và MP3 cần ffmpeg.exe trong thư mục tools. Hiện đang thiếu.",
    },
    # --- progress / status
    "ready": {"en": "Ready.", "vi": "Sẵn sàng."},
    "working": {"en": "Working…", "vi": "Đang xử lý…"},
    "retry_wait": {
        "en": "Some videos failed — trying them again shortly…",
        "vi": "Một số video bị lỗi — sắp thử lại…",
    },
    "eta": {"en": "{per} s per video · about {left} min left", "vi": "{per} giây mỗi video · còn khoảng {left} phút"},
    "workers": {"en": "Parallel downloads (transcripts)", "vi": "Tải song song (phụ đề)"},
    "workers_hint": {
        "en": "2 is fast and safe. Use 1 if YouTube keeps asking you to slow down.",
        "vi": "2 là nhanh và an toàn. Chọn 1 nếu YouTube liên tục yêu cầu chậm lại.",
    },
    "rate_limited_wait": {
        "en": "YouTube asked us to slow down — waiting a minute, then continuing…",
        "vi": "YouTube yêu cầu chậm lại — chờ 1 phút rồi tiếp tục…",
    },
    "st_pending": {"en": "", "vi": ""},
    "st_working": {"en": "Working…", "vi": "Đang xử lý…"},
    "st_done": {"en": "✓ Done", "vi": "✓ Xong"},
    "st_no_captions": {"en": "No captions", "vi": "Không có phụ đề"},
    "st_error": {"en": "✗ Failed", "vi": "✗ Lỗi"},
    "st_skipped": {"en": "Skipped", "vi": "Bỏ qua"},
    "finished": {
        "en": "Finished: {done} done, {nocap} without captions, {err} failed.",
        "vi": "Hoàn tất: {done} xong, {nocap} không có phụ đề, {err} lỗi.",
    },
    "stopped": {"en": "Stopped.", "vi": "Đã dừng."},
    "files_saved": {"en": "Saved:", "vi": "Đã lưu:"},
    "open_result": {"en": "Open Word file", "vi": "Mở file Word"},
    "details": {"en": "Details", "vi": "Chi tiết"},
    "hide_details": {"en": "Hide details", "vi": "Ẩn chi tiết"},
    "busy": {"en": "Please wait for the current task to finish.", "vi": "Vui lòng chờ tác vụ hiện tại hoàn tất."},
    # --- errors (also used in the Word file for missing transcripts)
    "reason_no_captions": {
        "en": "(This video has no captions in the chosen language.)",
        "vi": "(Video này không có phụ đề ở ngôn ngữ đã chọn.)",
    },
    "reason_error": {"en": "(Could not download this video's captions.)", "vi": "(Không tải được phụ đề của video này.)"},
    "err_rate_limited": {
        "en": "YouTube is limiting requests. Wait a while or raise the delay in Settings.",
        "vi": "YouTube đang giới hạn. Chờ một lúc hoặc tăng thời gian nghỉ trong Cài đặt.",
    },
    "err_bot_check": {
        "en": "YouTube wants a sign-in check. Turn on 'Use my browser login' in Settings.",
        "vi": "YouTube yêu cầu xác minh. Bật 'Dùng đăng nhập trình duyệt' trong Cài đặt.",
    },
    "err_age": {"en": "Age-restricted: needs your browser login (Settings).", "vi": "Giới hạn độ tuổi: cần đăng nhập trình duyệt (Cài đặt)."},
    "err_members": {"en": "Members-only video.", "vi": "Video chỉ dành cho hội viên."},
    "err_private": {"en": "Private video.", "vi": "Video riêng tư."},
    "err_unavailable": {"en": "Video unavailable or removed.", "vi": "Video không còn hoặc đã bị xóa."},
    "err_upcoming": {"en": "Not released yet (premiere/live).", "vi": "Chưa phát hành (công chiếu/trực tiếp)."},
    "err_no_ffmpeg": {"en": "ffmpeg is missing.", "vi": "Thiếu ffmpeg."},
    "err_network": {"en": "Network problem. Check your internet.", "vi": "Lỗi mạng. Kiểm tra kết nối internet."},
    "err_outdated": {
        "en": "The download engine is out of date. Settings → Update engine.",
        "vi": "Bộ tải đã cũ. Cài đặt → Cập nhật bộ tải.",
    },
    "err_unknown": {"en": "Unexpected error (see Details).", "vi": "Lỗi không xác định (xem Chi tiết)."},
    "available_langs": {"en": "Available: {langs}", "vi": "Có sẵn: {langs}"},
    # --- files tab
    "files_title": {"en": "Clean and combine caption files you already have", "vi": "Làm sạch và gộp các file phụ đề bạn đã có"},
    "files_hint": {
        "en": "Add .srt, .vtt or .txt files. Each file becomes a heading (its file name) in one Word document.",
        "vi": "Thêm file .srt, .vtt hoặc .txt. Mỗi file thành một tiêu đề (tên file) trong một file Word.",
    },
    "add_files": {"en": "Add files…", "vi": "Thêm file…"},
    "add_folder": {"en": "Add folder…", "vi": "Thêm thư mục…"},
    "sort_by": {"en": "Order", "vi": "Thứ tự"},
    "sort_name": {"en": "By name (1, 2, 10)", "vi": "Theo tên (1, 2, 10)"},
    "sort_date": {"en": "By date modified", "vi": "Theo ngày sửa"},
    "sort_added": {"en": "As added", "vi": "Theo thứ tự thêm"},
    "move_up": {"en": "▲ Up", "vi": "▲ Lên"},
    "move_down": {"en": "▼ Down", "vi": "▼ Xuống"},
    "remove": {"en": "Remove", "vi": "Xóa"},
    "files_save_txt": {"en": "Clean text file for each file", "vi": "File văn bản sạch cho mỗi file"},
    "files_save_srt": {"en": "Clean .srt for each subtitle file", "vi": "File .srt sạch cho mỗi file phụ đề"},
    "combine": {"en": "Combine", "vi": "Gộp"},
    "no_files": {"en": "Add some files first.", "vi": "Hãy thêm file trước."},
    "col_file": {"en": "File", "vi": "File"},
    "col_folder": {"en": "Folder", "vi": "Thư mục"},
    # --- settings
    "ui_language": {"en": "Interface language", "vi": "Ngôn ngữ giao diện"},
    "appearance": {"en": "Appearance", "vi": "Giao diện"},
    "theme_system": {"en": "Follow Windows", "vi": "Theo Windows"},
    "theme_light": {"en": "Light", "vi": "Sáng"},
    "theme_dark": {"en": "Dark", "vi": "Tối"},
    "delay": {"en": "Pause between videos (seconds)", "vi": "Nghỉ giữa các video (giây)"},
    "delay_hint": {
        "en": "1 s is enough for transcripts. Raise it to 2–5 s if YouTube asks you to slow down.",
        "vi": "1 giây là đủ cho phụ đề. Tăng lên 2–5 giây nếu YouTube yêu cầu chậm lại.",
    },
    "numbered_files": {"en": "Number file names in this order (001 - …)", "vi": "Đánh số tên file theo thứ tự này (001 - …)"},
    "order": {"en": "Order", "vi": "Thứ tự"},
    "order_list": {"en": "As listed", "vi": "Như danh sách"},
    "order_az": {"en": "Title A → Z", "vi": "Tên A → Z"},
    "order_za": {"en": "Title Z → A", "vi": "Tên Z → A"},
    "order_hint": {
        "en": "Files are named after the video title. The order also sets the Word file and the list.",
        "vi": "File được đặt theo tên video. Thứ tự này cũng áp dụng cho file Word và danh sách.",
    },
    "reuse_cache": {
        "en": "Reuse captions already downloaded (faster, fewer requests)",
        "vi": "Dùng lại phụ đề đã tải (nhanh hơn, ít yêu cầu hơn)",
    },
    "search_count": {"en": "Search results per search", "vi": "Số kết quả mỗi lần tìm"},
    "list_limit": {"en": "Max videos per playlist/channel (0 = all)", "vi": "Tối đa video mỗi playlist/kênh (0 = tất cả)"},
    "login": {"en": "Use my browser login", "vi": "Dùng đăng nhập trình duyệt"},
    "login_hint": {
        "en": "Only for age-restricted, members-only or 'confirm you're not a bot' videos. Firefox works best; close Chrome/Edge first.",
        "vi": "Chỉ cần cho video giới hạn tuổi, hội viên hoặc khi YouTube hỏi 'xác nhận không phải bot'. Firefox ổn định nhất; hãy đóng Chrome/Edge trước.",
    },
    "login_none": {"en": "Don't use (recommended)", "vi": "Không dùng (khuyên dùng)"},
    "login_file": {"en": "cookies.txt file…", "vi": "File cookies.txt…"},
    "engine": {"en": "Download engine", "vi": "Bộ tải"},
    "engine_version": {"en": "yt-dlp version: {v}", "vi": "Phiên bản yt-dlp: {v}"},
    "engine_old": {
        "en": "⚠ {days} days old — update it if downloads fail.",
        "vi": "⚠ Đã {days} ngày — hãy cập nhật nếu tải bị lỗi.",
    },
    "engine_ok": {"en": "✓ Up to date enough", "vi": "✓ Còn mới"},
    "update_engine": {"en": "Update engine", "vi": "Cập nhật bộ tải"},
    "updating": {"en": "Updating…", "vi": "Đang cập nhật…"},
    "update_ok": {"en": "Engine updated: {v}", "vi": "Đã cập nhật bộ tải: {v}"},
    "update_fail": {"en": "Update failed. See Details.", "vi": "Cập nhật lỗi. Xem Chi tiết."},
    "components": {"en": "Components", "vi": "Thành phần"},
    "comp_found": {"en": "found", "vi": "có"},
    "comp_missing": {"en": "missing", "vi": "thiếu"},
    "comp_ytdlp": {"en": "yt-dlp (required)", "vi": "yt-dlp (bắt buộc)"},
    "comp_deno": {"en": "Deno (for video formats)", "vi": "Deno (cho định dạng video)"},
    "comp_ffmpeg": {"en": "ffmpeg (for MP4 merge / MP3)", "vi": "ffmpeg (ghép MP4 / MP3)"},
    "default_folder": {"en": "Default save folder", "vi": "Thư mục lưu mặc định"},
    "save_settings_note": {"en": "Settings are saved automatically.", "vi": "Cài đặt được lưu tự động."},
    # --- dialogs
    "pick_folder": {"en": "Choose where to save", "vi": "Chọn nơi lưu"},
    "pick_txt": {"en": "Open a text file with links", "vi": "Mở file văn bản chứa link"},
    "confirm_clear": {"en": "Remove all videos from the list?", "vi": "Xóa toàn bộ video khỏi danh sách?"},
    "confirm_stop": {"en": "Stop now? Finished videos are kept.", "vi": "Dừng ngay? Các video đã xong vẫn được giữ."},
    "ok": {"en": "OK", "vi": "OK"},
    "cancel": {"en": "Cancel", "vi": "Hủy"},
    # --- Word labels
    "doc_label_contents": {"en": "Contents", "vi": "Mục lục"},
    "doc_label_created": {"en": "Created", "vi": "Tạo lúc"},
    "doc_label_videos": {"en": "videos", "vi": "video"},
    "doc_label_empty": {"en": "(No transcript text)", "vi": "(Không có nội dung phụ đề)"},
    # --- help
    "help_text": {
        "en": (
            "HOW TO USE\n\n"
            "1. Copy links from YouTube (a video, a playlist or a channel) and paste them into the box. "
            "You can paste many at once, or open a .txt file with one link per line. "
            "Typing words instead of a link searches YouTube.\n\n"
            "2. Click 'Add to list'. Playlists and channels turn into their videos. "
            "Untick the ones you don't want (click the box at the start of a row). "
            "Use the filter box to find titles.\n\n"
            "3. Choose what you want: transcript, video, audio or thumbnail. "
            "For transcripts pick the language and how to save them. "
            "'One Word file with all videos' puts every transcript in one document, with each video's name as a heading.\n\n"
            "4. Choose the folder and press Start. When it finishes, click 'Open Word file' or 'Open folder'.\n\n"
            "TIPS\n\n"
            "• Auto-generated captions repeat every line; 'Remove repeated lines' cleans this up.\n"
            "• Files are named after the video title. In step 3 choose the order (as listed, A → Z, Z → A) "
            "and tick 'Number file names' to get 001, 002, … in that order.\n"
            "• Already have .srt files? Use the 'Combine my files' tab.\n"
            "• If downloads suddenly fail, go to Settings → Update engine. YouTube changes often.\n"
            "• For very long lists, keep a 2–5 second pause (Settings) to avoid being blocked.\n"
            "• Only download content you have the right to use."
        ),
        "vi": (
            "CÁCH DÙNG\n\n"
            "1. Sao chép link từ YouTube (video, playlist hoặc kênh) rồi dán vào ô. "
            "Có thể dán nhiều link cùng lúc, hoặc mở file .txt mỗi dòng một link. "
            "Gõ chữ thay vì link sẽ tìm kiếm trên YouTube.\n\n"
            "2. Bấm 'Thêm vào danh sách'. Playlist và kênh sẽ được mở thành từng video. "
            "Bỏ chọn video không cần (bấm vào ô đầu dòng). Dùng ô lọc để tìm theo tiêu đề.\n\n"
            "3. Chọn nội dung cần lấy: phụ đề, video, âm thanh hoặc ảnh thu nhỏ. "
            "Với phụ đề, chọn ngôn ngữ và cách lưu. "
            "'Một file Word gồm tất cả video' gộp mọi phụ đề vào một tài liệu, tên video là tiêu đề.\n\n"
            "4. Chọn thư mục lưu và bấm Bắt đầu. Xong thì bấm 'Mở file Word' hoặc 'Mở thư mục'.\n\n"
            "MẸO\n\n"
            "• Phụ đề tự động hay lặp lại từng dòng; 'Xóa dòng bị lặp' sẽ làm sạch.\n"
            "• File được đặt theo tên video. Ở bước 3 chọn thứ tự (như danh sách, A → Z, Z → A) "
            "và tích 'Đánh số tên file' để có 001, 002, … theo thứ tự đó.\n"
            "• Đã có sẵn file .srt? Dùng thẻ 'Gộp file của tôi'.\n"
            "• Nếu tải đột nhiên bị lỗi, vào Cài đặt → Cập nhật bộ tải. YouTube thay đổi thường xuyên.\n"
            "• Với danh sách dài, để nghỉ 2–5 giây (Cài đặt) để tránh bị chặn.\n"
            "• Chỉ tải nội dung bạn có quyền sử dụng."
        ),
    },
}

CAPTION_LANGUAGES = [
    ("en", "English"),
    ("vi", "Tiếng Việt"),
    ("orig", None),  # label from lang_orig
    ("zh-Hans", "中文 (简体)"),
    ("zh-Hant", "中文 (繁體)"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("th", "ไทย"),
    ("id", "Bahasa Indonesia"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("es", "Español"),
    ("ru", "Русский"),
    ("hi", "हिन्दी"),
]

_current = "en"


def set_language(code: str) -> None:
    """Switch the interface language."""
    global _current
    _current = code if code in LANGS else "en"


def current_language() -> str:
    """Active interface language code."""
    return _current


def t(key: str, **kwargs: object) -> str:
    """Translated string for ``key`` (falls back to English, then the key)."""
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_current) or entry.get("en") or key
    return text.format(**kwargs) if kwargs else text
