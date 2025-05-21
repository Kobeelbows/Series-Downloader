import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import re
import json
import os
import threading
import subprocess

# Attempt to import yt_dlp and its specific DownloadError
YTDLPDownloadError = None # Placeholder for the specific error class
try:
    import yt_dlp
    from yt_dlp.utils import DownloadError as _YTDLPDownloadError_Imported
    YTDLPDownloadError = _YTDLPDownloadError_Imported
except ImportError:
    yt_dlp = None # yt_dlp will be None if import fails

# Attempt to import pyperclip, if not installed, pyperclip will be None
try:
    import pyperclip
except ImportError:
    pyperclip = None

class BilibiliCrawler:
    def __init__(self, root):
        self.root = root
        self.root.title("Bili-Series-Downloader")
        self.root.geometry("800x700") 
        self.root.resizable(True, True)

        # --- 用户可配置的 FFmpeg 路径 ---
        # 如果程序无法自动找到 FFmpeg，请取消下面一行的注释，并将其设置为你的 FFmpeg bin 文件夹的路径。
        # 例如: self.ffmpeg_directory_override = r"C:\ProgramData\chocolatey\bin"
        # 或者: self.ffmpeg_directory_override = r"C:\ffmpeg\bin"
        # MODIFIED: Set to user's provided path
        self.ffmpeg_directory_override = r"C:\ProgramData\chocolatey\bin" 
        # --- 用户可配置的 FFmpeg 路径结束 ---

        # Set styles
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, relief="flat")
        self.style.map("TButton", background=[('active', '#1E90FF'), ('!disabled', '#D0D0D0')])
        self.style.configure("TLabel", padding=6)
        self.style.configure("TFrame", background="#F0F0F0")

        # Main frame
        self.main_frame = ttk.Frame(root, padding="10 10 10 10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Input area
        input_frame = ttk.Frame(self.main_frame)
        input_frame.pack(fill=tk.X, pady=5)
        ttk.Label(input_frame, text="请输入B站视频地址:").pack(side=tk.LEFT, padx=(0, 5))
        self.url_entry = ttk.Entry(input_frame, width=60)
        self.url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.crawl_button = ttk.Button(input_frame, text="获取链接", command=self.start_crawl_videos)
        self.crawl_button.pack(side=tk.LEFT, padx=5)

        # Results area
        result_frame = ttk.Frame(self.main_frame)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        ttk.Label(result_frame, text="视频链接列表:").pack(anchor=tk.W)
        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD, height=15, relief=tk.SOLID, borderwidth=1)
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # Action buttons row 1
        action_frame_row1 = ttk.Frame(self.main_frame)
        action_frame_row1.pack(fill=tk.X, pady=(5,0))
        
        self.copy_button = ttk.Button(action_frame_row1, text="一键复制", command=self.copy_links)
        self.copy_button.pack(side=tk.LEFT, padx=5)
        self.clear_button = ttk.Button(action_frame_row1, text="清除", command=self.clear_results)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        self.folder_button = ttk.Button(action_frame_row1, text="选择下载目录", command=self.choose_folder)
        self.folder_button.pack(side=tk.LEFT, padx=5)
        
        # Action buttons row 2 (Download options)
        action_frame_row2 = ttk.Frame(self.main_frame)
        action_frame_row2.pack(fill=tk.X, pady=(2,5))

        self.download_button = ttk.Button(action_frame_row2, text="下载视频", command=self.start_download_videos)
        self.download_button.pack(side=tk.LEFT, padx=5)

        self.download_mode_label = ttk.Label(action_frame_row2, text="下载模式:")
        self.download_mode_label.pack(side=tk.LEFT, padx=(10, 2)) 
        self.download_mode_var = tk.StringVar()
        self.download_mode_options = {
            "合并音视频 (推荐FFmpeg)": "merge", 
            "仅音频 (元数据推荐FFmpeg)": "audio_only",
            "仅视频 (去声/元数据推荐FFmpeg)": "video_only" 
        }
        self.download_mode_combo = ttk.Combobox(
            action_frame_row2,
            textvariable=self.download_mode_var,
            values=list(self.download_mode_options.keys()),
            state="readonly",
            width=28 
        )
        self.download_mode_combo.pack(side=tk.LEFT, padx=5)
        self.download_mode_combo.set(list(self.download_mode_options.keys())[0])

        # Status bar
        self.status_var = tk.StringVar(value="准备就绪")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Storage
        self.video_links = [] 
        self.download_folder = os.getcwd() 
        self.status_var.set(f"准备就绪. 下载目录: {self.download_folder}")
        self.current_video_idx = 0 

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com'
        }

    def _update_gui_safe(self, func, *args, **kwargs):
        self.root.after(0, lambda: func(*args, **kwargs))

    def _check_thread_status(self, thread, button_to_enable):
        if thread.is_alive():
            self.root.after(100, lambda: self._check_thread_status(thread, button_to_enable))
        else:
            if button_to_enable:
                self._update_gui_safe(button_to_enable.config, state=tk.NORMAL)
    
    def extract_bvid(self, url):
        bv_pattern = r'BV[1-9A-HJ-NP-Za-km-z]{10}'
        match = re.search(bv_pattern, url)
        return match.group(0) if match else None

    def extract_song_title(self, text_content):
        try:
            last_start_bracket = text_content.rfind('《')
            if last_start_bracket != -1:
                first_end_bracket_after_last_start = text_content.find('》', last_start_bracket + 1)
                if first_end_bracket_after_last_start != -1:
                    extracted = text_content[last_start_bracket + 1:first_end_bracket_after_last_start].strip()
                    if extracted: 
                        return extracted
        except Exception:
            pass 
        return None

    def sanitize_filename(self, filename):
        if not isinstance(filename, str): 
            filename = str(filename)
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = re.sub(r'[\x00-\x1F\x7F]', '', sanitized) 
        return sanitized[:200] 


    def get_collection_id(self, bvid, video_data_ref): 
        try:
            video_url = f'https://www.bilibili.com/video/{bvid}'
            resp = requests.get(video_url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            
            initial_state_json = None
            match_initial_state = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', resp.text)
            if match_initial_state:
                initial_state_json = match_initial_state.group(1)
            
            if initial_state_json:
                try:
                    data = json.loads(initial_state_json)
                    current_video_data = data.get('videoData', {})
                    if video_data_ref is not None and isinstance(video_data_ref, list):
                        video_data_ref.clear() 
                        video_data_ref.append(current_video_data)

                    ugc_season_data = current_video_data.get('ugc_season')
                    if isinstance(ugc_season_data, dict) and \
                       ugc_season_data.get('id') and \
                       ugc_season_data.get('id') != 0: 
                        return ugc_season_data['id']
                
                except json.JSONDecodeError:
                    self._update_gui_safe(messagebox.showerror, "解析错误", "无法解析视频页面数据 (INITIAL_STATE)。")
            return None
        except requests.exceptions.RequestException as e:
            self._update_gui_safe(messagebox.showerror, "网络错误", f"获取视频信息失败: {e}")
            return None
        except Exception as e: 
            self._update_gui_safe(messagebox.showerror, "错误", f"提取合集ID时发生未知错误: {e}")
            return None

    def get_collection_videos(self, season_id, max_items=1000, progress_callback=None):
        videos = []
        page_size = 30
        page_num = 1
        while len(videos) < max_items:
            if progress_callback:
                progress_callback(f"拉取合集内容 (ID: {season_id}) - 第 {page_num} 页...")
            
            api_url = f'https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?mid=0&season_id={season_id}&sort_reverse=false&page_num={page_num}&page_size={page_size}'
            try:
                r = requests.get(api_url, headers=self.headers, timeout=10)
                r.raise_for_status()
                data = r.json()

                if data.get('code') != 0:
                    if progress_callback:
                        progress_callback(f"API错误: {data.get('message', '未知API错误')}")
                    break 
                archives = data.get('data', {}).get('archives', [])
                if not archives:
                    break
                for v_data in archives: 
                    if len(videos) < max_items:
                        bilibili_raw_title = v_data.get('title', '未知标题').strip()
                        preferred_song_title = self.extract_song_title(bilibili_raw_title)
                        
                        display_title = preferred_song_title if preferred_song_title else bilibili_raw_title
                        audio_filename_base = preferred_song_title if preferred_song_title else bilibili_raw_title
                        video_filename_base = bilibili_raw_title 
                        metadata_title_raw = preferred_song_title if preferred_song_title else bilibili_raw_title

                        author_name = v_data.get('owner', {}).get('name', '未知作者')
                        videos.append({
                            'display_title': self.sanitize_filename(display_title),
                            'audio_filename_base': self.sanitize_filename(audio_filename_base),
                            'video_filename_base': self.sanitize_filename(video_filename_base),
                            'metadata_title_raw': metadata_title_raw, 
                            'url': f"https://www.bilibili.com/video/{v_data.get('bvid','')}?p={v_data.get('page',{}).get('page',1)}" if v_data.get('bvid') else '',
                            'author': author_name
                        })
                    else:
                        break
                if len(archives) < page_size: 
                    break
                page_num += 1
            except requests.exceptions.RequestException as e:
                if progress_callback: progress_callback(f"网络错误 (页 {page_num}): {e}")
                break
            except json.JSONDecodeError:
                if progress_callback: progress_callback(f"API响应解析错误 (页 {page_num})")
                break
            except Exception as e:
                if progress_callback: progress_callback(f"未知错误 (页 {page_num}): {e}")
                break
        return videos[:max_items]

    def _display_crawl_results(self, crawled_videos):
        if not crawled_videos:
            self.result_text.insert(tk.END, "未能获取到任何视频链接。\n")
            self.status_var.set("未找到视频或获取失败")
            return

        self.video_links = crawled_videos 
        text_to_display = "".join([f"{i+1}. {v['display_title']} (作者: {v.get('author', '未知')})\n{v['url']}\n\n" for i, v in enumerate(crawled_videos)])
        self.result_text.insert(tk.END, text_to_display)
        self.status_var.set(f"成功获取 {len(crawled_videos)} 条视频链接")

    def _crawl_videos_worker(self, url):
        try:
            self._update_gui_safe(self.status_var.set, "正在提取BV号...")
            bvid = self.extract_bvid(url)
            if not bvid:
                self._update_gui_safe(messagebox.showwarning, "无效输入", "未能从输入地址中提取有效的BV号。")
                self._update_gui_safe(self.status_var.set, "BV号提取失败")
                return

            self._update_gui_safe(self.status_var.set, f"正在获取视频信息 (BV号: {bvid})...")
            
            initial_video_data_container = [] 
            season_id = self.get_collection_id(bvid, initial_video_data_container)

            if season_id: 
                self._update_gui_safe(self.status_var.set, f"检测到合集 (ID: {season_id})，正在拉取列表...")
                crawled_videos = self.get_collection_videos(
                    season_id, 1000, 
                    progress_callback=lambda msg: self._update_gui_safe(self.status_var.set, msg)
                )
                if not crawled_videos:
                    self._update_gui_safe(messagebox.showinfo, "提示", "未能从该合集获取到任何视频。")
                    self._update_gui_safe(self.status_var.set, "合集为空或获取失败")
                self._update_gui_safe(self._display_crawl_results, crawled_videos)
            
            else: 
                self._update_gui_safe(self.status_var.set, f"处理单个视频 (BV号: {bvid})...")
                author_name = "未知作者"
                video_title_overall = bvid 
                video_pages_data = []

                if initial_video_data_container: 
                    video_data = initial_video_data_container[0]
                    owner_info = video_data.get('owner', {})
                    author_name = owner_info.get('name', '未知作者')
                    video_title_overall = video_data.get('title', bvid).strip()
                    video_pages_data = video_data.get('pages', [])
                else: 
                    try:
                        self._update_gui_safe(self.status_var.set, f"重新获取页面数据 (BV号: {bvid})...")
                        video_url_fallback = f'https://www.bilibili.com/video/{bvid}'
                        resp_fallback = requests.get(video_url_fallback, headers=self.headers, timeout=10)
                        resp_fallback.raise_for_status()
                        
                        match_initial_state_fallback = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', resp_fallback.text)
                        if match_initial_state_fallback:
                            initial_state_json_fallback = match_initial_state_fallback.group(1)
                            data_fallback = json.loads(initial_state_json_fallback)
                            video_data_fallback = data_fallback.get('videoData', {})
                            
                            owner_info_fallback = video_data_fallback.get('owner', {})
                            author_name = owner_info_fallback.get('name', '未知作者')
                            video_title_overall = video_data_fallback.get('title', bvid).strip()
                            video_pages_data = video_data_fallback.get('pages', [])
                        else: 
                            title_match_fallback = re.search(r'<title[^>]*>(.*?)</title>', resp_fallback.text, re.IGNORECASE | re.DOTALL)
                            if title_match_fallback:
                                video_title_overall = title_match_fallback.group(1).split('_哔哩哔哩')[0].strip()
                    except Exception as e_fallback:
                        self._update_gui_safe(self.status_var.set, f"重新获取页面数据失败: {e_fallback}")

                single_video_list = []
                if video_pages_data and isinstance(video_pages_data, list) and len(video_pages_data) > 0:
                    self._update_gui_safe(self.status_var.set, f"检测到多P视频，共 {len(video_pages_data)} P...")
                    for part_info in video_pages_data:
                        part_raw_title = part_info.get('part', video_title_overall).strip() 
                        page_num = part_info.get('page', 1)
                        preferred_song_title = self.extract_song_title(part_raw_title)
                        display_title = preferred_song_title if preferred_song_title else part_raw_title
                        audio_filename_base = preferred_song_title if preferred_song_title else part_raw_title
                        video_filename_base = part_raw_title 
                        metadata_title_raw = preferred_song_title if preferred_song_title else part_raw_title
                        single_video_list.append({
                            'display_title': self.sanitize_filename(display_title), 
                            'audio_filename_base': self.sanitize_filename(audio_filename_base),
                            'video_filename_base': self.sanitize_filename(video_filename_base),
                            'metadata_title_raw': metadata_title_raw,
                            'url': f"https://www.bilibili.com/video/{bvid}?p={page_num}", 
                            'author': author_name
                        })
                else:
                    preferred_song_title = self.extract_song_title(video_title_overall)
                    display_title = preferred_song_title if preferred_song_title else video_title_overall
                    audio_filename_base = preferred_song_title if preferred_song_title else video_title_overall
                    video_filename_base = video_title_overall
                    metadata_title_raw = preferred_song_title if preferred_song_title else video_title_overall
                    single_video_list.append({
                        'display_title': self.sanitize_filename(display_title), 
                        'audio_filename_base': self.sanitize_filename(audio_filename_base),
                        'video_filename_base': self.sanitize_filename(video_filename_base),
                        'metadata_title_raw': metadata_title_raw,
                        'url': f"https://www.bilibili.com/video/{bvid}", 
                        'author': author_name
                    })
                
                if not single_video_list: 
                     self._update_gui_safe(messagebox.showinfo, "提示", "未能解析该单个视频的信息。")
                     self._update_gui_safe(self.status_var.set, "单个视频解析失败")
                else:
                    self._update_gui_safe(self._display_crawl_results, single_video_list)

        except requests.exceptions.RequestException as e:
            self._update_gui_safe(messagebox.showerror, "网络错误", f"爬取过程中发生网络错误: {e}")
            self._update_gui_safe(self.status_var.set, f"网络错误: {e}")
        except Exception as e:
            self._update_gui_safe(messagebox.showerror, "严重错误", f"爬取过程中发生未知错误: {e}")
            self._update_gui_safe(self.status_var.set, f"严重错误: {e}")

    def start_crawl_videos(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("警告", "请输入B站视频或合集链接。")
            return
        self.crawl_button.config(state=tk.DISABLED)
        self.result_text.delete(1.0, tk.END)
        self.video_links = []
        self._update_gui_safe(self.status_var.set, "正在处理请求...")
        thread = threading.Thread(target=self._crawl_videos_worker, args=(url,), daemon=True)
        thread.start()
        self._check_thread_status(thread, self.crawl_button)

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.download_folder)
        if folder:
            self.download_folder = folder
            self.status_var.set(f"下载目录已选择: {folder}")

    def _download_videos_worker(self):
        try:
            ffmpeg_executable_path = 'ffmpeg' # Default to PATH
            ffmpeg_directory_to_use = None

            if self.ffmpeg_directory_override and os.path.isdir(self.ffmpeg_directory_override):
                ffmpeg_executable_path = os.path.join(self.ffmpeg_directory_override, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
                ffmpeg_directory_to_use = self.ffmpeg_directory_override
                print(f"FFmpeg check: Attempting to use FFmpeg from override directory: {self.ffmpeg_directory_override}")
            else:
                print("FFmpeg check: Override directory not set or invalid. Attempting to use FFmpeg from system PATH.")

            ffmpeg_is_available = False
            try:
                startupinfo = None
                if os.name == 'nt': 
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                subprocess.run([ffmpeg_executable_path, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
                ffmpeg_is_available = True
                print(f"FFmpeg check: Successfully executed '{ffmpeg_executable_path} -version'. FFmpeg is available.")
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                print(f"FFmpeg check: Failed to execute '{ffmpeg_executable_path} -version'. Error: {e}")
                self._update_gui_safe(messagebox.showerror, "依赖缺失", f"未能找到或执行 FFmpeg。\n尝试路径: {ffmpeg_executable_path}\n请安装 FFmpeg 并确保它在系统路径中，或者在代码中正确设置 ffmpeg_directory_override。")
                self._update_gui_safe(self.status_var.set, "FFmpeg 未找到或无法执行，下载中止。")
            finally: 
                if not ffmpeg_is_available:
                    self._update_gui_safe(self.download_button.config, state=tk.NORMAL) 
                    return 

            links_to_download = list(self.video_links) 
            total_videos = len(links_to_download)
            download_count = 0
            failed_downloads = []

            selected_mode_key = self.download_mode_var.get()
            actual_mode = self.download_mode_options.get(selected_mode_key, "merge")
            
            progress_hook = lambda d: self._yt_dlp_progress_hook(d, self.current_video_idx, total_videos)
            postprocessor_hook = lambda d: self._yt_dlp_postprocessor_hook(d, self.current_video_idx, total_videos)
            
            for idx, video_info in enumerate(links_to_download):
                self.current_video_idx = idx 
                
                title_for_filename = ""
                if actual_mode == "audio_only":
                    title_for_filename = video_info.get('audio_filename_base', '未知音频标题')
                else: 
                    title_for_filename = video_info.get('video_filename_base', '未知视频标题')
                
                if not isinstance(title_for_filename, str):
                    title_for_filename = str(title_for_filename)

                current_outtmpl = os.path.join(self.download_folder, f"{title_for_filename}.%(ext)s")

                loop_ydl_opts = {
                    'noplaylist': True,
                    'nocheckcertificate': True,
                    'quiet': False, 
                    'ignoreerrors': False, 
                    'progress_hooks': [progress_hook],
                    'postprocessor_hooks': [postprocessor_hook],
                    'restrictfilenames': False, 
                    'add_metadata': True, 
                    'outtmpl': current_outtmpl, 
                    'postprocessors': [], 
                    'postprocessor_args': {} 
                }

                if ffmpeg_directory_to_use: 
                    loop_ydl_opts['ffmpeg_location'] = ffmpeg_directory_to_use
                    print(f"yt-dlp: Using ffmpeg_location: {ffmpeg_directory_to_use}")


                if actual_mode == "audio_only":
                    loop_ydl_opts['format'] = 'bestaudio/best'
                    loop_ydl_opts['extract_audio'] = True 
                    loop_ydl_opts['audio_format'] = 'm4a' 
                elif actual_mode == "merge":
                    loop_ydl_opts['format'] = 'bestvideo+bestaudio/best'
                    loop_ydl_opts['merge_output_format'] = 'mp4'
                    loop_ydl_opts['postprocessors'] = [{'key': 'FFmpegMerger'}] 
                elif actual_mode == "video_only":
                    loop_ydl_opts['format'] = 'bestvideo[acodec=none]/bestvideo' 
                    if not any(pp.get('key') == 'FFmpegVideoConvertor' for pp in loop_ydl_opts['postprocessors']):
                        loop_ydl_opts['postprocessors'].append(
                            {'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}
                        )
                    if 'FFmpegVideoConvertor' not in loop_ydl_opts['postprocessor_args']:
                        loop_ydl_opts['postprocessor_args']['FFmpegVideoConvertor'] = []
                    if '-an' not in loop_ydl_opts['postprocessor_args']['FFmpegVideoConvertor']:
                         loop_ydl_opts['postprocessor_args']['FFmpegVideoConvertor'].append('-an')

                if not any(pp.get('key') == 'FFmpegMetadata' for pp in loop_ydl_opts['postprocessors']):
                    loop_ydl_opts['postprocessors'].append({'key': 'FFmpegMetadata'})
                
                author_for_metadata = video_info.get("author", "未知作者")
                metadata_title_tag = video_info.get('metadata_title_raw', '未知标题')
                if not isinstance(metadata_title_tag, str): metadata_title_tag = str(metadata_title_tag)

                loop_ydl_opts['postprocessor_args']['FFmpegMetadata'] = [
                    '-metadata', f'artist={author_for_metadata}', 
                    '-metadata', f'album_artist={author_for_metadata}', 
                    '-metadata', f'title={metadata_title_tag}'
                ]
                
                if actual_mode == "video_only": 
                    if any(pp.get('key') == 'FFmpegVideoConvertor' for pp in loop_ydl_opts['postprocessors']):
                        if 'FFmpegVideoConvertor' not in loop_ydl_opts['postprocessor_args']:
                             loop_ydl_opts['postprocessor_args']['FFmpegVideoConvertor'] = []
                        if '-an' not in loop_ydl_opts['postprocessor_args']['FFmpegVideoConvertor']:
                            loop_ydl_opts['postprocessor_args']['FFmpegVideoConvertor'].append('-an')
                
                self._update_gui_safe(self.status_var.set, f"准备下载 ({idx+1}/{total_videos}): {video_info['display_title'][:30]} (作者: {author_for_metadata[:15]})")
                
                try:
                    with yt_dlp.YoutubeDL(loop_ydl_opts) as ydl: 
                        ydl.download([video_info['url']]) 
                    download_count +=1
                except Exception as e: 
                    error_message = str(e)
                    is_ytdlp_error = YTDLPDownloadError is not None and isinstance(e, YTDLPDownloadError)
                    
                    if is_ytdlp_error:
                        print(f"yt-dlp DownloadError for '{video_info['display_title']}': {error_message}")
                        if "ffmpeg" in error_message.lower() or "ffprobe" in error_message.lower() or "merge" in error_message.lower():
                            error_message_display = f"合并/处理失败 (FFmpeg相关): {error_message}"
                        else:
                            error_message_display = f"yt-dlp 下载/处理错误: {error_message}"
                    else: 
                        print(f"下载 '{video_info['display_title']}' 时发生一般错误: {error_message}")
                        error_message_display = f"下载时发生未知错误: {error_message}"
                    
                    failed_downloads.append(f"{video_info['display_title']} (URL: {video_info['url']}) - Error: {error_message_display}")
                    self._update_gui_safe(self.status_var.set, f"失败 ({idx+1}/{total_videos}): {video_info['display_title'][:30]}...")
            
            final_message = f"下载任务完成。成功下载 {download_count}/{total_videos} 个文件。"
            if failed_downloads:
                final_message += "\n\n以下文件下载失败:\n" + "\n".join(failed_downloads)
                final_message += "\n\n注意: 如果出现合并错误或处理失败，请确保FFmpeg已正确安装并在系统PATH中，或在代码中正确设置了ffmpeg_directory_override。"
                final_message += "\n详细错误信息可能已打印到程序启动的控制台/终端窗口。"
                self._update_gui_safe(self.result_text.insert, tk.END, "\n--- 下载失败详情 ---\n" + "\n".join(failed_downloads) + "\n")

            self._update_gui_safe(messagebox.showinfo, "下载完成", final_message)
            self._update_gui_safe(self.status_var.set, f"下载完成. 成功: {download_count}, 失败: {len(failed_downloads)}")
        except Exception as e: 
            self._update_gui_safe(messagebox.showerror, "下载线程错误", f"下载过程中发生严重错误: {e}")
            self._update_gui_safe(self.status_var.set, f"下载线程错误: {e}")
        finally: 
            self._update_gui_safe(self.download_button.config, state=tk.NORMAL)


    def _yt_dlp_progress_hook(self, d, current_idx_hook, total_videos_hook):
        title_prefix_info = "当前文件" 
        author_info_str = "" 
        if hasattr(self, 'video_links') and self.video_links and 0 <= current_idx_hook < len(self.video_links):
             video_item = self.video_links[current_idx_hook]
             title_prefix_info = video_item.get('display_title', '未知标题')[:30] + "..."
             author_info_str = f" (作者: {video_item.get('author', '')[:15]})"
        
        prefix = f"({current_idx_hook+1}/{total_videos_hook}) {title_prefix_info}{author_info_str}"

        if d['status'] == 'downloading':
            p = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            self._update_gui_safe(self.status_var.set, f"{prefix}: {p} at {speed}, ETA {eta}")
        elif d['status'] == 'finished':
            self._update_gui_safe(self.status_var.set, f"{prefix}: 下载完成, 等待处理...")
        elif d['status'] == 'error': 
            self._update_gui_safe(self.status_var.set, f"{prefix}: 下载阶段报告错误.")

    def _yt_dlp_postprocessor_hook(self, d, current_idx_hook, total_videos_hook):
        title_prefix_info = "当前文件" 
        author_info_str = "" 
        if hasattr(self, 'video_links') and self.video_links and 0 <= current_idx_hook < len(self.video_links):
             video_item = self.video_links[current_idx_hook]
             title_prefix_info = video_item.get('display_title', '未知标题')[:30] + "..."
             author_info_str = f" (作者: {video_item.get('author', '')[:15]})"

        prefix = f"({current_idx_hook+1}/{total_videos_hook}) {title_prefix_info}{author_info_str}"
        
        pp_name = d.get('postprocessor')
        status = d.get('status')

        if status == 'started' or status == 'processing':
            self._update_gui_safe(self.status_var.set, f"{prefix}: 后处理 ({pp_name})...")
        elif status == 'finished':
            self._update_gui_safe(self.status_var.set, f"{prefix}: 后处理 ({pp_name}) 完成.")
        elif status == 'error': 
            self._update_gui_safe(self.status_var.set, f"{prefix}: 后处理 ({pp_name}) 错误.")


    def start_download_videos(self):
        if not self.video_links:
            messagebox.showinfo("提示", "列表中没有视频链接。请先获取链接。")
            return
        if yt_dlp is None: 
            messagebox.showerror("依赖缺失", "未找到 yt_dlp 模块。\n请先通过 pip 安装: pip install yt-dlp")
            return
        if not self.download_folder or not os.path.isdir(self.download_folder):
            messagebox.showwarning("选择目录", "请先选择一个有效的下载目录。")
            self.choose_folder()
            if not self.download_folder or not os.path.isdir(self.download_folder):
                return
        
        self.download_button.config(state=tk.DISABLED)
        self._update_gui_safe(self.status_var.set, "正在初始化下载...")
        thread = threading.Thread(target=self._download_videos_worker, daemon=True)
        thread.start()
        self._check_thread_status(thread, self.download_button)


    def copy_links(self):
        if pyperclip is None:
            self._update_gui_safe(messagebox.showerror, "依赖缺失", "未找到 pyperclip 模块。\n请安装: pip install pyperclip")
            self._update_gui_safe(self.status_var.set, "复制失败: pyperclip 未安装")
            return
        if not self.video_links:
            messagebox.showinfo("提示", "没有可复制的链接。")
            return
        try:
            links_text = "\n".join([v['url'] for v in self.video_links])
            pyperclip.copy(links_text)
            self.status_var.set(f"{len(self.video_links)} 条链接已复制到剪贴板")
        except Exception as e:
            self._update_gui_safe(messagebox.showerror, "复制错误", f"无法复制到剪贴板: {e}")
            self.status_var.set("复制到剪贴板失败")

    def clear_results(self):
        self.result_text.delete(1.0, tk.END)
        self.video_links = []
        self.status_var.set("结果已清除")

if __name__ == '__main__':
    root = tk.Tk()
    app = BilibiliCrawler(root)
    root.mainloop()
