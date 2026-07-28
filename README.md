# GUI Screenshot Tool

Windowsアプリのウィンドウだけを撮影し、覚えておいた場所へ同じファイル名で
上書き保存するツールです。README用スクリーンショットを手動で切り抜かずに
更新できます。

## 機能

- 起動中のトップレベルウィンドウをタイトル、ハンドル、状態付きで一覧表示
- 選択したウィンドウだけを撮影（最小化中は誤った画像を防ぐため撮影不可）
- 保存先とファイル名を `%APPDATA%\gui_screenshot_tool\settings.json` に保存
- 保存先ディレクトリを必要に応じて自動作成し、確認なしで上書き
- GUIでいつでも対象ウィンドウ、保存先、ファイル名を変更
- 保存済み設定を使ったワンコマンド撮影

## 動作環境

- Windows 10 / 11
- Python 3.13

## セットアップ

PowerShellでリポジトリを開き、仮想環境へインストールします。

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

開発ツールも入れる場合:

```powershell
python -m pip install -e ".[dev]"
```

## 使い方

GUIを起動します。

```powershell
python main.py
```

一覧から対象ウィンドウを選び、保存先とファイル名を入力して「設定保存」を
押します。「スクリーンショット撮影」は現在の設定を保存してから撮影します。
「更新」で起動後のウィンドウを一覧へ反映できます。

設定変更時も同じGUIを開きます。

```powershell
python main.py --configure
```

一度設定した後はGUIなしで撮影できます。

```powershell
python main.py --capture
```

インストール後は `gui-screenshot-tool` コマンドも利用できます。

## 設定ファイル

設定はユーザーごとに次の場所へUTF-8 JSONとして保存されます。

```text
%APPDATA%\gui_screenshot_tool\settings.json
```

```json
{
  "apps": {
    "default": {
      "window_title": "compare_tool",
      "output_directory": "C:\\work\\compare_tool\\docs\\images",
      "filename": "main_window.png"
    }
  }
}
```

ウィンドウハンドルは起動ごとに変わるため保存せず、撮影時にタイトルから
ウィンドウを探し直します。完全一致を優先し、見つからない場合は部分一致を
使用します。

## 注意点

- 対象ウィンドウは最小化を解除してから撮影してください。
- DRM保護、管理者権限、GPU描画方式などにより `PrintWindow` を拒否する
  アプリは撮影できない場合があります。
- 同じタイトルのウィンドウが複数ある場合は最初に見つかったものを撮影します。
- GUIで選べるのはタイトルのある表示中のトップレベルウィンドウです。

## 開発

```powershell
ruff check .
ruff format --check .
pytest
```

`config`、`windows`、`capture`、`service`、`gui`、`cli` を分離しています。
撮影形式、複数プロファイル、待機時間、一括撮影などを各層へ追加しやすい構成です。

## License

[MIT License](LICENSE)
