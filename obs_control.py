import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from typing import List, Dict, Optional, Any
from config import Config
from obssocket import OBSWebSocketManager

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

class OBSControlWindow:
    """OBS制御設定ウィンドウ"""
    
    # ゲーム状態トリガー定義
    TRIGGERS = {
        "app_start": "アプリ起動時",
        "select_start": "選曲画面開始時",
        "select_end": "選曲画面終了時",
        "play_start": "プレー画面開始時",
        "play_end": "プレー画面終了時",
        "result_start": "リザルト画面開始時",
        "result_end": "リザルト画面終了時",
        "app_end": "アプリ終了時", 
    }
    
    # アクション種別定義
    ACTIONS = {
        "show_source": "ソースを表示",
        "hide_source": "ソースを非表示",
        "switch_scene": "シーンを切り替え"
    }
    
    def __init__(self, parent, obs_manager):
        self.parent = parent
        self.obs_manager = obs_manager
        self.control_data = OBSControlData()
        
        # ウィンドウ設定
        self.window = tk.Toplevel(parent)
        self.window.title("OBS制御設定")
        self.window.geometry("900x600")
        self.window.minsize(900, 600)
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
        button_frame.pack(fill=tk.X, pady=2)
        
        ttk.Button(button_frame, text="選択した設定を削除", command=self.delete_setting).pack(fill=tk.X)
        ttk.Button(button_frame, text="すべて削除", command=self.delete_all_settings).pack(fill=tk.X, pady=2)
        
        # 初期状態でUIを更新
        self.update_ui_visibility()
    
    def center_window(self):
        """ウィンドウを親ウィンドウの中央に配置"""
        self.window.update_idletasks()
        
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()
        
        x = parent_x + (parent_width - window_width) // 2
        y = parent_y + (parent_height - window_height) // 2
        
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
                        scene_items = self.obs_manager.get_sources(scene_name)
                        if scene_items:
                            self.sources_data[scene_name] = scene_items
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

# メイン関数（テスト用）
if __name__ == "__main__":
    config = Config()
    print(config.__dict__)
    
    root = tk.Tk()
    #root.withdraw()  # メインウィンドウを非表示
    
    # OBS WebSocket管理クラス初期化
    import time
    obs_manager = OBSWebSocketManager()
    obs_manager.set_config(config)
    obs_manager.start_auto_reconnect()
    time.sleep(1)
    control_window = OBSControlWindow(root, obs_manager)
    
    root.mainloop()