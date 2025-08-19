import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class SettingsWindow:
    def __init__(self, parent, config, on_close_callback=None):
        self.parent = parent
        self.config = config
        self.on_close_callback = on_close_callback
        
        # ウィンドウ設定
        self.window = tk.Toplevel(parent)
        self.window.title("設定")
        self.window.geometry("600x550")  # サイズを拡大
        self.window.minsize(600, 550)    # 最小サイズを設定
        self.window.resizable(True, True)
        self.window.transient(parent)
        self.window.grab_set()
        
        # 変数の初期化
        self.oraja_path_var = tk.StringVar(value=self.config.oraja_path)
        self.player_path_var = tk.StringVar(value=self.config.player_path)
        self.websocket_host_var = tk.StringVar(value=self.config.websocket_host)
        self.websocket_port_var = tk.IntVar(value=self.config.websocket_port)
        self.websocket_password_var = tk.StringVar(value=self.config.websocket_password)
        self.enable_websocket_var = tk.BooleanVar(value=self.config.enable_websocket)
        self.enable_autotweet_var = tk.BooleanVar(value=self.config.enable_autotweet)
        self.autoload_offset_var = tk.IntVar(value=self.config.autoload_offset)
        self.enable_register_conditions_var = tk.BooleanVar(value=self.config.enable_register_conditions)
        
        self.setup_ui()
        self.update_websocket_state()
        
        # ウィンドウを中央に配置
        self.center_window()
        
        # ウィンドウ閉じる時のイベント
        self.window.protocol("WM_DELETE_WINDOW", self.on_cancel)
    
    def setup_ui(self):
        """UIセットアップ"""
        # メインフレーム
        main_frame = ttk.Frame(self.window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 自動ツイート機能on/off
        self.enable_autotweet_cb = ttk.Checkbutton(
            main_frame, 
            text="終了時に結果を自動でTweetする",
            variable=self.enable_autotweet_var,
        )
        self.enable_autotweet_cb.pack(anchor=tk.W, pady=(0, 10))
        
        # 起動時に自動で読み込む範囲の設定
        autoload_offset_frame = ttk.Frame(main_frame)
        autoload_offset_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(autoload_offset_frame, text="何時間前までのリザルトを自動で読み込むか:", width=45).pack(side=tk.LEFT)
        self.autoload_offset_entry = ttk.Entry(autoload_offset_frame, textvariable=self.autoload_offset_var, width=5)
        self.autoload_offset_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # フォルダ設定セクション
        folder_frame = ttk.LabelFrame(main_frame, text="監視設定", padding="10")
        folder_frame.pack(fill=tk.X, pady=(0, 15))
        
        # フォルダパス設定
        ttk.Label(folder_frame, text="beatorajaインストール先:").pack(anchor=tk.W)
        
        oraja_path_frame = ttk.Frame(folder_frame)
        oraja_path_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.oraja_path_entry = ttk.Entry(oraja_path_frame, textvariable=self.oraja_path_var, state="readonly")
        self.oraja_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(oraja_path_frame, text="変更", command=self.change_oraja_path).pack(side=tk.RIGHT)

        # フォルダパス設定
        ttk.Label(folder_frame, text="playerフォルダ:").pack(anchor=tk.W)
        
        player_path_frame = ttk.Frame(folder_frame)
        player_path_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.player_path_entry = ttk.Entry(player_path_frame, textvariable=self.player_path_var, state="readonly")
        self.player_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(player_path_frame, text="変更", command=self.change_player_path).pack(side=tk.RIGHT)
        
        # WebSocket設定セクション
        websocket_frame = ttk.LabelFrame(main_frame, text="WebSocket連携設定", padding="10")
        websocket_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 連携機能有効/無効
        self.enable_websocket_cb = ttk.Checkbutton(
            websocket_frame, 
            text="WebSocket連携機能を使用する",
            variable=self.enable_websocket_var,
            command=self.update_websocket_state
        )
        self.enable_websocket_cb.pack(anchor=tk.W, pady=(0, 10))
        
        # ホスト名設定
        host_frame = ttk.Frame(websocket_frame)
        host_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(host_frame, text="ホスト名:", width=12).pack(side=tk.LEFT)
        self.websocket_host_entry = ttk.Entry(host_frame, textvariable=self.websocket_host_var)
        self.websocket_host_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # ポート設定
        port_frame = ttk.Frame(websocket_frame)
        port_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(port_frame, text="ポート:", width=12).pack(side=tk.LEFT)
        self.websocket_port_entry = ttk.Entry(port_frame, textvariable=self.websocket_port_var, width=10)
        self.websocket_port_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # パスワード設定
        password_frame = ttk.Frame(websocket_frame)
        password_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(password_frame, text="パスワード:", width=12).pack(side=tk.LEFT)
        self.websocket_password_entry = ttk.Entry(password_frame, textvariable=self.websocket_password_var, show="*")
        self.websocket_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        ttk.Button(button_frame, text="キャンセル", command=self.on_cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="保存", command=self.on_save).pack(side=tk.RIGHT)
        
        # WebSocketエントリリストを保存（状態更新用）
        self.websocket_entries = [
            self.websocket_host_entry,
            self.websocket_port_entry, 
            self.websocket_password_entry
        ]
    
    def center_window(self):
        """ウィンドウを親ウィンドウの中央に配置（画面内に収まるように調整）"""
        self.window.update_idletasks()
        
        # 画面サイズを取得
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # 親ウィンドウの位置とサイズを取得
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # 自分のウィンドウサイズを取得
        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()
        
        # 親ウィンドウの中央に配置する座標を計算
        x = parent_x + (parent_width - window_width) // 2
        y = parent_y + (parent_height - window_height) // 2
        
        # 画面内に収まるように調整
        x = max(0, min(x, screen_width - window_width))
        y = max(0, min(y, screen_height - window_height))
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def change_oraja_path(self):
        """フォルダ選択ダイアログを開く"""
        oraja_path = filedialog.askdirectory(
            title="beatorajaのインストール先を選択してください",
            initialdir=self.oraja_path_var.get() or "/"
        )
        
        if oraja_path:
            self.oraja_path_var.set(oraja_path)
    
    def change_player_path(self):
        """フォルダ選択ダイアログを開く"""
        player_path = filedialog.askdirectory(
            title="playerフォルダを選択してください",
            initialdir=self.player_path_var.get() or "/"
        )
        
        if player_path:
            self.player_path_var.set(player_path)
    
    def update_websocket_state(self):
        """WebSocket設定欄の有効/無効を更新"""
        is_enabled = self.enable_websocket_var.get()
        
        state = tk.NORMAL if is_enabled else tk.DISABLED
        
        for entry in self.websocket_entries: # 設定が無効な場合に入力欄を無効化
            entry.config(state=state)
    
    def validate_settings(self):
        """設定値の妥当性をチェック"""
        # ポート番号の妥当性チェック
        try:
            port = self.websocket_port_var.get()
            if port < 1 or port > 65535:
                messagebox.showerror("入力エラー", "ポート番号は1-65535の範囲で入力してください。")
                return False
        except tk.TclError:
            messagebox.showerror("入力エラー", "ポート番号は数値で入力してください。")
            return False
        
        # ホスト名の基本チェック
        if self.enable_websocket_var.get():
            host = self.websocket_host_var.get().strip()
            if not host:
                messagebox.showerror("入力エラー", "WebSocket連携を使用する場合、ホスト名を入力してください。")
                return False
        
        return True
    
    def on_save(self):
        """設定を保存"""
        if not self.validate_settings():
            return
        
        try:
            # 設定を保存
            self.config.oraja_path = self.oraja_path_var.get()
            self.config.player_path = self.player_path_var.get()
            self.config.websocket_host = self.websocket_host_var.get().strip()
            self.config.websocket_port = self.websocket_port_var.get()
            self.config.websocket_password = self.websocket_password_var.get()
            self.config.enable_websocket = self.enable_websocket_var.get()
            self.config.enable_autotweet = self.enable_autotweet_var.get()
            self.config.autoload_offset = self.autoload_offset_var.get()
            self.config.enable_register_conditions = self.enable_register_conditions_var.get()
            
            # ファイルに保存
            self.config.save_config()
            
            messagebox.showinfo("保存完了", "設定を保存しました。")
            self.close_window()
            
        except Exception as e:
            messagebox.showerror("保存エラー", f"設定の保存に失敗しました。\n{str(e)}")
    
    def on_cancel(self):
        """キャンセル処理"""
        self.close_window()
    
    def close_window(self):
        """ウィンドウを閉じる"""
        if self.on_close_callback:
            self.on_close_callback()
        
        self.window.grab_release()
        self.window.destroy()