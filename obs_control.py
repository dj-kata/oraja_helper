import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from typing import List, Dict, Optional, Any
from PIL import Image, ImageTk
import numpy as np

# imagehashライブラリのimport（オプション）
try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    print("Warning: imagehash not installed. Install with: pip install imagehash")

class OBSControlData:
    """OBS制御設定のデータ管理クラス"""
    
    def __init__(self, config_file="obs_control_config.json"):
        self.config_file = config_file
        self.control_settings: List[Dict[str, Any]] = []
        self.load_settings()
    
    def load_settings(self):
        """設定ファイルから制御設定を読み込む"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.control_settings = data.get("control_settings", [])
            except Exception as e:
                print(f"OBS制御設定読み込みエラー: {e}")
                self.control_settings = []
    
    def save_settings(self):
        """設定ファイルに制御設定を保存"""
        try:
            data = {"control_settings": self.control_settings}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"OBS制御設定保存エラー: {e}")
    
    def add_setting(self, setting: Dict[str, Any]):
        """新しい制御設定を追加"""
        self.control_settings.append(setting)
        self.save_settings()
    
    def remove_setting(self, index: int):
        """指定インデックスの制御設定を削除"""
        if 0 <= index < len(self.control_settings):
            del self.control_settings[index]
            self.save_settings()
    
    def get_settings_by_trigger(self, trigger: str) -> List[Dict[str, Any]]:
        """指定されたトリガーの設定一覧を取得"""
        return [setting for setting in self.control_settings if setting.get("trigger") == trigger]

class ImageRecognitionData:
    """画像認識設定のデータ管理クラス"""
    
    def __init__(self, config_file="image_recognition_config.json", image_dir="recognition_images"):
        self.config_file = config_file
        self.image_dir = image_dir
        self.recognition_settings: Dict[str, Dict[str, Any]] = {}
        
        # 画像保存ディレクトリを作成
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)
        
        self.load_settings()
    
    def load_settings(self):
        """設定ファイルから画像認識設定を読み込む"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.recognition_settings = data.get("recognition_settings", {})
            except Exception as e:
                print(f"画像認識設定読み込みエラー: {e}")
                self.recognition_settings = {}
    
    def save_settings(self):
        """設定ファイルに画像認識設定を保存"""
        try:
            data = {"recognition_settings": self.recognition_settings}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"画像認識設定保存エラー: {e}")
    
    def save_condition(self, screen_type: str, image: Image.Image, coordinates: Dict[str, int], 
                      hash_value: str, threshold: int):
        """画像認識条件を保存"""
        try:
            # 画像を保存
            image_filename = f"{screen_type}_reference.png"
            image_path = os.path.join(self.image_dir, image_filename)
            image.save(image_path)
            
            # 設定を保存
            self.recognition_settings[screen_type] = {
                "coordinates": coordinates,
                "hash": hash_value,
                "threshold": threshold,
                "image_file": image_filename,
                "image_path": image_path
            }
            
            self.save_settings()
            return True
            
        except Exception as e:
            print(f"画像認識条件保存エラー: {e}")
            return False
    
    def get_condition(self, screen_type: str) -> Optional[Dict[str, Any]]:
        """指定された画面タイプの条件を取得"""
        return self.recognition_settings.get(screen_type)
    
    def has_condition(self, screen_type: str) -> bool:
        """指定された画面タイプの条件が存在するかチェック"""
        return screen_type in self.recognition_settings
    
    def get_all_conditions(self) -> Dict[str, Dict[str, Any]]:
        """すべての条件を取得"""
        return self.recognition_settings

class OBSControlWindow:
    """OBS制御設定ウィンドウ"""
    
    # ゲーム状態トリガー定義
    TRIGGERS = {
        "app_start": "アプリ起動時",
        "app_end": "アプリ終了時", 
        "select_start": "選曲画面開始時",
        "select_end": "選曲画面終了時",
        "play_start": "プレー画面開始時",
        "play_end": "プレー画面終了時",
        "result_start": "リザルト画面開始時",
        "result_end": "リザルト画面終了時"
    }
    
    # アクション種別定義
    ACTIONS = {
        "show_source": "ソースを表示",
        "hide_source": "ソースを非表示",
        "switch_scene": "シーンを切り替え"
    }
    
    def __init__(self, parent, obs_manager, config=None):
        self.parent = parent
        self.obs_manager = obs_manager
        self.config = config
        self.control_data = OBSControlData()
        self.image_recognition_data = ImageRecognitionData()  # 画像認識データ管理を追加
        
        # ウィンドウ設定
        self.window = tk.Toplevel(parent)
        self.window.title("OBS制御設定")
        
        # 画面判定条件設定機能が有効な場合は高さを増やす
        if config and config.enable_register_conditions:
            self.window.geometry("900x750")
            self.window.minsize(900, 750)
        else:
            self.window.geometry("800x600")
            self.window.minsize(800, 600)
        
        self.window.resizable(True, True)
        self.window.transient(parent)
        self.window.grab_set()
        
        # OBSデータ
        self.scenes_data = []
        self.sources_data = {}  # {scene_name: [source_list]}
        
        # UI変数
        self.selected_scene_var = tk.StringVar()
        self.selected_source_var = tk.StringVar()
        self.selected_trigger_var = tk.StringVar()
        self.selected_action_var = tk.StringVar()
        self.target_scene_var = tk.StringVar()  # シーン切り替え用
        
        self.setup_ui()
        self.refresh_obs_data()
        self.refresh_settings_list()
        
        # ウィンドウを中央に配置
        self.center_window()
        
        # ウィンドウ閉じる時のイベント
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def setup_ui(self):
        """UIセットアップ"""
        # メインフレーム
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # OBS接続状態表示
        status_frame = ttk.LabelFrame(main_frame, text="OBS接続状態", padding="5")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.obs_status_var = tk.StringVar(value="接続確認中...")
        self.obs_status_label = ttk.Label(status_frame, textvariable=self.obs_status_var)
        self.obs_status_label.pack(side=tk.LEFT)
        
        ttk.Button(status_frame, text="更新", command=self.refresh_obs_data).pack(side=tk.RIGHT)
        
        # 設定追加セクション
        add_frame = ttk.LabelFrame(main_frame, text="新しい制御設定を追加", padding="10")
        add_frame.pack(fill=tk.X, pady=(0, 10))
        
        # トリガー選択
        trigger_frame = ttk.Frame(add_frame)
        trigger_frame.pack(fill=tk.X, pady=2)
        ttk.Label(trigger_frame, text="実行タイミング:", width=15).pack(side=tk.LEFT)
        self.trigger_combo = ttk.Combobox(trigger_frame, textvariable=self.selected_trigger_var, 
                                         values=list(self.TRIGGERS.values()), state="readonly", width=20)
        self.trigger_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # アクション選択
        action_frame = ttk.Frame(add_frame)
        action_frame.pack(fill=tk.X, pady=2)
        ttk.Label(action_frame, text="アクション:", width=15).pack(side=tk.LEFT)
        self.action_combo = ttk.Combobox(action_frame, textvariable=self.selected_action_var,
                                        values=list(self.ACTIONS.values()), state="readonly", width=20)
        self.action_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.action_combo.bind("<<ComboboxSelected>>", self.on_action_changed)
        
        # シーン選択
        scene_frame = ttk.Frame(add_frame)
        scene_frame.pack(fill=tk.X, pady=2)
        ttk.Label(scene_frame, text="対象シーン:", width=15).pack(side=tk.LEFT)
        self.scene_combo = ttk.Combobox(scene_frame, textvariable=self.selected_scene_var,
                                       state="readonly", width=30)
        self.scene_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.scene_combo.bind("<<ComboboxSelected>>", self.on_scene_changed)
        
        # ソース選択（ソース操作時のみ）
        source_frame = ttk.Frame(add_frame)
        source_frame.pack(fill=tk.X, pady=2)
        self.source_label = ttk.Label(source_frame, text="対象ソース:", width=15)
        self.source_label.pack(side=tk.LEFT)
        self.source_combo = ttk.Combobox(source_frame, textvariable=self.selected_source_var,
                                        state="readonly", width=30)
        self.source_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # 切り替え先シーン選択（シーン切り替え時のみ）
        target_scene_frame = ttk.Frame(add_frame)
        target_scene_frame.pack(fill=tk.X, pady=2)
        self.target_scene_label = ttk.Label(target_scene_frame, text="切り替え先シーン:", width=15)
        self.target_scene_label.pack(side=tk.LEFT)
        self.target_scene_combo = ttk.Combobox(target_scene_frame, textvariable=self.target_scene_var,
                                              state="readonly", width=30)
        self.target_scene_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # 追加ボタン
        ttk.Button(add_frame, text="設定を追加", command=self.add_setting).pack(pady=(10, 0))
        
        # 設定一覧表示セクション
        list_frame = ttk.LabelFrame(main_frame, text="登録済み制御設定", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # ツリービュー
        columns = ("trigger", "action", "target", "details")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        
        # ヘッダー設定
        self.tree.heading("trigger", text="実行タイミング")
        self.tree.heading("action", text="アクション")
        self.tree.heading("target", text="対象")
        self.tree.heading("details", text="詳細")
        
        # カラム幅設定
        self.tree.column("trigger", width=150)
        self.tree.column("action", width=120)
        self.tree.column("target", width=200)
        self.tree.column("details", width=250)
        
        # スクロールバー
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 配置
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 削除ボタン
        button_frame = ttk.Frame(list_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="選択した設定を削除", command=self.delete_setting).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="すべて削除", command=self.delete_all_settings).pack(side=tk.LEFT, padx=(10, 0))
        
        # 画面判定条件設定セクション（enable_register_conditionsが有効な場合のみ）
        if self.config and self.config.enable_register_conditions:
            self.setup_image_recognition_section(main_frame)
        
        # 初期状態でUIを更新
        self.update_ui_visibility()
    
    def setup_image_recognition_section(self, parent_frame):
        """画面判定条件設定セクションをセットアップ"""
        if not IMAGEHASH_AVAILABLE:
            # imagehashライブラリがない場合は警告を表示
            warning_frame = ttk.LabelFrame(parent_frame, text="画面判定条件設定（利用不可）", padding="10")
            warning_frame.pack(fill=tk.X, pady=(10, 0))
            
            ttk.Label(warning_frame, text="imagehashライブラリがインストールされていません。", 
                     foreground="red").pack(anchor=tk.W)
            ttk.Label(warning_frame, text="pip install imagehash でインストールしてください。", 
                     foreground="red").pack(anchor=tk.W)
            return
        
        # 画面判定条件設定セクション
        recognition_frame = ttk.LabelFrame(parent_frame, text="画面判定条件設定", padding="10")
        recognition_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(recognition_frame, text="各ゲーム画面を判定するための条件を設定できます。", 
                 foreground="blue").pack(anchor=tk.W, pady=(0, 10))
        
        # 画面タイプ選択ボタン
        button_frame = ttk.Frame(recognition_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(button_frame, text="選曲画面の判定条件を設定", 
                  command=lambda: self.open_image_recognition_dialog("select")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="プレー画面の判定条件を設定", 
                  command=lambda: self.open_image_recognition_dialog("play")).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="リザルト画面の判定条件を設定", 
                  command=lambda: self.open_image_recognition_dialog("result")).pack(side=tk.LEFT, padx=5)
        
        # 設定済み条件の表示
        self.recognition_status_var = tk.StringVar()
        ttk.Label(recognition_frame, textvariable=self.recognition_status_var).pack(anchor=tk.W, pady=(10, 0))
        
        # 設定済み条件の状況を更新
        self.update_recognition_status()
        
        # 初期状態でUIを更新
        self.update_ui_visibility()
    
    def update_recognition_status(self):
        """画像認識設定の状況を更新"""
        if not self.config or not self.config.enable_register_conditions:
            return
        
        conditions = self.image_recognition_data.get_all_conditions()
        screen_names = {"select": "選曲", "play": "プレー", "result": "リザルト"}
        
        if not conditions:
            self.recognition_status_var.set("設定済み条件: なし")
        else:
            status_list = []
            for screen_type, name in screen_names.items():
                if screen_type in conditions:
                    status_list.append(f"{name}画面")
            
            if status_list:
                self.recognition_status_var.set(f"設定済み条件: {', '.join(status_list)}")
            else:
                self.recognition_status_var.set("設定済み条件: なし")
    
    def open_image_recognition_dialog(self, screen_type):
        """画像認識設定ダイアログを開く"""
        if not IMAGEHASH_AVAILABLE:
            messagebox.showerror("エラー", "imagehashライブラリがインストールされていません。")
            return
        
        screen_names = {
            "select": "選曲画面",
            "play": "プレー画面", 
            "result": "リザルト画面"
        }
        
        def on_dialog_close():
            # ダイアログが閉じられた時に状況を更新
            self.update_recognition_status()
        
        dialog = ImageRecognitionDialog(self.window, screen_names[screen_type], screen_type, 
                                       self.image_recognition_data, on_dialog_close)

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
    
    def refresh_obs_data(self):
        """OBSからシーンとソースの情報を取得"""
        if not self.obs_manager.is_connected:
            self.obs_status_var.set("OBSに接続されていません")
            self.scene_combo.configure(values=[])
            self.source_combo.configure(values=[])
            self.target_scene_combo.configure(values=[])
            return
        
        try:
            # シーン一覧取得
            scene_list = self.obs_manager.get_scene_list()
            if scene_list:
                self.scenes_data = scene_list.scenes
                scene_names = [scene["sceneName"] for scene in self.scenes_data]
                
                self.scene_combo.configure(values=scene_names)
                self.target_scene_combo.configure(values=scene_names)
                
                # 各シーンのソース一覧を取得
                self.sources_data = {}
                for scene in self.scenes_data:
                    scene_name = scene["sceneName"]
                    try:
                        scene_items = self.obs_manager.send_command("get_scene_item_list", scene_name=scene_name)
                        if scene_items:
                            sources = [item["sourceName"] for item in scene_items.scene_items]
                            self.sources_data[scene_name] = sources
                    except Exception as e:
                        print(f"シーン {scene_name} のソース取得エラー: {e}")
                        self.sources_data[scene_name] = []
                
                self.obs_status_var.set(f"接続中 - {len(scene_names)}個のシーンを取得")
            else:
                self.obs_status_var.set("シーン情報の取得に失敗")
                
        except Exception as e:
            self.obs_status_var.set(f"データ取得エラー: {str(e)}")
            print(f"OBSデータ取得エラー: {e}")
    
    def on_scene_changed(self, event=None):
        """シーン選択が変更された時の処理"""
        scene_name = self.selected_scene_var.get()
        if scene_name in self.sources_data:
            self.source_combo.configure(values=self.sources_data[scene_name])
            self.selected_source_var.set("")  # リセット
    
    def on_action_changed(self, event=None):
        """アクション選択が変更された時の処理"""
        self.update_ui_visibility()
    
    def update_ui_visibility(self):
        """アクション種別に応じてUI要素の表示/非表示を切り替え"""
        action = self.selected_action_var.get()
        
        if action == "シーンを切り替え":
            # シーン切り替えの場合：対象シーンは不要、切り替え先シーンのみ
            self.source_label.pack_forget()
            self.source_combo.pack_forget()
            self.target_scene_label.pack(side=tk.LEFT)
            self.target_scene_combo.pack(side=tk.LEFT, padx=(5, 0))
        elif action in ["ソースを表示", "ソースを非表示"]:
            # ソース操作の場合：対象シーンとソースが必要
            self.target_scene_label.pack_forget()
            self.target_scene_combo.pack_forget()
            self.source_label.pack(side=tk.LEFT)
            self.source_combo.pack(side=tk.LEFT, padx=(5, 0))
        else:
            # 未選択の場合：すべて非表示
            self.source_label.pack_forget()
            self.source_combo.pack_forget()
            self.target_scene_label.pack_forget()
            self.target_scene_combo.pack_forget()
    
    def add_setting(self):
        """新しい制御設定を追加"""
        trigger_text = self.selected_trigger_var.get()
        action_text = self.selected_action_var.get()
        
        if not trigger_text or not action_text:
            messagebox.showerror("入力エラー", "実行タイミングとアクションを選択してください。")
            return
        
        # trigger_textからキーを逆引き
        trigger_key = None
        for key, value in self.TRIGGERS.items():
            if value == trigger_text:
                trigger_key = key
                break
        
        # action_textからキーを逆引き
        action_key = None
        for key, value in self.ACTIONS.items():
            if value == action_text:
                action_key = key
                break
        
        if not trigger_key or not action_key:
            messagebox.showerror("設定エラー", "無効な設定です。")
            return
        
        # 設定データ作成
        setting = {
            "trigger": trigger_key,
            "action": action_key
        }
        
        if action_key == "switch_scene":
            target_scene = self.target_scene_var.get()
            if not target_scene:
                messagebox.showerror("入力エラー", "切り替え先シーンを選択してください。")
                return
            setting["target_scene"] = target_scene
            
        elif action_key in ["show_source", "hide_source"]:
            scene_name = self.selected_scene_var.get()
            source_name = self.selected_source_var.get()
            if not scene_name or not source_name:
                messagebox.showerror("入力エラー", "対象シーンとソースを選択してください。")
                return
            setting["scene_name"] = scene_name
            setting["source_name"] = source_name
        
        # 設定を追加
        self.control_data.add_setting(setting)
        self.refresh_settings_list()
        
        # 入力フィールドをクリア
        self.selected_trigger_var.set("")
        self.selected_action_var.set("")
        self.selected_scene_var.set("")
        self.selected_source_var.set("")
        self.target_scene_var.set("")
        self.update_ui_visibility()
        
        messagebox.showinfo("追加完了", "制御設定を追加しました。")
    
    def refresh_settings_list(self):
        """設定一覧を更新"""
        # 既存の項目をクリア
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 設定を表示
        for i, setting in enumerate(self.control_data.control_settings):
            trigger_text = self.TRIGGERS.get(setting["trigger"], setting["trigger"])
            action_text = self.ACTIONS.get(setting["action"], setting["action"])
            
            if setting["action"] == "switch_scene":
                target = setting.get("target_scene", "未設定")
                details = f"→ {target}"
            elif setting["action"] in ["show_source", "hide_source"]:
                scene = setting.get("scene_name", "未設定")
                source = setting.get("source_name", "未設定")
                target = f"{scene}"
                details = f"ソース: {source}"
            else:
                target = "未設定"
                details = ""
            
            self.tree.insert("", "end", values=(trigger_text, action_text, target, details))
    
    def delete_setting(self):
        """選択した設定を削除"""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("選択エラー", "削除する設定を選択してください。")
            return
        
        if messagebox.askyesno("削除確認", "選択した設定を削除しますか？"):
            # 選択されたアイテムのインデックスを取得
            for item in selected_items:
                index = self.tree.index(item)
                self.control_data.remove_setting(index)
            
            self.refresh_settings_list()
            messagebox.showinfo("削除完了", "設定を削除しました。")
    
    def delete_all_settings(self):
        """全ての設定を削除"""
        if not self.control_data.control_settings:
            messagebox.showwarning("削除エラー", "削除する設定がありません。")
            return
        
        if messagebox.askyesno("全削除確認", "すべての設定を削除しますか？\nこの操作は取り消せません。"):
            self.control_data.control_settings = []
            self.control_data.save_settings()
            self.refresh_settings_list()
            messagebox.showinfo("削除完了", "すべての設定を削除しました。")
    
    def execute_trigger(self, trigger: str):
        """指定されたトリガーの制御を実行"""
        if not self.obs_manager.is_connected:
            print(f"OBS未接続のため、トリガー '{trigger}' をスキップ")
            return
        
        settings = self.control_data.get_settings_by_trigger(trigger)
        for setting in settings:
            try:
                action = setting["action"]
                
                if action == "switch_scene":
                    target_scene = setting.get("target_scene")
                    if target_scene:
                        self.obs_manager.set_current_scene(target_scene)
                        print(f"シーンを切り替え: {target_scene}")
                
                elif action == "show_source":
                    scene_name = setting.get("scene_name")
                    source_name = setting.get("source_name")
                    if scene_name and source_name:
                        self.obs_manager.send_command("set_scene_item_enabled", 
                                                    scene_name=scene_name, 
                                                    scene_item_id=self._get_scene_item_id(scene_name, source_name),
                                                    scene_item_enabled=True)
                        print(f"ソースを表示: {scene_name}/{source_name}")
                
                elif action == "hide_source":
                    scene_name = setting.get("scene_name")
                    source_name = setting.get("source_name")
                    if scene_name and source_name:
                        self.obs_manager.send_command("set_scene_item_enabled",
                                                    scene_name=scene_name,
                                                    scene_item_id=self._get_scene_item_id(scene_name, source_name),
                                                    scene_item_enabled=False)
                        print(f"ソースを非表示: {scene_name}/{source_name}")
                        
            except Exception as e:
                print(f"制御実行エラー (trigger: {trigger}, setting: {setting}): {e}")
    
    def _get_scene_item_id(self, scene_name: str, source_name: str) -> int:
        """シーンアイテムIDを取得"""
        try:
            result = self.obs_manager.send_command("get_scene_item_id", 
                                                 scene_name=scene_name, 
                                                 source_name=source_name)
            return result.scene_item_id if result else 0
        except Exception as e:
            print(f"シーンアイテムID取得エラー: {e}")
            return 0
    
    def on_close(self):
        """ウィンドウを閉じる"""
        self.window.grab_release()
        self.window.destroy()

class ImageRecognitionDialog:
    """画像認識設定ダイアログ"""
    
    def __init__(self, parent, screen_name, screen_type, image_recognition_data, on_close_callback=None):
        self.parent = parent
        self.screen_name = screen_name
        self.screen_type = screen_type
        self.image_recognition_data = image_recognition_data
        self.on_close_callback = on_close_callback
        
        # ウィンドウ設定
        self.window = tk.Toplevel(parent)
        self.window.title(f"{screen_name}の判定条件設定")
        self.window.geometry("900x700")
        self.window.resizable(True, True)
        self.window.transient(parent)
        self.window.grab_set()
        
        # 画像関連の変数
        self.original_image = None
        self.display_image = None
        self.image_scale = 1.0
        self.canvas = None
        self.selection_rect = None
        self.start_x = self.start_y = 0
        self.end_x = self.end_y = 0
        self.selecting = False
        
        # UI変数
        self.x1_var = tk.IntVar(value=0)
        self.y1_var = tk.IntVar(value=0)
        self.x2_var = tk.IntVar(value=100)
        self.y2_var = tk.IntVar(value=100)
        self.threshold_var = tk.IntVar(value=10)
        self.hash_var = tk.StringVar(value="画像を選択してください")
        
        self.setup_ui()
        
        # 既存設定を読み込み
        self.load_existing_condition()
        
        # ウィンドウを中央に配置
        self.center_window()
        
        # ウィンドウ閉じる時のイベント
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def setup_ui(self):
        """UIセットアップ"""
        # メインフレーム
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 画像選択セクション
        file_frame = ttk.LabelFrame(main_frame, text="画像ファイル選択", padding="10")
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(file_frame, text="画像ファイルを選択", command=self.select_image_file).pack(side=tk.LEFT)
        self.file_label = ttk.Label(file_frame, text="ファイルが選択されていません")
        self.file_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # 画像表示・選択セクション
        image_frame = ttk.LabelFrame(main_frame, text="画像表示・範囲選択", padding="10")
        image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # キャンバス用のフレーム（スクロールバー付き）
        canvas_frame = ttk.Frame(image_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # スクロールバー
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # キャンバス
        self.canvas = tk.Canvas(canvas_frame, bg="white", 
                               yscrollcommand=v_scrollbar.set,
                               xscrollcommand=h_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        v_scrollbar.config(command=self.canvas.yview)
        h_scrollbar.config(command=self.canvas.xview)
        
        # マウスイベントをバインド
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        # ウィンドウサイズ変更時の画像再描画
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        
        # 座標設定セクション
        coord_frame = ttk.LabelFrame(main_frame, text="座標設定", padding="10")
        coord_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 座標入力
        coord_input_frame = ttk.Frame(coord_frame)
        coord_input_frame.pack(fill=tk.X)
        
        ttk.Label(coord_input_frame, text="左上 X:").pack(side=tk.LEFT)
        x1_entry = ttk.Entry(coord_input_frame, textvariable=self.x1_var, width=8)
        x1_entry.pack(side=tk.LEFT, padx=(5, 10))
        x1_entry.bind('<KeyRelease>', self.on_coordinate_changed)
        
        ttk.Label(coord_input_frame, text="Y:").pack(side=tk.LEFT)
        y1_entry = ttk.Entry(coord_input_frame, textvariable=self.y1_var, width=8)
        y1_entry.pack(side=tk.LEFT, padx=(5, 20))
        y1_entry.bind('<KeyRelease>', self.on_coordinate_changed)
        
        ttk.Label(coord_input_frame, text="右下 X:").pack(side=tk.LEFT)
        x2_entry = ttk.Entry(coord_input_frame, textvariable=self.x2_var, width=8)
        x2_entry.pack(side=tk.LEFT, padx=(5, 10))
        x2_entry.bind('<KeyRelease>', self.on_coordinate_changed)
        
        ttk.Label(coord_input_frame, text="Y:").pack(side=tk.LEFT)
        y2_entry = ttk.Entry(coord_input_frame, textvariable=self.y2_var, width=8)
        y2_entry.pack(side=tk.LEFT, padx=(5, 20))
        y2_entry.bind('<KeyRelease>', self.on_coordinate_changed)
        
        ttk.Button(coord_input_frame, text="範囲を更新", command=self.update_selection_and_calculate).pack(side=tk.LEFT, padx=(20, 0))
        
        # ハッシュ計算・しきい値設定セクション
        hash_frame = ttk.LabelFrame(main_frame, text="ハッシュ計算・しきい値設定", padding="10")
        hash_frame.pack(fill=tk.X, pady=(0, 10))
        
        # ハッシュ表示
        hash_display_frame = ttk.Frame(hash_frame)
        hash_display_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(hash_display_frame, text="画像ハッシュ:").pack(side=tk.LEFT)
        ttk.Label(hash_display_frame, textvariable=self.hash_var, foreground="blue").pack(side=tk.LEFT, padx=(5, 0))
        
        # しきい値設定
        threshold_frame = ttk.Frame(hash_frame)
        threshold_frame.pack(fill=tk.X)
        
        ttk.Label(threshold_frame, text="判定しきい値 (1-30):").pack(side=tk.LEFT)
        threshold_scale = ttk.Scale(threshold_frame, from_=1, to=30, orient=tk.HORIZONTAL, 
                                   variable=self.threshold_var, length=200)
        threshold_scale.pack(side=tk.LEFT, padx=(10, 10))
        threshold_scale.configure(command=self.on_threshold_changed)  # 整数値に丸める
        
        threshold_entry = ttk.Entry(threshold_frame, textvariable=self.threshold_var, width=5)
        threshold_entry.pack(side=tk.LEFT, padx=(5, 0))
        threshold_entry.bind('<KeyRelease>', self.on_threshold_entry_changed)
        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="キャンセル", command=self.on_close).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="保存", command=self.save_condition).pack(side=tk.RIGHT)
    
    def on_threshold_changed(self, value):
        """スケールが変更された時に整数値に丸める"""
        self.threshold_var.set(int(float(value)))
    
    def on_threshold_entry_changed(self, event):
        """エントリフィールドが変更された時に値を検証"""
        try:
            value = int(self.threshold_var.get())
            if value < 1:
                self.threshold_var.set(1)
            elif value > 30:
                self.threshold_var.set(30)
        except (ValueError, tk.TclError):
            self.threshold_var.set(10)  # デフォルト値に戻す
    
    def on_coordinate_changed(self, event):
        """座標が変更された時の処理（自動ハッシュ計算）"""
        # 少し遅延させて入力完了を待つ
        if hasattr(self, '_coord_timer'):
            self.window.after_cancel(self._coord_timer)
        self._coord_timer = self.window.after(500, self.update_selection_and_calculate)
    
    def update_selection_and_calculate(self):
        """選択範囲を更新してハッシュを自動計算"""
        self.update_selection()
        self.auto_calculate_hash()
    
    def auto_calculate_hash(self):
        """ハッシュを自動計算（エラー時は静かに失敗）"""
        if not self.original_image or not IMAGEHASH_AVAILABLE:
            return
        
        try:
            # 座標を取得して補正
            x1 = max(0, min(self.x1_var.get(), self.original_image.width))
            y1 = max(0, min(self.y1_var.get(), self.original_image.height))
            x2 = max(0, min(self.x2_var.get(), self.original_image.width))
            y2 = max(0, min(self.y2_var.get(), self.original_image.height))
            
            # 左上と右下を正しく設定
            left = min(x1, x2)
            top = min(y1, y2)
            right = max(x1, x2)
            bottom = max(y1, y2)
            
            if right <= left or bottom <= top:
                self.hash_var.set("範囲が無効です")
                return
            
            # 範囲が小さすぎる場合はスキップ
            if (right - left) < 10 or (bottom - top) < 10:
                self.hash_var.set("範囲が小さすぎます")
                return
            
            # 選択範囲を切り出し
            cropped_image = self.original_image.crop((left, top, right, bottom))
            
            # imagehashを計算
            hash_value = imagehash.average_hash(cropped_image)
            self.hash_var.set(str(hash_value))
            
        except Exception as e:
            # エラー時は静かに失敗（コンソールにログだけ出力）
            print(f"自動ハッシュ計算エラー: {e}")
            self.hash_var.set("計算エラー")

    def load_existing_condition(self):
        """既存の設定を読み込んで表示"""
        condition = self.image_recognition_data.get_condition(self.screen_type)
        if not condition:
            return
        
        try:
            # 画像を読み込み
            image_path = condition.get("image_path")
            if image_path and os.path.exists(image_path):
                self.original_image = Image.open(image_path)
                self.file_label.config(text=f"読み込み済み: {os.path.basename(image_path)}")
                self.display_image_on_canvas()
            
            # 座標を設定
            coordinates = condition.get("coordinates", {})
            self.x1_var.set(coordinates.get("x1", 0))
            self.y1_var.set(coordinates.get("y1", 0))
            self.x2_var.set(coordinates.get("x2", 100))
            self.y2_var.set(coordinates.get("y2", 100))
            
            # ハッシュを設定
            hash_value = condition.get("hash", "")
            if hash_value:
                self.hash_var.set(hash_value)
            
            # しきい値を設定
            threshold = condition.get("threshold", 10)
            self.threshold_var.set(threshold)
            
            # 選択範囲を更新
            self.window.after(100, self.update_selection)  # 少し遅延させて確実に更新
            
            # ハッシュを再計算（設定値と比較のため）
            self.window.after(300, self.auto_calculate_hash)
            
            print(f"{self.screen_name}の既存設定を読み込みました")
            
        except Exception as e:
            print(f"既存設定の読み込みエラー: {e}")
            messagebox.showwarning("警告", f"既存設定の読み込みに失敗しました。\n{str(e)}")

    def center_window(self):
        """ウィンドウを中央に配置（画面内に収まるように調整）"""
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
    
    def select_image_file(self):
        """画像ファイルを選択"""
        file_path = filedialog.askopenfilename(
            title="画像ファイルを選択",
            filetypes=[
                ("画像ファイル", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"),
                ("PNGファイル", "*.png"),
                ("JPEGファイル", "*.jpg *.jpeg"),
                ("すべてのファイル", "*.*")
            ]
        )
        
        if file_path:
            try:
                # 画像を読み込み
                self.original_image = Image.open(file_path)
                self.file_label.config(text=os.path.basename(file_path))
                
                # 画像を表示
                self.display_image_on_canvas()
                
                # 初期座標を設定
                self.x2_var.set(min(self.original_image.width, 200))
                self.y2_var.set(min(self.original_image.height, 200))
                self.update_selection()
                
                # 初期ハッシュを自動計算
                self.window.after(200, self.auto_calculate_hash)
                
            except Exception as e:
                messagebox.showerror("エラー", f"画像の読み込みに失敗しました。\n{str(e)}")
    
    def display_image_on_canvas(self):
        """キャンバスに画像を表示（ウィンドウサイズに合わせて拡大対応）"""
        if not self.original_image:
            return
        
        # キャンバスのサイズを取得
        self.canvas.update_idletasks()  # サイズを確定させる
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            # キャンバスのサイズが確定していない場合は少し待つ
            self.window.after(100, self.display_image_on_canvas)
            return
        
        img_width, img_height = self.original_image.size
        
        # スケール計算（キャンバスのサイズに合わせて、拡大も許可）
        scale_x = canvas_width / img_width
        scale_y = canvas_height / img_height
        
        # 小さい画像の場合は拡大し、大きい画像の場合は縮小
        # アスペクト比を保持しつつ、キャンバスに収まる最大サイズにする
        self.image_scale = min(scale_x, scale_y)
        
        # 最小スケールを設定（あまり小さくなりすぎないように）
        self.image_scale = max(self.image_scale, 0.1)
        
        # 画像をリサイズ
        new_width = int(img_width * self.image_scale)
        new_height = int(img_height * self.image_scale)
        
        # 高品質リサンプリングを使用
        resized_image = self.original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.display_image = ImageTk.PhotoImage(resized_image)
        
        # キャンバスをクリアして画像を表示
        self.canvas.delete("all")
        
        # 画像を中央に配置
        center_x = max(0, (canvas_width - new_width) // 2)
        center_y = max(0, (canvas_height - new_height) // 2)
        
        self.canvas.create_image(center_x, center_y, anchor=tk.NW, image=self.display_image)
        
        # スクロール領域を設定
        scroll_width = max(new_width, canvas_width)
        scroll_height = max(new_height, canvas_height)
        self.canvas.configure(scrollregion=(0, 0, scroll_width, scroll_height))
        
        # 既存の選択範囲があれば再描画
        if hasattr(self, 'selection_rect') and self.selection_rect:
            self.window.after(50, self.draw_selection_rect)
    
    def on_canvas_configure(self, event):
        """キャンバスサイズ変更時の処理"""
        if self.original_image and event.widget == self.canvas:
            # サイズ変更が完了してから画像を再描画
            if hasattr(self, '_resize_timer'):
                self.window.after_cancel(self._resize_timer)
            self._resize_timer = self.window.after(200, self.display_image_on_canvas)

    def on_canvas_click(self, event):
        """キャンバスクリック時の処理"""
        if not self.original_image:
            return
        
        # キャンバス座標を取得
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # 画像の表示オフセットを考慮
        img_width, img_height = self.original_image.size
        new_width = int(img_width * self.image_scale)
        new_height = int(img_height * self.image_scale)
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        center_x = max(0, (canvas_width - new_width) // 2)
        center_y = max(0, (canvas_height - new_height) // 2)
        
        # 画像範囲内かチェック
        if (canvas_x < center_x or canvas_x > center_x + new_width or
            canvas_y < center_y or canvas_y > center_y + new_height):
            return
        
        # 画像座標に変換
        image_x = (canvas_x - center_x) / self.image_scale
        image_y = (canvas_y - center_y) / self.image_scale
        
        self.start_x = int(image_x)
        self.start_y = int(image_y)
        self.selecting = True
        
        # 選択開始座標を設定
        self.x1_var.set(self.start_x)
        self.y1_var.set(self.start_y)
    
    def on_canvas_drag(self, event):
        """キャンバスドラッグ時の処理"""
        if not self.selecting or not self.original_image:
            return
        
        # キャンバス座標を取得
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # 画像の表示オフセットを考慮
        img_width, img_height = self.original_image.size
        new_width = int(img_width * self.image_scale)
        new_height = int(img_height * self.image_scale)
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        center_x = max(0, (canvas_width - new_width) // 2)
        center_y = max(0, (canvas_height - new_height) // 2)
        
        # 画像座標に変換
        image_x = (canvas_x - center_x) / self.image_scale
        image_y = (canvas_y - center_y) / self.image_scale
        
        # 画像範囲内に制限
        self.end_x = int(max(0, min(image_x, img_width)))
        self.end_y = int(max(0, min(image_y, img_height)))
        
        # 終了座標を設定
        self.x2_var.set(self.end_x)
        self.y2_var.set(self.end_y)
        
        # 選択範囲を表示
        self.draw_selection_rect()
    
    def on_canvas_release(self, event):
        """キャンバスリリース時の処理"""
        self.selecting = False
        # マウス操作完了時にハッシュを自動計算
        self.window.after(100, self.auto_calculate_hash)
    
    def update_selection(self):
        """座標入力に基づいて選択範囲を更新"""
        self.draw_selection_rect()
    
    def draw_selection_rect(self):
        """選択範囲の赤い枠を描画（中央配置対応）"""
        if not self.original_image:
            return
        
        # 既存の選択範囲を削除
        if self.selection_rect:
            self.canvas.delete(self.selection_rect)
        
        # 座標を取得して補正
        x1 = max(0, min(self.x1_var.get(), self.original_image.width))
        y1 = max(0, min(self.y1_var.get(), self.original_image.height))
        x2 = max(0, min(self.x2_var.get(), self.original_image.width))
        y2 = max(0, min(self.y2_var.get(), self.original_image.height))
        
        # 左上と右下を正しく設定
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)
        
        # 画像の表示オフセットを考慮
        img_width, img_height = self.original_image.size
        new_width = int(img_width * self.image_scale)
        new_height = int(img_height * self.image_scale)
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        center_x = max(0, (canvas_width - new_width) // 2)
        center_y = max(0, (canvas_height - new_height) // 2)
        
        # 表示用座標に変換（中央配置のオフセットを加算）
        display_left = center_x + (left * self.image_scale)
        display_top = center_y + (top * self.image_scale)
        display_right = center_x + (right * self.image_scale)
        display_bottom = center_y + (bottom * self.image_scale)
        
        # 赤い枠を描画
        self.selection_rect = self.canvas.create_rectangle(
            display_left, display_top, display_right, display_bottom,
            outline="red", width=2
        )
    
    def calculate_hash(self):
        """選択範囲の画像ハッシュを計算"""
        if not self.original_image or not IMAGEHASH_AVAILABLE:
            return
        
        try:
            # 座標を取得して補正
            x1 = max(0, min(self.x1_var.get(), self.original_image.width))
            y1 = max(0, min(self.y1_var.get(), self.original_image.height))
            x2 = max(0, min(self.x2_var.get(), self.original_image.width))
            y2 = max(0, min(self.y2_var.get(), self.original_image.height))
            
            # 左上と右下を正しく設定
            left = min(x1, x2)
            top = min(y1, y2)
            right = max(x1, x2)
            bottom = max(y1, y2)
            
            if right <= left or bottom <= top:
                messagebox.showwarning("警告", "有効な範囲を選択してください。")
                return
            
            # 選択範囲を切り出し
            cropped_image = self.original_image.crop((left, top, right, bottom))
            
            # imagehashを計算
            hash_value = imagehash.average_hash(cropped_image)
            self.hash_var.set(str(hash_value))
            
        except Exception as e:
            messagebox.showerror("エラー", f"ハッシュ計算に失敗しました。\n{str(e)}")
    
    def save_condition(self):
        """判定条件を保存"""
        if not self.original_image:
            messagebox.showwarning("警告", "画像を選択してください。")
            return
        
        hash_value = self.hash_var.get()
        if (not hash_value or hash_value == "画像を選択してください" or 
            hash_value == "範囲が無効です" or hash_value == "範囲が小さすぎます" or 
            hash_value == "計算エラー"):
            messagebox.showwarning("警告", "有効な範囲を選択してハッシュ値を生成してください。")
            return
        
        # 座標を取得
        coordinates = {
            "x1": self.x1_var.get(),
            "y1": self.y1_var.get(),
            "x2": self.x2_var.get(),
            "y2": self.y2_var.get()
        }
        
        # 設定を保存
        success = self.image_recognition_data.save_condition(
            self.screen_type,
            self.original_image,
            coordinates,
            hash_value,
            self.threshold_var.get()
        )
        
        if success:
            messagebox.showinfo("保存完了", f"{self.screen_name}の判定条件を保存しました。")
            self.on_close()
        else:
            messagebox.showerror("保存エラー", "判定条件の保存に失敗しました。")
    
    def on_close(self):
        """ウィンドウを閉じる"""
        if self.on_close_callback:
            self.on_close_callback()
        
        self.window.grab_release()
        self.window.destroy()

# メイン関数（テスト用）
if __name__ == "__main__":
    # テスト用のダミーOBSマネージャー
    class DummyOBSManager:
        def __init__(self):
            self.is_connected = False
        
        def get_scene_list(self):
            return None
        
        def send_command(self, command, **kwargs):
            return None
    
    root = tk.Tk()
    root.withdraw()  # メインウィンドウを非表示
    
    obs_manager = DummyOBSManager()
    control_window = OBSControlWindow(root, obs_manager)
    
    root.mainloop()