import tkinter as tk
class DraggableWindow:
    def __init__(self, root):
        self.root = root
        self.start_x = 0
        self.start_y = 0
        
        # ドラッグ機能を有効にする
        self.make_draggable(root)
    
    def start_drag(self, event):
        """ドラッグ開始時の処理"""
        self.start_x = event.x
        self.start_y = event.y
    
    def drag_window(self, event):
        """ドラッグ中の処理"""
        # 現在のウィンドウ位置を取得
        x = self.root.winfo_x() + (event.x - self.start_x)
        y = self.root.winfo_y() + (event.y - self.start_y)
        
        # ウィンドウを新しい位置に移動
        self.root.geometry(f"+{x}+{y}")
    
    def make_draggable(self, widget):
        """ウィジェットにドラッグ機能を追加"""
        widget.bind("<Button-1>", self.start_drag)
        widget.bind("<B1-Motion>", self.drag_window)
        
        # 子ウィジェットにも再帰的に適用
        for child in widget.winfo_children():
            # 特定のウィジェットは除外（ボタンクリックなどを阻害しないため）
            if not isinstance(child, (tk.Entry, tk.Text, tk.Listbox, tk.Scale, tk.Scrollbar)):
                self.make_draggable(child)