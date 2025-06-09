import os
import tkinter as tk
from tkinter import messagebox, filedialog

def check_downloaded_files(download_folder):
    """检查下载文件夹中的视频数量"""
    if not download_folder or not os.path.isdir(download_folder):
        messagebox.showinfo("提示", "请先选择一个有效的下载目录。")
        download_folder = filedialog.askdirectory(title="选择下载目录")
        if not download_folder or not os.path.isdir(download_folder):
            return
    
    # 获取下载文件夹中的所有视频文件
    video_extensions = ['.mp4', '.mkv', '.webm', '.flv', '.avi', '.mov', '.wmv', '.ts', '.3gp']
    audio_extensions = ['.mp3', '.m4a', '.flac', '.wav', '.ogg', '.opus', '.aac', '.ac3', '.dts', '.amr', '.wma']
    all_extensions = video_extensions + audio_extensions
    
    # 计算文件数量
    file_count = 0
    for root, _, files in os.walk(download_folder):
        for file in files:
            if any(file.lower().endswith(ext) for ext in all_extensions):
                file_count += 1
    
    # 显示结果
    message = f"下载文件夹中共有 {file_count} 个媒体文件。"
    messagebox.showinfo("下载文件统计", message)
    return file_count

if __name__ == "__main__":
    # 简单的测试窗口
    root = tk.Tk()
    root.title("下载检查工具")
    root.geometry("300x100")
    
    def select_folder():
        folder = filedialog.askdirectory(title="选择下载目录")
        if folder:
            check_downloaded_files(folder)
    
    btn = tk.Button(root, text="选择文件夹并检查", command=select_folder)
    btn.pack(pady=20)
    
    root.mainloop() 