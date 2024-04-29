import pickle, os

savefile = 'settings.pkl'

class BmsMiscSettings:
    def __init__(self):
        self.lx = 0
        self.ly = 0
        self.dir_oraja = ''
        self.dir_player = ''
        self.db_songdata = ''
        self.db_songinfo = ''
        self.db_scorelog = ''
        self.db_scoredatalog = ''
        self.db_score    = ''
        self.port = ''
        self.host = 'localhost'
        self.wspass = ''
        self.table_url = ['https://stellabms.xyz/sl/table.html', 'https://mirai-yokohama.sakura.ne.jp/bms/insane_bms.html']
        self.load()
        self.save()

    def load(self):
        try:
            with open(savefile, 'rb') as f:
                tmp = pickle.load(f)
                for k in tmp.__dict__.keys():
                    setattr(self, k, getattr(tmp, k))
        except Exception: # 読み込みエラー時はデフォルトで使う
            pass

    def save(self):
        with open(savefile, 'wb') as f:
            pickle.dump(self, f)

    def is_valid(self):
        """すべての設定ファイルが存在すればTrue,無効な設定があればFalseを返す

        Returns:
            bool: 判定結果
        """
        ret = True
        ret &= os.path.exists(self.db_score)
        ret &= os.path.exists(self.db_scoredatalog)
        ret &= os.path.exists(self.db_scorelog)
        ret &= os.path.exists(self.db_songdata)
        ret &= os.path.exists(self.db_songinfo)
        return ret

if __name__ == '__main__':
    a = BmsMiscSettings()
    a.save()
    print(a.is_valid())