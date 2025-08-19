import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
from datetime import datetime, timedelta
from config import Config
from settings import SettingsWindow
from obssocket import OBSWebSocketManager
import logging, logging.handlers
from PIL import ImageDraw, Image
import imagehash
from enum import Enum

os.makedirs('log', exist_ok=True)
os.makedirs('out', exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdl = logging.handlers.RotatingFileHandler(
    f'log/{os.path.basename(__file__).split(".")[0]}.log',
    encoding='utf-8',
    maxBytes=1024*1024*2,
    backupCount=1,
)
hdl.setLevel(logging.DEBUG)
hdl_formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)5d %(funcName)s() [%(levelname)s] %(message)s')
hdl.setFormatter(hdl_formatter)
logger.addHandler(hdl)
lamp = ['NO PLAY', 'FAILED', 'FAILED', 'A-CLEAR', 'E-CLEAR', 'CLEAR', 'H-CLEAR', 'EXH-CLEAR', 'F-COMBO', 'PERFECT']

class gui_mode(Enum):
    init = 0
    main = 1
    settings = 2
    obs_control = 3
    register_scene = 4

class detect_mode(Enum):
    init = 0
    select = 1
    play = 2
    result = 3

try:
    with open('version.txt', 'r') as f:
        SWVER = f.readline().strip()
except Exception:
    SWVER = "v0.0.0"

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.config = Config()
        self.start_time = datetime.now()
        self.file_exists = False
        self.monitoring_thread = None
        self.is_running = True
        
        # OBS WebSocket管理クラス初期化
        self.obs_manager = OBSWebSocketManager(status_callback=self.on_obs_status_changed)
        self.obs_manager.set_config(self.config)
        
        self.setup_ui()
        self.start_monitoring()
        self.update_display()
        
        # WebSocket自動接続開始
        if self.config.enable_websocket:
            self.obs_manager.start_auto_reconnect()
    
    def setup_ui(self):
        """UIの初期設定"""
        self.root.title(f"oraja_helper {SWVER}")
        self.root.geometry("500x300")
        
        # メニューバー
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 設定メニュー
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="設定", menu=settings_menu)
        settings_menu.add_command(label="設定を開く", command=self.open_settings)
        
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 経過時間表示
        ttk.Label(main_frame, text="起動からの経過時間:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.elapsed_time_var = tk.StringVar(value="00:00:00")
        ttk.Label(main_frame, textvariable=self.elapsed_time_var, font=("Arial", 12, "bold")).grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 監視対象フォルダ表示
        ttk.Label(main_frame, text="監視対象フォルダ:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.oraja_path_var = tk.StringVar()
        ttk.Label(main_frame, textvariable=self.oraja_path_var, wraplength=300).grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # ファイル存在状況表示
        ttk.Label(main_frame, text="ファイル存在状況:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.file_status_var = tk.StringVar(value="確認中...")
        self.file_status_label = ttk.Label(main_frame, textvariable=self.file_status_var, font=("Arial", 12, "bold"))
        self.file_status_label.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 最終確認時刻表示
        ttk.Label(main_frame, text="最終確認時刻:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.last_check_var = tk.StringVar(value="未確認")
        ttk.Label(main_frame, textvariable=self.last_check_var).grid(row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # OBS WebSocket連携状況表示
        ttk.Label(main_frame, text="OBS WebSocket:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.obs_status_var = tk.StringVar()
        self.obs_status_label = ttk.Label(main_frame, textvariable=self.obs_status_var, wraplength=300)
        self.obs_status_label.grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # ステータスバー
        status_frame = ttk.Frame(self.root)
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.status_var = tk.StringVar(value="準備完了")
        ttk.Label(status_frame, textvariable=self.status_var, relief=tk.SUNKEN).pack(fill=tk.X, padx=5, pady=2)
        
        # グリッドの重み設定
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        self.update_config_display()
    
    def update_config_display(self):
        """設定情報の表示を更新"""
        self.oraja_path_var.set(self.config.oraja_path or "未設定")
        
        # OBS WebSocket設定の更新
        self.obs_manager.set_config(self.config)
        
        # 現在のOBSステータスを取得して表示
        status_message, is_connected = self.obs_manager.get_status()
        self.obs_status_var.set(status_message)
        
        # 接続状態に応じて色を変更
        if is_connected:
            self.obs_status_label.config(foreground="green")
        elif "無効" in status_message or "インストール" in status_message:
            self.obs_status_label.config(foreground="gray")
        else:
            self.obs_status_label.config(foreground="red")
        
        # WebSocket連携が有効になった場合は自動接続を開始
        if self.config.enable_websocket and not self.obs_manager.should_reconnect:
            self.obs_manager.start_auto_reconnect()
        elif not self.config.enable_websocket:
            self.obs_manager.stop_auto_reconnect()
            self.obs_manager.disconnect()
    
    def on_obs_status_changed(self, status_message: str, is_connected: bool):
        """OBS WebSocket接続状態変更時のコールバック"""
        def update_ui():
            self.obs_status_var.set(status_message)
            
            # 接続状態に応じて色を変更
            if is_connected:
                self.obs_status_label.config(foreground="green")
                self.status_var.set("OBS WebSocket接続完了")
            else:
                # 詳細な状態による色分け
                if "無効" in status_message or "インストール" in status_message:
                    self.obs_status_label.config(foreground="gray")
                    self.status_var.set("OBS WebSocket機能無効")
                elif "接続中" in status_message:
                    self.obs_status_label.config(foreground="orange")
                    self.status_var.set("OBS WebSocket接続試行中...")
                elif "タイムアウト" in status_message:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket接続タイムアウト")
                elif "接続拒否" in status_message:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket接続拒否 (OBS未起動?)")
                elif "失われました" in status_message:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket接続が失われました")
                elif "エラー" in status_message:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket接続エラー")
                else:
                    self.obs_status_label.config(foreground="red")
                    self.status_var.set("OBS WebSocket切断")
        
        # メインスレッドでUI更新を実行
        self.root.after(0, update_ui)

    def start_monitoring(self):
        """ファイル監視スレッドを開始"""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(target=self.file_monitoring_worker, daemon=True)
            self.monitoring_thread.start()
    
    def file_monitoring_worker(self):
        """ファイル監視を行うワーカースレッド（スケルトンコード）"""
        while self.is_running:
            try:
                # 実際のファイル監視処理をここに実装
                target_file = self.config.get_target_file_path()
                
                if target_file:
                    self.file_exists = os.path.exists(target_file)
                    
                    # WebSocket連携処理もここに実装予定
                    if self.config.enable_websocket:
                        # TODO: WebSocket送信処理
                        pass
                else:
                    self.file_exists = False
                
                # メインスレッドでUI更新をスケジュール
                self.root.after(0, self.update_file_status)
                
            except Exception as e:
                print(f"監視エラー: {e}")
                self.root.after(0, lambda: self.status_var.set(f"監視エラー: {e}"))
            
            # 5秒間隔で監視
            time.sleep(5)
    
    def update_file_status(self):
        """ファイル状況の表示を更新"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_check_var.set(current_time)
        
        if self.file_exists:
            self.file_status_var.set("存在します")
            self.file_status_label.config(foreground="green")
            self.status_var.set("ファイルが見つかりました")
        else:
            self.file_status_var.set("存在しません")
            self.file_status_label.config(foreground="red")
            self.status_var.set("ファイルが見つかりません")
    
    def update_display(self):
        """表示の定期更新"""
        # 経過時間の更新
        elapsed = datetime.now() - self.start_time
        hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed_time_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # 1秒後に再実行
        self.root.after(1000, self.update_display)
    
    def open_settings(self):
        """設定ダイアログを開く"""
        def on_settings_close():
            # 設定が更新されたら表示を更新
            self.update_config_display()
        
        settings_window = SettingsWindow(self.root, self.config, on_settings_close)
    
    def on_closing(self):
        """アプリケーション終了時の処理"""
        self.is_running = False
        
        # OBS WebSocket接続を停止
        if hasattr(self, 'obs_manager'):
            self.obs_manager.stop_auto_reconnect()
            self.obs_manager.disconnect()
        
        # ファイル監視スレッドを停止
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=1)
            
        self.root.destroy()
    
    def run(self):
        """アプリケーションを実行"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

if __name__ == "__main__":
    app = MainWindow()
    app.run()