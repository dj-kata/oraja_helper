#!/usr/bin/python3
import pickle
import json
import traceback
from config import Config

class SafeUnpickler(pickle.Unpickler):
    """クラス情報を無視してデータのみを辞書として読み込むUnpickler"""
    
    def find_class(self, module, name):
        # すべてのクラスを辞書型で作成するダミークラスを返す
        class DummyClass(dict):
            def __setstate__(self, state):
                self.update(state)
            def __getstate__(self):
                return dict(self)
        return DummyClass

def create_dummy_class():
    """一時的にBmsMiscSettingsクラスを作成してpickleを読み込む"""
    class BmsMiscSettings:
        def __init__(self):
            pass
    
    # settingsモジュールにダミークラスを追加
    import sys
    if 'settings' not in sys.modules:
        import types
        settings_module = types.ModuleType('settings')
        sys.modules['settings'] = settings_module
    
    sys.modules['settings'].BmsMiscSettings = BmsMiscSettings
    return BmsMiscSettings

def convert_with_dummy_class(pickle_file_path):
    """ダミークラスを作成してpickleを読み込む方法"""
    try:
        create_dummy_class()
        
        with open(pickle_file_path, 'rb') as f:
            data = pickle.load(f)
            
        # オブジェクトの属性を辞書として取得
        if hasattr(data, '__dict__'):
            return data.__dict__
        else:
            return vars(data)
            
    except Exception as e:
        print(f"Error with dummy class method: {e}")
        traceback.print_exc()
        return None

if __name__ == '__main__':
    pickle_file = 'settings.pkl'
    json_file = 'settings.json'
    
    print("\nMethod 2: Using dummy class")
    data = convert_with_dummy_class(pickle_file)
    if data:
        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            print("Successfully converted using dummy class method")
        except Exception as e:
            print(f"Error writing JSON: {e}")
    
    # 変換されたデータの確認
    if data:
        print(f"\nConverted data preview:")
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                converted_data = json.load(f)
                for key, value in list(converted_data.items())[:5]:  # 最初の5項目のみ表示
                    print(f"  {key}: {value}")
                if len(converted_data) > 5:
                    print(f"  ... and {len(converted_data) - 5} more items")
        except Exception as e:
            print(f"Error reading converted JSON: {e}")
