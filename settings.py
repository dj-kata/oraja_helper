import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclass import DiffTable, DataBaseAccessor
from config import Config
# from tooltip import ToolTip

class SettingsWindow:
    def __init__(self, parent, config, on_close_callback=None):
        self.parent = parent
        self.config = config
        self.on_close_callback = on_close_callback
        
        # ウィンドウ設定
        self.window = tk.Toplevel(parent)
        self.window.title("設定")
        self.window.geometry("600x700")  # 高さを少し増やす
        self.window.minsize(600, 600)    # 最小サイズも調整
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
        self.enable_judge_var = tk.BooleanVar(value=self.config.enable_judge)
        self.enable_folder_updates_var = tk.BooleanVar(value=self.config.enable_folder_updates)
        self.autoload_offset_var = tk.IntVar(value=self.config.autoload_offset)
        self.enable_register_conditions_var = tk.BooleanVar(value=self.config.enable_register_conditions)
        self.nglist_vars = {}
        self.nglist_checkbuttons = {}
        
        # 難易度表関連の初期化
        self.difftable = None
        self.nglist_frame = None
        self.canvas = None
        
        self.setup_ui()
        self.update_websocket_state()
        
        # ウィンドウを中央に配置
        self.center_window()
        
        # ウィンドウ閉じる時のイベント
        self.window.protocol("WM_DELETE_WINDOW", self.on_save)
    
    def setup_ui(self):
        """UIセットアップ"""
        # スクロール可能なメインフレームを作成
        self.setup_scrollable_frame()
        
        # 起動時に自動で読み込む範囲の設定
        autoload_offset_frame = ttk.Frame(self.scrollable_frame)
        autoload_offset_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(autoload_offset_frame, text="何時間前までのリザルトを自動で読み込むか:", width=45).pack(side=tk.LEFT)
        self.autoload_offset_entry = ttk.Entry(autoload_offset_frame, textvariable=self.autoload_offset_var, width=5)
        self.autoload_offset_entry.pack(side=tk.LEFT, padx=(5, 0))

        self.button_load_oraja_log = ttk.Button(autoload_offset_frame, text="過去ログ取得", command=self.load_oraja_log).pack(side=tk.RIGHT)
        # ToolTip(self.button_load_oraja_log, 'beatorajaのdbからプレーログを取得して本ツールのログとして保存します。\n連奏した曲は取得漏れとなるので注意。')

        # ツイート設定セクション
        tweet_frame = ttk.LabelFrame(self.scrollable_frame, text="ツイート設定", padding="10")
        tweet_frame.pack(fill=tk.X, pady=(0, 15))
        # 自動ツイート機能on/off
        self.enable_autotweet_cb = ttk.Checkbutton(
            tweet_frame, 
            text="終了時に結果を自動でTweetする",
            variable=self.enable_autotweet_var,
        )
        self.enable_autotweet_cb.pack(anchor=tk.W, pady=(0, 10))
        # 判定内訳のon/off
        self.enable_judge_cb = ttk.Checkbutton(
            tweet_frame, 
            text="判定内訳を含む(PG,GRなど)",
            variable=self.enable_judge_var,
        )
        self.enable_judge_cb.pack(anchor=tk.W, pady=(0, 10))
        # フォルダ更新状況のon/off
        self.enable_folder_updates_cb = ttk.Checkbutton(
            tweet_frame, 
            text="フォルダごとのランプ更新数を出力する",
            variable=self.enable_folder_updates_var,
        )
        self.enable_folder_updates_cb.pack(anchor=tk.W, pady=(0, 10))
        
        # フォルダ設定セクション
        folder_frame = ttk.LabelFrame(self.scrollable_frame, text="監視設定", padding="10")
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
        websocket_frame = ttk.LabelFrame(self.scrollable_frame, text="WebSocket連携設定", padding="10")
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
        
        # WebSocketエントリリストを保存（状態更新用）
        self.websocket_entries = [
            self.websocket_host_entry,
            self.websocket_port_entry, 
            self.websocket_password_entry
        ]
    
        # 難易度表セクションを初期化
        self.setup_ui_nglist()
        
        # ボタンフレーム（固定位置）
        self.setup_button_frame()
    
    def setup_scrollable_frame(self):
        """スクロール可能なメインフレームを作成"""
        # ボタンフレーム用のスペースを確保
        self.main_container = ttk.Frame(self.window)
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # スクロール可能エリア
        self.scroll_canvas = tk.Canvas(self.main_container)
        self.scrollbar = ttk.Scrollbar(self.main_container, orient="vertical", command=self.scroll_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.scroll_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        )
        
        self.scroll_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.scroll_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # マウスホイールでスクロール
        def _on_mousewheel(event):
            self.scroll_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        self.scroll_canvas.bind("<MouseWheel>", _on_mousewheel)
        
        # ウィンドウサイズ変更時の対応
        def configure_scroll_region(event):
            self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
        
        self.scrollable_frame.bind("<Configure>", configure_scroll_region)
        
        # スクロール可能エリアをパック（ボタン分のスペースを確保）
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
    
    def setup_button_frame(self):
        """固定位置のボタンフレームを作成"""
        # ボタンフレーム（ウィンドウの下部に固定）
        self.button_container = ttk.Frame(self.window)
        self.button_container.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(5, 15))
        
        button_frame = ttk.Frame(self.button_container)
        button_frame.pack(fill=tk.X)
        
    def setup_ui_nglist(self):
        """難易度表UIセクションの初期化"""
        # 既存のUIが存在する場合は削除
        if hasattr(self, 'nglist_section') and self.nglist_section:
            self.nglist_section.destroy()
        
        # 難易度表セクションフレーム（高さを制限）
        self.nglist_section = ttk.LabelFrame(self.scrollable_frame, text="難易度表選択", padding="10")
        self.nglist_section.pack(fill=tk.X, pady=(0, 15))  # expand=Trueを削除
        
        # 現在のチェック状態を保存
        current_states = {}
        if hasattr(self, 'nglist_vars'):
            current_states = {name: var.get() for name, var in self.nglist_vars.items()}
        
        # 変数をリセット
        self.nglist_vars = {}
        self.nglist_checkbuttons = {}
        
        # 難易度表データを読み込み
        self.load_difftable_data()
        
        if not self.difftable or not hasattr(self.difftable, 'table_names'):
            # 難易度表データが読み込めない場合
            ttk.Label(self.nglist_section, 
                     text="難易度表データを読み込めません。\nbeatorajaのインストール先が正しく設定されているか確認してください。",
                     foreground="red").pack(anchor=tk.W, pady=10)
            return
        
        # 難易度表数に応じて高さを動的に決定（最大300px）
        table_count = len(self.difftable.table_names)
        dynamic_height = min(max(150, table_count * 25), 300)
        
        # キャンバスとスクロールバー
        self.canvas = tk.Canvas(self.nglist_section, height=dynamic_height)
        nglist_scrollbar = ttk.Scrollbar(self.nglist_section, orient="vertical", command=self.canvas.yview)
        self.nglist_frame = ttk.Frame(self.canvas)
        
        ttk.Label(self.nglist_frame, text="ログに難易度を表示する難易度表", width=30).pack(fill=tk.X, pady=2)
        
        self.nglist_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.nglist_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=nglist_scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        nglist_scrollbar.pack(side="right", fill="y")

        # 難易度表のチェックボックスを作成
        for i, item in enumerate(self.difftable.table_names):
            # BooleanVar を作成（チェック状態を管理）
            var = tk.BooleanVar()
            self.nglist_vars[item] = var
            
            # チェックボックスを作成
            checkbox = ttk.Checkbutton(
                self.nglist_frame,
                text=item,
                variable=var,
            )
            checkbox.pack(anchor="w", padx=10, pady=2)
            self.nglist_checkbuttons[item] = checkbox

            # チェック状態を設定（優先順位：保存された状態 > 設定ファイル > デフォルト）
            if item in current_states:
                # 以前のUIセッションの状態を復元
                var.set(current_states[item])
            elif item in self.config.difftable_nglist: 
                # 設定ファイルの状態を反映
                var.set(False)
            else:
                # デフォルト（有効）
                var.set(True)
        
        # スクロール領域を更新
        self.scrollable_frame.update_idletasks()
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
    
    def load_difftable_data(self):
        """難易度表データを読み込み"""
        try:
            # 現在のoraja_pathを使用して一時的なConfigを作成
            temp_config = type('TempConfig', (), {})()
            temp_config.oraja_path = self.oraja_path_var.get()
            temp_config.difftable_nglist = self.config.difftable_nglist
            
            # DiffTableを新しいパスで初期化
            if temp_config.oraja_path:
                self.difftable = DiffTable()
                self.difftable.set_config(temp_config)
                print(f"難易度表を読み込みました: {len(self.difftable.table_names)}個")
            else:
                self.difftable = None
                print("oraja_pathが設定されていません")
                
        except Exception as e:
            print(f"難易度表読み込みエラー: {e}")
            self.difftable = None
    
    def refresh_difftable_ui(self):
        """難易度表UIを再構築"""
        print("難易度表UIを更新中...")
        try:
            # UIを再構築
            self.setup_ui_nglist()
            # ウィンドウを更新
            self.window.update_idletasks()
            print("難易度表UI更新完了")
        except Exception as e:
            print(f"難易度表UI更新エラー: {e}")
            messagebox.showerror("エラー", f"難易度表UIの更新に失敗しました。\n{str(e)}")

    def center_window(self):
        """ウィンドウを親ウィンドウの中央に配置（画面内に収まるように調整）"""
        self.window.update_idletasks()
        
        # 親ウィンドウの位置とサイズを取得
        parent_x = self.parent.winfo_x()
        
        # 自分のウィンドウサイズを取得
        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()
        
        # 親ウィンドウの中央に配置する座標を計算
        x = parent_x
        y = 0
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def change_oraja_path(self):
        """フォルダ選択ダイアログを開く"""
        oraja_path = filedialog.askdirectory(
            title="beatorajaのインストール先を選択してください",
            initialdir=self.oraja_path_var.get() or "/"
        )
        
        if oraja_path:
            print(f"oraja_pathを変更: {self.oraja_path_var.get()} -> {oraja_path}")
            self.oraja_path_var.set(oraja_path)
            
            # 難易度表UIを即座に更新
            self.window.after(100, self.refresh_difftable_ui)  # 少し遅延させて確実に更新
    
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

    def load_oraja_log(self):
        # 現在のUI状態でconfigを更新してからDataBaseAccessorを作成
        temp_config = Config()
        temp_config.oraja_path = self.oraja_path_var.get()
        temp_config.player_path = self.player_path_var.get()
        temp_config.autoload_offset = self.autoload_offset_var.get()

        acc = DataBaseAccessor()
        acc.set_config(temp_config)
        acc.read_old_results()
        acc.manage_results.save()
    
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
            self.config.enable_judge = self.enable_judge_var.get()
            self.config.enable_folder_updates = self.enable_folder_updates_var.get()
            self.config.autoload_offset = self.autoload_offset_var.get()
            self.config.enable_register_conditions = self.enable_register_conditions_var.get()

            # 難易度表設定を保存
            self.config.difftable_nglist = []
            if self.difftable and hasattr(self.difftable, 'table_names'):
                for item in self.difftable.table_names:
                    if item in self.nglist_vars and not self.nglist_vars[item].get():
                        self.config.difftable_nglist.append(item)
            
            # ファイルに保存
            self.config.save_config()
            
            # messagebox.showinfo("保存完了", "設定を保存しました。")
            self.close_window()
            
        except Exception as e:
            messagebox.showerror("保存エラー", f"設定の保存に失敗しました。\n{str(e)}")
    
    def close_window(self):
        """ウィンドウを閉じる"""
        if self.on_close_callback:
            self.on_close_callback()
        
        self.window.grab_release()
        self.window.destroy()