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
        self.tweet_on_exit = False
        self.save_on_capture = True
        #self.log_offset = '0'
        self.table_url = ['https://stellabms.xyz/sl/table.html', 'https://mirai-yokohama.sakura.ne.jp/bms/insane_bms.html']

        # OBS制御関連
        self.enable_obs_control = False # OBS連動を有効にする
        self.obs_source = ''
        self.obs_scene_collection = ''
        self.host = 'localhost'
        self.port = '4444'
        self.passwd = ''

        self.obs_enable = {}
        self.obs_disable = {}
        self.obs_scene = {}
        self.obs_trim = {}
        self.obs_target_hash = {}
        self.obs_hash_threshold = {}
        for k in ('boot','select','play','result','quit'):
            self.obs_target_hash[k] = None
            self.obs_hash_threshold[k] = 10
            self.obs_scene[k]   = ''
            if k not in ('boot','quit'):
                self.obs_trim[k] = ['0','0','1920','1080']
                for n in range(2):
                    key = f"{k}{n}"
                    self.obs_enable[key]  = []
                    self.obs_disable[key] = []
            else:
                key = k
                self.obs_enable[key]  = []
                self.obs_disable[key] = []
            
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