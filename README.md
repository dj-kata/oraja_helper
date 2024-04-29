# oraja_helperとは？
beatorajaのプレーログ及び、その日に叩いたノーツ数をOBSで表示するツールです。  
ゲーム画面のキャプチャではなく、beatorajaのdbファイルを監視してデータを取得しています。  

リザルトからノーツ数を割り出しているので、選曲画面での空打ちがカウントされず、正確なノーツ数が出ます。  
(pg+gr+gdのみ加算)

OBSにこういう感じのやつが出せます。
![image](https://github.com/dj-kata/oraja_helper/assets/61326119/0f597d3c-27cf-48bb-8f08-5314028c195b)

動画
https://twitter.com/cold_planet_/status/1777387654835007731/video/1

# 設定方法
1. [releaseページ](https://github.com/dj-kata/oraja_helper/releases)から一番上のoraja_helper.zipをDLし、好きなフォルダに解凍する
2. oraja_helper.exeを実行する
3. メニューバー->settingsよりbeatorajaのパスを指定する
4. 必要に応じて、表示したい難易度表のURLを追加することもできます。reloadボタンを押すことで反映されます。
5. OBSにtoday_result.htmlをD&Dする

初期設定後に一度再起動しないとdbの変更が取得されないかもしれません(調査中)

※一度上記設定を行っていれば、それ以降はoraja_helper.exeを実行するだけでOKです

メイン画面にOKと出ていれば動いています。  
![image](https://github.com/dj-kata/oraja_helper/assets/61326119/e7cc5707-4b93-4559-8e91-27c8e408d72a)

beatorajaのパス設定は以下のようになっていればOKです。
playerフォルダはdbファイルが入っているフォルダを指定してください。
![image](https://github.com/dj-kata/oraja_helper/assets/61326119/3a8cc5f0-85f0-4ebf-ab79-abf10b788181)

また、OBSでtoday_result.htmlのカスタムCSSに以下のプロパティを設定することで、表示する曲数を変更できます。

```
:root{
--num: 20;
}
```

today_result.htmlは幅2000,高さ1500ぐらいを想定しています。
(高さはもっと大きくすることもできます)

# その他
OBS連携機能も追加するかもしれません  
- リザルト自動保存
- OBSソースの表示・非表示自動制御
  - 選曲画面、プレー画面、リザルト画面の条件(マッチングに使う画像と領域)をユーザが登録する形を想定
