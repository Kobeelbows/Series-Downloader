import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import requests
import re
import json
import os
import threading
import subprocess
import sys # Moved import to top for robust path handling, e.g. when frozen

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
        self.root.title("Bili-Series-Downloader (Modern UI)")
        self.root.geometry("850x750") 
        self.root.resizable(True, True)
        self.root.configure(bg="#ECEFF1") 

        self.ffmpeg_directory_override = r"C:\ProgramData\chocolatey\bin"

        self.style = ttk.Style()
        self.style.theme_use('clam') 

        self.bg_color = "#ECEFF1" 
        self.primary_color = "#03A9F4" 
        self.primary_dark_color = "#0288D1" 
        self.text_color = "#263238" 
        self.entry_bg_color = "#CFD8DC" 
        self.button_text_color = "#FFFFFF"

        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("TLabel", background=self.bg_color, foreground=self.text_color, padding=6, font=('Helvetica', 10))
        self.style.configure("TButton", padding=8, relief="flat", font=('Helvetica', 10, 'bold'), foreground=self.button_text_color, background=self.primary_color)
        self.style.map("TButton",
                       background=[('active', self.primary_dark_color), ('disabled', '#B0BEC5')],
                       foreground=[('disabled', self.text_color)])
        self.style.configure("TEntry", fieldbackground=self.entry_bg_color, foreground=self.text_color, padding=6, font=('Helvetica', 10))
        self.style.configure("TCombobox", fieldbackground=self.entry_bg_color, foreground=self.text_color, padding=6, font=('Helvetica', 10))
        self.style.map("TCombobox",
            fieldbackground=[('readonly', self.entry_bg_color)],
            selectbackground=[('readonly', self.entry_bg_color)],
            selectforeground=[('readonly', self.text_color)])

        self.style.configure("TCheckbutton", background=self.bg_color, foreground=self.text_color, font=('Helvetica', 10), padding=3)
        self.style.map("TCheckbutton",
            indicatorcolor=[('selected', self.primary_color), ('!selected', self.text_color)],
            background=[('active', '#CFD8DC')]) 

        self.main_frame = ttk.Frame(root, padding="15 15 15 15")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.main_frame.columnconfigure(0, weight=1) 

        input_frame = ttk.Frame(self.main_frame)
        input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="B站视频/合集链接:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.url_entry = ttk.Entry(input_frame, width=60)
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=5)
        self.crawl_button = ttk.Button(input_frame, text="获取链接", command=self.start_crawl_videos)
        self.crawl_button.grid(row=0, column=2, sticky="e", padx=5)

        result_outer_frame = ttk.Frame(self.main_frame)
        result_outer_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        result_outer_frame.rowconfigure(1, weight=1) 
        result_outer_frame.columnconfigure(0, weight=1) 

        self.main_frame.rowconfigure(1, weight=1) 

        select_all_frame = ttk.Frame(result_outer_frame)
        select_all_frame.grid(row=0, column=0, sticky="ew", pady=(0,5))
        
        self.toggle_all_button = ttk.Button(select_all_frame, text="全选/取消全选", command=self.toggle_all_videos_selection)
        self.toggle_all_button.pack(side=tk.LEFT, padx=5)
        self.toggle_all_button.config(state=tk.DISABLED)

        self.video_list_canvas = tk.Canvas(result_outer_frame, borderwidth=0, background=self.bg_color, highlightthickness=0)
        self.video_list_scrollbar = ttk.Scrollbar(result_outer_frame, orient="vertical", command=self.video_list_canvas.yview)
        self.video_list_canvas.configure(yscrollcommand=self.video_list_scrollbar.set)

        self.video_list_canvas.grid(row=1, column=0, sticky="nsew")
        self.video_list_scrollbar.grid(row=1, column=1, sticky="ns")

        self.scrollable_frame = ttk.Frame(self.video_list_canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.video_list_canvas.configure(
                scrollregion=self.video_list_canvas.bbox("all")
            )
        )
        self.video_list_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.video_list_canvas.bind_all("<MouseWheel>", self._on_mousewheel) 
        self.video_list_canvas.bind_all("<Button-4>", self._on_mousewheel) 
        self.video_list_canvas.bind_all("<Button-5>", self._on_mousewheel) 

        action_frame_container = ttk.Frame(self.main_frame)
        action_frame_container.grid(row=2, column=0, sticky="ew", pady=(10, 5))
        action_frame_container.columnconfigure(0, weight=1) 

        action_frame_row1 = ttk.Frame(action_frame_container)
        action_frame_row1.pack(fill=tk.X, pady=(0,5))

        self.copy_button = ttk.Button(action_frame_row1, text="复制选中链接", command=self.copy_selected_links)
        self.copy_button.pack(side=tk.LEFT, padx=5)
        self.clear_button = ttk.Button(action_frame_row1, text="清除列表", command=self.clear_results)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        self.folder_button = ttk.Button(action_frame_row1, text="选择下载目录", command=self.choose_folder)
        self.folder_button.pack(side=tk.LEFT, padx=5)
        
        self.retry_button = ttk.Button(action_frame_row1, text="重试失败任务", command=self.retry_failed_downloads)
        self.retry_button.pack(side=tk.LEFT, padx=5)
        self.retry_button.config(state=tk.DISABLED)

        self.check_duplicates_button = ttk.Button(action_frame_row1, text="检查重复文件", command=self.check_duplicate_files)
        self.check_duplicates_button.pack(side=tk.LEFT, padx=5)

        self.check_count_button = ttk.Button(action_frame_row1, text="检查文件数量", command=self.check_file_count)
        self.check_count_button.pack(side=tk.LEFT, padx=5)

        action_frame_row2 = ttk.Frame(action_frame_container)
        action_frame_row2.pack(fill=tk.X, pady=(5,0))

        self.download_button = ttk.Button(action_frame_row2, text="下载选中视频", command=self.start_download_videos)
        self.download_button.pack(side=tk.LEFT, padx=5)

        self.download_mode_label = ttk.Label(action_frame_row2, text="下载模式:")
        self.download_mode_label.pack(side=tk.LEFT, padx=(10, 2))
        self.download_mode_var = tk.StringVar()
        self.download_mode_options = {
            "合并音视频": "merge",
            "仅音频 ": "audio_only",
            "仅视频 (无声)": "video_only"
        }
        self.download_mode_combo = ttk.Combobox(
            action_frame_row2,
            textvariable=self.download_mode_var,
            values=list(self.download_mode_options.keys()),
            state="readonly",
            width=28,
            font=('Helvetica', 10)
        )
        self.download_mode_combo.pack(side=tk.LEFT, padx=5)
        self.download_mode_combo.set(list(self.download_mode_options.keys())[0])

        log_frame = ttk.Frame(self.main_frame)
        log_frame.grid(row=3, column=0, sticky="ew", pady=(5,0))
        log_frame.columnconfigure(0, weight=1)
        
        ttk.Label(log_frame, text="日志:").pack(anchor=tk.W)
        self.log_text_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=5, relief=tk.SOLID, borderwidth=1, font=('Helvetica', 9), bg=self.entry_bg_color, fg=self.text_color)
        self.log_text_area.pack(fill=tk.X, expand=False, pady=(0,5)) 
        self.log_text_area.config(state=tk.DISABLED)

        self.status_var = tk.StringVar(value="准备就绪")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=8, font=('Helvetica', 9))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.video_links_data = [] 
        self.download_folder = os.getcwd()
        self.status_var.set(f"准备就绪. 下载目录: {self.download_folder}")
        self.current_video_idx = 0

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.bilibili.com'
        }

        self.failed_downloads = []

    def _on_mousewheel(self, event):
        if event.num == 4: 
             self.video_list_canvas.yview_scroll(-1, "units")
        elif event.num == 5: 
             self.video_list_canvas.yview_scroll(1, "units")
        else: 
            self.video_list_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _add_log_message(self, message):
        self.log_text_area.config(state=tk.NORMAL)
        self.log_text_area.insert(tk.END, message + "\n")
        self.log_text_area.see(tk.END) 
        self.log_text_area.config(state=tk.DISABLED)
        print(message) 

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
                        
                        # 获取BV号作为唯一标识符
                        bvid = v_data.get('bvid', '')
                        
                        # 在文件名中添加BV号作为唯一标识符
                        audio_filename_base = f"{audio_filename_base}_[{bvid}]"
                        video_filename_base = f"{video_filename_base}_[{bvid}]"
                        
                        videos.append({
                            'display_title': self.sanitize_filename(display_title),
                            'audio_filename_base': self.sanitize_filename(audio_filename_base),
                            'video_filename_base': self.sanitize_filename(video_filename_base),
                            'metadata_title_raw': metadata_title_raw,
                            'url': f"https://www.bilibili.com/video/{v_data.get('bvid','')}?p={v_data.get('page',{}).get('page',1)}" if v_data.get('bvid') else '',
                            'author': author_name,
                            'bvid': bvid,  # 保存BV号以便后续使用
                            'tk_var': tk.BooleanVar(value=True) 
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

    def _clear_video_list_display(self):
        # Unbind the configure event from canvas before destroying children
        self.video_list_canvas.unbind("<Configure>") 

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.video_links_data = []
        self.toggle_all_button.config(state=tk.DISABLED)

    def _on_canvas_configure_update_labels(self, event=None):
        """
        Called when the video_list_canvas is configured (e.g., resized).
        Updates the wraplength of all video item labels within the scrollable_frame.
        """
        canvas_width = self.video_list_canvas.winfo_width()
        scrollbar_width = 0
        if self.video_list_scrollbar.winfo_ismapped():
             scrollbar_width = self.video_list_scrollbar.winfo_width()
        
        # Estimate available width for label text within an item_frame.
        # Considers canvas width, scrollbar, checkbox, and some padding.
        # The value '45' is an empirical estimation for checkbox and its surrounding horizontal space.
        available_width_for_label = canvas_width - scrollbar_width - 55 # Adjusted offset
        
        if available_width_for_label <= 50: # Minimum sensible wraplength
            available_width_for_label = 100 # Fallback if calculated width is too small

        for item_f_widget in self.scrollable_frame.winfo_children():
            if isinstance(item_f_widget, ttk.Frame): # Each item is in a frame
                for widget in item_f_widget.winfo_children():
                    if isinstance(widget, ttk.Label):
                        widget.config(wraplength=available_width_for_label)
        
        self.scrollable_frame.update_idletasks()
        self.video_list_canvas.config(scrollregion=self.video_list_canvas.bbox("all"))

    def _display_crawl_results(self, crawled_videos_data):
        self._clear_video_list_display() 

        if not crawled_videos_data:
            self._add_log_message("未能获取到任何视频链接。")
            self.status_var.set("未找到视频或获取失败")
            return

        self.video_links_data = crawled_videos_data 

        for i, video_info in enumerate(self.video_links_data):
            item_frame = ttk.Frame(self.scrollable_frame, padding=(5,2))
            item_frame.pack(fill=tk.X, expand=True)

            cb = ttk.Checkbutton(item_frame, variable=video_info['tk_var'])
            cb.pack(side=tk.LEFT, padx=(0, 5))
            
            # Modified: URL removed from display text
            label_text = f"{i+1}. {video_info['display_title']} (作者: {video_info.get('author', '未知')})"
            
            lbl = ttk.Label(item_frame, text=label_text, anchor="w", justify=tk.LEFT)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            # Initial wraplength will be set by _on_canvas_configure_update_labels via root.after and on <Configure>

        # Bind configure event ONCE to the canvas to update all labels' wraplength
        self.video_list_canvas.bind("<Configure>", self._on_canvas_configure_update_labels)
        
        # Trigger initial wraplength update after GUI has had a chance to render and get dimensions
        self.root.after(100, lambda: self._on_canvas_configure_update_labels(None))


        self.status_var.set(f"成功获取 {len(self.video_links_data)} 条视频链接")
        self.toggle_all_button.config(state=tk.NORMAL)
        self.video_list_canvas.yview_moveto(0) 
        self.scrollable_frame.update_idletasks() 
        self.video_list_canvas.config(scrollregion=self.video_list_canvas.bbox("all"))


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
            
            crawled_videos_result = []

            if season_id:
                self._update_gui_safe(self.status_var.set, f"检测到合集 (ID: {season_id})，正在拉取列表...")
                crawled_videos_result = self.get_collection_videos(
                    season_id, 1000,
                    progress_callback=lambda msg: self._update_gui_safe(self.status_var.set, msg)
                )
                if not crawled_videos_result:
                    self._update_gui_safe(messagebox.showinfo, "提示", "未能从该合集获取到任何视频。")
                    self._update_gui_safe(self.status_var.set, "合集为空或获取失败")

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
                        self._update_gui_safe(self._add_log_message, f"错误: 重新获取页面数据失败: {e_fallback}")


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
                        
                        # 在文件名中添加BV号和P数作为唯一标识符
                        audio_filename_base = f"{audio_filename_base}_[{bvid}_p{page_num}]"
                        video_filename_base = f"{video_filename_base}_[{bvid}_p{page_num}]"
                        
                        crawled_videos_result.append({
                            'display_title': self.sanitize_filename(display_title),
                            'audio_filename_base': self.sanitize_filename(audio_filename_base),
                            'video_filename_base': self.sanitize_filename(video_filename_base),
                            'metadata_title_raw': metadata_title_raw,
                            'url': f"https://www.bilibili.com/video/{bvid}?p={page_num}",
                            'author': author_name,
                            'bvid': bvid,  # 保存BV号以便后续使用
                            'tk_var': tk.BooleanVar(value=True)
                        })
                else: 
                    preferred_song_title = self.extract_song_title(video_title_overall)
                    display_title = preferred_song_title if preferred_song_title else video_title_overall
                    audio_filename_base = preferred_song_title if preferred_song_title else video_title_overall
                    video_filename_base = video_title_overall
                    metadata_title_raw = preferred_song_title if preferred_song_title else video_title_overall
                    
                    # 在文件名中添加BV号作为唯一标识符
                    audio_filename_base = f"{audio_filename_base}_[{bvid}]"
                    video_filename_base = f"{video_filename_base}_[{bvid}]"
                    
                    crawled_videos_result.append({
                        'display_title': self.sanitize_filename(display_title),
                        'audio_filename_base': self.sanitize_filename(audio_filename_base),
                        'video_filename_base': self.sanitize_filename(video_filename_base),
                        'metadata_title_raw': metadata_title_raw,
                        'url': f"https://www.bilibili.com/video/{bvid}",
                        'author': author_name,
                        'bvid': bvid,  # 保存BV号以便后续使用
                        'tk_var': tk.BooleanVar(value=True)
                    })

                if not crawled_videos_result:
                     self._update_gui_safe(messagebox.showinfo, "提示", "未能解析该单个视频的信息。")
                     self._update_gui_safe(self.status_var.set, "单个视频解析失败")

            self._update_gui_safe(self._display_crawl_results, crawled_videos_result)

        except requests.exceptions.RequestException as e:
            self._update_gui_safe(messagebox.showerror, "网络错误", f"爬取过程中发生网络错误: {e}")
            self._update_gui_safe(self.status_var.set, f"网络错误: {e}")
            self._update_gui_safe(self._add_log_message, f"错误: 网络错误: {e}")
        except Exception as e:
            self._update_gui_safe(messagebox.showerror, "严重错误", f"爬取过程中发生未知错误: {e}")
            self._update_gui_safe(self.status_var.set, f"严重错误: {e}")
            self._update_gui_safe(self._add_log_message, f"错误: 严重错误: {e}")


    def start_crawl_videos(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("警告", "请输入B站视频或合集链接。")
            return
        self.crawl_button.config(state=tk.DISABLED)
        self._clear_video_list_display() 
        self._update_gui_safe(self.status_var.set, "正在处理请求...")
        self._update_gui_safe(self._add_log_message, "开始获取视频链接...") 
        thread = threading.Thread(target=self._crawl_videos_worker, args=(url,), daemon=True)
        thread.start()
        self._check_thread_status(thread, self.crawl_button)

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.download_folder)
        if folder:
            self.download_folder = folder
            self.status_var.set(f"下载目录已选择: {folder}")
            self._add_log_message(f"下载目录更新为: {folder}")


    def _download_videos_worker(self):
        try:
            ffmpeg_executable_to_run = None 
            ffmpeg_dir_for_yt_dlp = None  

            if getattr(sys, 'frozen', False): 
                script_dir = os.path.dirname(sys.executable)
            else: 
                try:
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                except NameError: 
                    script_dir = os.getcwd()


            local_ffmpeg_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
            local_ffmpeg_full_path = os.path.join(script_dir, local_ffmpeg_name)

            if os.path.isfile(local_ffmpeg_full_path):
                ffmpeg_executable_to_run = local_ffmpeg_full_path
                ffmpeg_dir_for_yt_dlp = script_dir 
                self._add_log_message(f"FFmpeg check: 优先使用脚本目录下的FFmpeg: {local_ffmpeg_full_path}")
            else:
                self._add_log_message(f"FFmpeg check: 脚本目录 ({script_dir}) 未找到FFmpeg。")
                if self.ffmpeg_directory_override and os.path.isdir(self.ffmpeg_directory_override):
                    override_ffmpeg_full_path = os.path.join(self.ffmpeg_directory_override, local_ffmpeg_name)
                    if os.path.isfile(override_ffmpeg_full_path):
                        ffmpeg_executable_to_run = override_ffmpeg_full_path
                        ffmpeg_dir_for_yt_dlp = self.ffmpeg_directory_override
                        self._add_log_message(f"FFmpeg check: 使用自定义覆盖目录中的FFmpeg: {override_ffmpeg_full_path}")
                    else:
                        self._add_log_message(f"FFmpeg check: 自定义覆盖目录 ({self.ffmpeg_directory_override}) 中未找到FFmpeg。")
                else:
                    self._add_log_message("FFmpeg check: 未设置或无效的自定义覆盖目录。")

                if not ffmpeg_executable_to_run:
                    ffmpeg_executable_to_run = 'ffmpeg' 
                    self._add_log_message("FFmpeg check: 尝试从系统PATH中查找FFmpeg。")
            
            ffmpeg_is_available = False
            try:
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                subprocess.run([ffmpeg_executable_to_run, '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, startupinfo=startupinfo)
                ffmpeg_is_available = True
                self._add_log_message(f"FFmpeg check:成功执行 '{ffmpeg_executable_to_run} -version'. FFmpeg可用。")
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                self._add_log_message(f"FFmpeg check: 执行 '{ffmpeg_executable_to_run} -version' 失败. Error: {e}")
                self._update_gui_safe(messagebox.showerror, "依赖缺失", f"未能找到或执行 FFmpeg。\n尝试路径: {ffmpeg_executable_to_run}\n请确保FFmpeg已正确安装并配置，或放置在脚本目录中，或在代码中正确设置 ffmpeg_directory_override。")
                self._update_gui_safe(self.status_var.set, "FFmpeg 未找到或无法执行，下载中止。")
            finally:
                if not ffmpeg_is_available:
                    self._update_gui_safe(self.download_button.config, state=tk.NORMAL)
                    return

            links_to_download_info = [vinfo for vinfo in self.video_links_data if vinfo['tk_var'].get()]

            if not links_to_download_info:
                self._update_gui_safe(messagebox.showinfo, "提示", "没有选中任何视频进行下载。")
                self._update_gui_safe(self.status_var.set, "没有选中视频。")
                self._update_gui_safe(self.download_button.config, state=tk.NORMAL)
                return

            total_videos_to_download = len(links_to_download_info)
            download_count = 0
            failed_downloads_log = []

            selected_mode_key = self.download_mode_var.get()
            actual_mode = self.download_mode_options.get(selected_mode_key, "merge")

            progress_hook = lambda d: self._yt_dlp_progress_hook(d, self.current_video_idx, total_videos_to_download)
            postprocessor_hook = lambda d: self._yt_dlp_postprocessor_hook(d, self.current_video_idx, total_videos_to_download)

            for idx, video_info in enumerate(links_to_download_info):
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

                if ffmpeg_dir_for_yt_dlp:
                    loop_ydl_opts['ffmpeg_location'] = ffmpeg_dir_for_yt_dlp
                    self._add_log_message(f"yt-dlp: 设置 ffmpeg_location (目录): {ffmpeg_dir_for_yt_dlp}")

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

                loop_ydl_opts['postprocessor_args'].setdefault('FFmpegMetadata', []) 
                loop_ydl_opts['postprocessor_args']['FFmpegMetadata'].extend([
                    '-metadata', f'artist={author_for_metadata}',
                    '-metadata', f'album_artist={author_for_metadata}',
                    '-metadata', f'title={metadata_title_tag}'
                ])
                
                if actual_mode == "video_only":
                    if any(pp.get('key') == 'FFmpegVideoConvertor' for pp in loop_ydl_opts['postprocessors']):
                        loop_ydl_opts['postprocessor_args'].setdefault('FFmpegVideoConvertor', [])
                        if '-an' not in loop_ydl_opts['postprocessor_args']['FFmpegVideoConvertor']:
                            loop_ydl_opts['postprocessor_args']['FFmpegVideoConvertor'].append('-an')


                self._update_gui_safe(self.status_var.set, f"准备下载 ({idx+1}/{total_videos_to_download}): {video_info['display_title'][:30]} (作者: {author_for_metadata[:15]})")
                self._update_gui_safe(self._add_log_message, f"开始下载: {video_info['display_title']}")

                try:
                    with yt_dlp.YoutubeDL(loop_ydl_opts) as ydl:
                        ydl.download([video_info['url']])
                    download_count +=1
                    self._update_gui_safe(self._add_log_message, f"成功下载: {video_info['display_title']}")
                except Exception as e:
                    error_message = str(e)
                    is_ytdlp_error = YTDLPDownloadError is not None and isinstance(e, YTDLPDownloadError)

                    if is_ytdlp_error:
                        self._add_log_message(f"yt-dlp DownloadError for '{video_info['display_title']}': {error_message}")
                        if "ffmpeg" in error_message.lower() or "ffprobe" in error_message.lower() or "merge" in error_message.lower():
                            error_message_display = f"合并/处理失败 (FFmpeg相关): {error_message}"
                        else:
                            error_message_display = f"yt-dlp 下载/处理错误: {error_message}"
                    else:
                        self._add_log_message(f"下载 '{video_info['display_title']}' 时发生一般错误: {error_message}")
                        error_message_display = f"下载时发生未知错误: {error_message}"

                    failed_downloads_log.append(f"{video_info['display_title']} (URL: {video_info['url']}) - Error: {error_message_display}")
                    self.failed_downloads.append(video_info)
                    self._update_gui_safe(self.status_var.set, f"失败 ({idx+1}/{total_videos_to_download}): {video_info['display_title'][:30]}...")
                    self._update_gui_safe(self._add_log_message, f"下载失败: {video_info['display_title']} - {error_message_display}")


            final_message = f"下载任务完成。成功下载 {download_count}/{total_videos_to_download} 个文件。"
            if failed_downloads_log:
                final_message += "\n\n以下文件下载失败:\n" + "\n".join(failed_downloads_log)
                final_message += "\n\n注意: 如果出现合并错误或处理失败，请确保FFmpeg已正确安装并配置，或放置在脚本目录中，或在代码中正确设置了ffmpeg_directory_override。"
                final_message += "\n详细错误信息已记录在日志区域和程序启动的控制台/终端窗口。"
                
                self._update_gui_safe(self._add_log_message, "\n--- 下载失败详情 ---")
                for fail_msg in failed_downloads_log:
                     self._update_gui_safe(self._add_log_message, fail_msg)
                self._update_gui_safe(self._add_log_message, "--- 下载失败详情结束 ---")


            self._update_gui_safe(messagebox.showinfo, "下载完成", final_message)
            self._update_gui_safe(self.status_var.set, f"下载完成. 成功: {download_count}, 失败: {len(failed_downloads_log)}")
            self._update_gui_safe(self._add_log_message, f"总任务完成. 成功: {download_count}, 失败: {len(failed_downloads_log)}")

            self._update_gui_safe(self.retry_button.config, state=tk.NORMAL if self.failed_downloads else tk.DISABLED)
        except Exception as e:
            self._update_gui_safe(messagebox.showerror, "下载线程错误", f"下载过程中发生严重错误: {e}")
            self._update_gui_safe(self.status_var.set, f"下载线程错误: {e}")
            self._update_gui_safe(self._add_log_message, f"严重错误 (下载线程): {e}")
        finally:
            self._update_gui_safe(self.download_button.config, state=tk.NORMAL)


    def _yt_dlp_progress_hook(self, d, current_idx_hook, total_videos_hook):
        links_currently_downloading = [vinfo for vinfo in self.video_links_data if vinfo['tk_var'].get()]
        title_prefix_info = "当前文件"
        author_info_str = ""
        if 0 <= current_idx_hook < len(links_currently_downloading):
            video_item = links_currently_downloading[current_idx_hook]
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
        links_currently_downloading = [vinfo for vinfo in self.video_links_data if vinfo['tk_var'].get()]
        title_prefix_info = "当前文件"
        author_info_str = ""
        if 0 <= current_idx_hook < len(links_currently_downloading):
            video_item = links_currently_downloading[current_idx_hook]
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
        selected_videos = [vinfo for vinfo in self.video_links_data if vinfo['tk_var'].get()]
        if not selected_videos:
            messagebox.showinfo("提示", "没有选中任何视频。请先选中视频再下载。")
            return
        if yt_dlp is None:
            messagebox.showerror("依赖缺失", "未找到 yt_dlp 模块。\n请先通过 pip 安装: pip install yt-dlp")
            self._add_log_message("错误: yt_dlp 模块未找到。")
            return
        if not self.download_folder or not os.path.isdir(self.download_folder):
            messagebox.showwarning("选择目录", "请先选择一个有效的下载目录。")
            self.choose_folder() 
            if not self.download_folder or not os.path.isdir(self.download_folder): 
                self._add_log_message("下载中止: 未选择有效的下载目录。")
                return

        self.download_button.config(state=tk.DISABLED)
        self._update_gui_safe(self.status_var.set, f"正在初始化下载 {len(selected_videos)} 个选定视频...")
        self._update_gui_safe(self._add_log_message, f"开始下载 {len(selected_videos)} 个选定视频...")
        thread = threading.Thread(target=self._download_videos_worker, daemon=True)
        thread.start()
        self._check_thread_status(thread, self.download_button)


    def copy_selected_links(self):
        if pyperclip is None:
            self._update_gui_safe(messagebox.showerror, "依赖缺失", "未找到 pyperclip 模块。\n请安装: pip install pyperclip")
            self._update_gui_safe(self.status_var.set, "复制失败: pyperclip 未安装")
            self._update_gui_safe(self._add_log_message, "错误: pyperclip 模块未安装，无法复制。")
            return

        selected_video_urls = [vinfo['url'] for vinfo in self.video_links_data if vinfo['tk_var'].get()]

        if not selected_video_urls:
            messagebox.showinfo("提示", "没有选中任何链接可供复制。")
            return
        try:
            links_text = "\n".join(selected_video_urls)
            pyperclip.copy(links_text)
            self.status_var.set(f"{len(selected_video_urls)} 条选中链接已复制到剪贴板")
            self._add_log_message(f"{len(selected_video_urls)} 条链接已复制。")
        except Exception as e:
            self._update_gui_safe(messagebox.showerror, "复制错误", f"无法复制到剪贴板: {e}")
            self.status_var.set("复制到剪贴板失败")
            self._update_gui_safe(self._add_log_message, f"错误: 复制到剪贴板失败: {e}")

    def clear_results(self):
        self._clear_video_list_display()
        self.status_var.set("结果已清除")
        self.log_text_area.config(state=tk.NORMAL)
        self.log_text_area.delete(1.0, tk.END) 
        self.log_text_area.config(state=tk.DISABLED)
        self._add_log_message("列表和日志已清除。")
        self.failed_downloads = []
        self.retry_button.config(state=tk.DISABLED)


    def toggle_all_videos_selection(self):
        if not self.video_links_data:
            return

        all_selected = all(vinfo['tk_var'].get() for vinfo in self.video_links_data)
        new_state = not all_selected 

        for vinfo in self.video_links_data:
            vinfo['tk_var'].set(new_state)

        if new_state:
            self._add_log_message("已全选所有视频。")
        else:
            self._add_log_message("已取消全选所有视频。")

    def retry_failed_downloads(self):
        """重新下载失败的视频"""
        if not self.failed_downloads:
            messagebox.showinfo("提示", "没有需要重试的失败任务。")
            return

        # 将失败的视频添加到下载列表
        for video_info in self.failed_downloads:
            video_info['tk_var'].set(True)  # 选中失败的视频
            
        # 取消选中其他视频
        for video_info in self.video_links_data:
            if video_info not in self.failed_downloads:
                video_info['tk_var'].set(False)

        # 开始下载
        self.start_download_videos()

    def check_duplicate_files(self):
        """检查下载目录中是否已存在勾选的视频/音频文件"""
        if not self.video_links_data:
            messagebox.showinfo("提示", "没有视频列表可供检查。")
            return
            
        if not self.download_folder or not os.path.isdir(self.download_folder):
            messagebox.showwarning("选择目录", "请先选择一个有效的下载目录。")
            self.choose_folder()
            if not self.download_folder or not os.path.isdir(self.download_folder):
                return
                
        # 获取下载目录中所有文件
        existing_files = os.listdir(self.download_folder)
        
        # 获取当前下载模式
        selected_mode_key = self.download_mode_var.get()
        actual_mode = self.download_mode_options.get(selected_mode_key, "merge")
        
        # 计数器
        unchecked_count = 0
        checked_count = 0
        
        # 检查每个勾选的视频
        for video_info in self.video_links_data:
            if not video_info['tk_var'].get():
                continue
                
            checked_count += 1
            
            # 根据下载模式选择文件名基础
            if actual_mode == "audio_only":
                filename_base = video_info.get('audio_filename_base', '')
                possible_extensions = ['.m4a', '.mp3', '.aac', '.wav', '.opus']
            elif actual_mode == "video_only":
                filename_base = video_info.get('video_filename_base', '')
                possible_extensions = ['.mp4', '.mkv', '.webm']
            else:  # merge mode
                filename_base = video_info.get('video_filename_base', '')
                possible_extensions = ['.mp4', '.mkv', '.webm']
            
            # 检查是否存在对应文件
            file_exists = False
            for ext in possible_extensions:
                potential_filename = f"{filename_base}{ext}"
                if potential_filename in existing_files:
                    file_exists = True
                    break
            
            # 如果文件已存在，取消勾选
            if file_exists:
                video_info['tk_var'].set(False)
                unchecked_count += 1
        
        # 显示结果
        if unchecked_count > 0:
            messagebox.showinfo("检查完成", f"检查了 {checked_count} 个勾选的视频，发现并取消勾选了 {unchecked_count} 个已存在的文件。")
            self._add_log_message(f"检查重复: 取消勾选了 {unchecked_count} 个已存在的文件。")
        else:
            messagebox.showinfo("检查完成", f"检查了 {checked_count} 个勾选的视频，没有发现重复文件。")
            self._add_log_message("检查重复: 没有发现重复文件。")

    def check_file_count(self):
        """检查下载文件数量与记录数量是否匹配"""
        if not self.download_folder or not os.path.isdir(self.download_folder):
            messagebox.showwarning("选择目录", "请先选择一个有效的下载目录。")
            self.choose_folder()
            if not self.download_folder or not os.path.isdir(self.download_folder):
                return
                
        # 获取下载目录中所有文件
        try:
            all_files = os.listdir(self.download_folder)
            # 过滤掉非媒体文件
            media_extensions = ['.mp4', '.mkv', '.webm', '.m4a', '.mp3', '.aac', '.wav', '.opus']
            media_files = [f for f in all_files if any(f.lower().endswith(ext) for ext in media_extensions)]
            
            # 检查是否有部分下载的临时文件
            temp_files = [f for f in all_files if f.endswith('.part') or f.endswith('.temp') or f.endswith('.tmp')]
            
            # 查找可能的重复文件（基于文件名前缀）
            filename_prefixes = {}
            potential_duplicates = []
            
            for file in media_files:
                # 去除扩展名的文件名
                name_without_ext = os.path.splitext(file)[0]
                if name_without_ext in filename_prefixes:
                    potential_duplicates.append((name_without_ext, filename_prefixes[name_without_ext], file))
                else:
                    filename_prefixes[name_without_ext] = file
            
            # 构建分析报告
            report = f"文件夹分析报告:\n\n"
            report += f"1. 文件夹路径: {self.download_folder}\n"
            report += f"2. 文件夹中的总文件数: {len(all_files)}\n"
            report += f"3. 媒体文件数量: {len(media_files)}\n"
            report += f"4. 临时/部分下载文件数: {len(temp_files)}\n"
            
            if potential_duplicates:
                report += f"\n5. 发现 {len(potential_duplicates)} 个可能的重复文件名:\n"
                for i, (prefix, file1, file2) in enumerate(potential_duplicates[:10], 1):
                    report += f"   {i}. {prefix} → {file1}, {file2}\n"
                if len(potential_duplicates) > 10:
                    report += f"   ...以及其他 {len(potential_duplicates) - 10} 个\n"
            else:
                report += "\n5. 未发现重复文件名\n"
                
            # 如果有视频列表数据，比较与实际文件的差异
            if self.video_links_data:
                total_videos = len(self.video_links_data)
                report += f"\n6. 当前视频列表中的视频总数: {total_videos}\n"
                
                # 检查文件名匹配情况
                matched_files = 0
                unmatched_videos = []
                
                # 创建一个字典，用于检测文件名冲突
                filename_to_videos = {}
                
                # 首先，收集所有视频可能的文件名
                for video_info in self.video_links_data:
                    video_filename_base = video_info.get('video_filename_base', '')
                    audio_filename_base = video_info.get('audio_filename_base', '')
                    
                    # 对于每个可能的扩展名，记录哪些视频会使用这个文件名
                    for ext in media_extensions:
                        if video_filename_base:
                            full_filename = f"{video_filename_base}{ext}"
                            if full_filename not in filename_to_videos:
                                filename_to_videos[full_filename] = []
                            filename_to_videos[full_filename].append(video_info)
                            
                        if audio_filename_base and audio_filename_base != video_filename_base:
                            full_filename = f"{audio_filename_base}{ext}"
                            if full_filename not in filename_to_videos:
                                filename_to_videos[full_filename] = []
                            filename_to_videos[full_filename].append(video_info)
                
                # 检查每个视频是否能匹配到文件
                for video_info in self.video_links_data:
                    video_filename_base = video_info.get('video_filename_base', '')
                    audio_filename_base = video_info.get('audio_filename_base', '')
                    
                    if any(f.startswith(video_filename_base) for f in media_files) or \
                       any(f.startswith(audio_filename_base) for f in media_files):
                        matched_files += 1
                    else:
                        unmatched_videos.append(video_info)
                
                # 查找文件名冲突（多个视频使用相同文件名）
                filename_conflicts = {}
                for filename, videos in filename_to_videos.items():
                    if len(videos) > 1 and any(filename == f or f.startswith(os.path.splitext(filename)[0] + '.') for f in media_files):
                        filename_conflicts[filename] = videos
                
                report += f"7. 能匹配到文件名的视频数: {matched_files}\n"
                report += f"8. 未匹配到文件的视频数: {total_videos - matched_files}\n"
                
                # 显示文件名冲突信息
                if filename_conflicts:
                    conflict_count = sum(len(videos) for videos in filename_conflicts.values()) - len(filename_conflicts)
                    report += f"\n⚠️ 发现 {len(filename_conflicts)} 个文件名被多个视频使用，共涉及 {conflict_count + len(filename_conflicts)} 个视频！\n"
                    report += "这意味着多个视频下载时会使用相同的文件名，导致后下载的覆盖先下载的。\n\n"
                    report += "文件名冲突详情（最多显示10个）：\n"
                    
                    for i, (filename, videos) in enumerate(list(filename_conflicts.items())[:10], 1):
                        report += f"{i}. 文件名: {filename} 被以下 {len(videos)} 个视频使用:\n"
                        for j, video in enumerate(videos[:3], 1):
                            report += f"   {j}. {video.get('display_title', '未知标题')} (URL: {video.get('url', '未知URL')})\n"
                        if len(videos) > 3:
                            report += f"   ...以及其他 {len(videos) - 3} 个视频\n"
                    
                    if len(filename_conflicts) > 10:
                        report += f"...以及其他 {len(filename_conflicts) - 10} 个冲突文件名\n"
                    
                    report += "\n解决方案：\n"
                    report += "1. 修改软件代码，在文件名中添加唯一标识符（如BV号）\n"
                    report += "2. 手动重命名已下载的文件，然后重新下载缺失的视频\n"
                    report += "3. 使用不同的下载目录，避免覆盖\n"
                
                # 检查文件数量差异
                if matched_files < total_videos:
                    report += f"\n⚠️ 警告：有 {total_videos - matched_files} 个视频在列表中但在文件夹中未找到对应文件！\n"
                    report += "可能原因：\n"
                    report += "- 文件命名冲突导致覆盖\n"
                    report += "- 下载失败但计数增加\n"
                    report += "- 文件被移动或删除\n"
                    
                    # 显示未匹配的视频信息
                    if unmatched_videos:
                        report += "\n未找到对应文件的视频列表（最多显示10个）：\n"
                        for i, video in enumerate(unmatched_videos[:10], 1):
                            report += f"{i}. {video.get('display_title', '未知标题')} (URL: {video.get('url', '未知URL')})\n"
                        if len(unmatched_videos) > 10:
                            report += f"...以及其他 {len(unmatched_videos) - 10} 个\n"
                
                # 检查文件夹中的文件是否都在视频列表中
                if matched_files < len(media_files):
                    extra_files = len(media_files) - matched_files
                    report += f"\n⚠️ 注意：文件夹中有 {extra_files} 个媒体文件不在当前视频列表中\n"
                    report += "可能原因：\n"
                    report += "- 这些文件是从其他来源下载的\n"
                    report += "- 文件名与视频标题不匹配\n"
                    report += "- 之前下载的视频不在当前列表中\n"
                    
                # 总结文件数量差异
                if total_videos != len(media_files):
                    report += f"\n📊 总结：列表中有 {total_videos} 个视频，但文件夹中有 {len(media_files)} 个媒体文件，差异为 {abs(total_videos - len(media_files))} 个\n"
                    
                    if total_videos > len(media_files):
                        missing_count = total_videos - len(media_files)
                        report += f"⚠️ 缺少 {missing_count} 个文件！"
                        
                        if filename_conflicts:
                            report += f"这很可能是由于发现的 {len(filename_conflicts)} 个文件名冲突导致的覆盖。\n"
                        else:
                            report += "这可能是由于文件命名冲突导致覆盖或下载失败。\n"
                    else:
                        extra_count = len(media_files) - total_videos
                        report += f"⚠️ 多出 {extra_count} 个文件！这可能是由于之前下载的文件或其他来源的文件。\n"
                        
            # 显示分析报告
            report_window = tk.Toplevel(self.root)
            report_window.title("文件数量分析报告")
            report_window.geometry("700x600")
            report_window.resizable(True, True)
            
            report_text = scrolledtext.ScrolledText(report_window, wrap=tk.WORD, font=('Helvetica', 10))
            report_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            report_text.insert(tk.END, report)
            report_text.config(state=tk.DISABLED)
            
            # 添加复制按钮
            def copy_report():
                report_window.clipboard_clear()
                report_window.clipboard_append(report)
                messagebox.showinfo("已复制", "报告已复制到剪贴板")
                
            copy_button = ttk.Button(report_window, text="复制报告", command=copy_report)
            copy_button.pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("分析错误", f"分析文件夹时出错: {e}")
            self._add_log_message(f"文件数量检查错误: {e}")

if __name__ == '__main__':
    root = tk.Tk()
    app = BilibiliCrawler(root)
    root.mainloop()
