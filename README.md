# oraja_helperとは？
beatorajaのプレーログ及び、その日に叩いたノーツ数をOBSで表示するツールです。  
ゲーム画面のキャプチャではなく、beatorajaのdbファイルを監視してデータを取得しています。  

リザルトからノーツ数を割り出しているので、選曲画面での空打ちがカウントされず、正確なノーツ数が出ます。  
(pg+gr+gd+bd+見逃しprのみ加算)

OBSにこういう感じのやつが出せます。  
![image](https://github.com/user-attachments/assets/c45d8e91-7f53-4c8b-a3eb-44e1b5e0ec5b)  

v.1.0.6からOBSソースの自動制御にも対応しました。  
選曲画面などのキャプチャ画像を登録することで、どんなスキンを使っていてもシーン検出ができます。  
(~~それどころか、beatoraja以外の音ゲーでも動く気がします~~)  
詳しくは[wiki](https://github.com/dj-kata/oraja_helper/wiki/OBS%E9%80%A3%E6%90%BA%E6%A9%9F%E8%83%BD%E3%81%AE%E8%A8%AD%E5%AE%9A%E6%96%B9%E6%B3%95)を参照してください。

プレーログ(today_result.html)+統計情報(info.html)+OBS制御の動作例(動画)  
https://x.com/cold_planet_/status/1791741023158460618

# 設定方法
1. [releaseページ](https://github.com/dj-kata/oraja_helper/releases)から一番上のoraja_helper.zipをDLし、好きなフォルダに解凍する
2. oraja_helper.exeを実行する
3. メニューバー->settingsよりbeatorajaのパス(本体、プレーヤーフォルダ)を指定する
5. 必要に応じて、```終了時にツイート画面を開く```をチェックする。
4. 必要に応じて、表示したい難易度表のURLを追加することもできます。reloadボタンを押すことで反映されます。
5. OBSにtoday_result.html(プレーログ表示)をD&Dする (-> 幅2000,高さ1500)
6. 必要に応じてOBSにinfo.html(統計情報表示)をD&Dする (-> 幅1200,高さ162)
7. 必要に応じてOBSにreceipt.html(その日の成果まとめ)をD&Dする (-> 幅2400,高さ3000)
7. シーン(選曲、プレー、リザルト)ごとにOBSソースやシーンを自動制御したい場合は[wiki](https://github.com/dj-kata/oraja_helper/wiki/OBS%E9%80%A3%E6%90%BA%E6%A9%9F%E8%83%BD%E3%81%AE%E8%A8%AD%E5%AE%9A%E6%96%B9%E6%B3%95)を参考に設定する。

初期設定後に一度再起動しないとdbの変更が取得されないかもしれません(調査中)

※一度上記設定を行っていれば、それ以降はoraja_helper.exeを実行するだけでOKです

メイン画面にOKと出ていれば動いています。  
![image](https://github.com/dj-kata/oraja_helper/assets/61326119/7acb4c0f-2039-42d8-8bfc-1390a830df85)

beatorajaのパス設定は以下のようになっていればOKです。
playerフォルダはdbファイルが入っているフォルダを指定してください。  
![image](https://github.com/dj-kata/ytlive_helper/assets/61326119/6f7ee76e-77a6-4635-ac02-a3ecc102f403)

自動ツイート設定をすると、oraja_helper終了時にブラウザ上で以下のようなツイート画面が出ます。  
こちらの機能は```メニューバー内のTool->ノーツ数をTweet```からも利用できます。  
![image](https://github.com/user-attachments/assets/b30eb7f1-6740-4321-88e6-0e218a734269)  
※playtime(プレイ画面のみの合計時間)はOBS制御設定からプレイ画面の判定条件を登録した場合のみ表示されます。

また、OBSでtoday_result.htmlのカスタムCSSに以下のプロパティを設定することで、表示する曲数を変更できます。  
(2025/4/10更新)ランプ、スコア、BPが一切更新されなかったプレイを非表示にするための設定も可能です。

```css
:root{
    /*   最大表示曲数を20曲に制限   */
    --num: 20;

    /*   更新のないログを表示しない   */
    --skip-no-update: 1;
}
```

today_result.htmlは幅2000,高さ1500ぐらいを想定しています。
(高さはもっと大きくすることもできます)

info.htmlでは以下のような情報が表示されます。  
幅1200,高さ162ぐらいを想定しています。  
(幅はレイアウトに応じて変更してください)
![image](https://github.com/dj-kata/oraja_helper/assets/61326119/fda9ce59-a35f-498f-b1cd-3e015520283e)

receipt.htmlでは以下のような情報が表示されます。
幅2400，高さ3000ぐらいを想定しています。こちらも配信画面などに合わせて適宜修正してください。
![image](https://github.com/user-attachments/assets/ff5c8e9b-720b-4c55-a913-3b6feb0fbf33)

# その他
今後追加するかもしれない機能
- リザルト画像の自動保存
- 月間、年間ノーツ数の表示
