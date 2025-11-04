# parse-gaussian-output

Gaussian ログファイルを解析し、結果を JSON 形式で集約する Python プロジェクトです。cclib を使用して量子化学計算のログファイルを処理します。

## 機能

- バッチ処理で複数の Gaussian ログファイルを解析
- SCF エネルギー、振動スペクトル、双極子モーメント、Mulliken 電荷などのデータを抽出
- 結果を JSON ファイルに出力
- 単一ファイル解析のサンプルスクリプトも提供

## インストール

Python 3.10 以上が必要です。

依存関係をインストールするには、以下のコマンドを実行してください：

```bash
pip install -r requirements.lock
```

または、開発用依存関係を含む場合：

```bash
pip install -r requirements-dev.lock
```

## 使用方法

### バッチ解析 (parse_gaussian_logs.py)

ディレクトリ内のすべての `.log` ファイルを解析し、結果を JSON ファイルに出力します。

デフォルトの挙動:
- 引数を指定せずに実行すると、`./out_molecules/cid_75` ディレクトリ内のすべての `*.log` ファイルを解析し、結果を `out_molecules_json/out_molecules.json` ファイルに出力します。

設計の選択:
- 複数の log ファイルを一回の実行でまとめて一つの JSON ファイルに出力する方式を採用しています。これは以下の理由からです：
  - **データ集約の容易さ**: 全体の分析や比較がしやすい。
  - **バッチ処理の効率**: 複数のファイルを一度に処理し、結果を統合できる。
  - **ファイル管理の簡便さ**: 出力ファイルが一つで済む。
  - 個別の JSON ファイル方式と比較すると、ファイル数が少なくなり、管理が簡単ですが、大きなデータセットではファイルサイズが大きくなる可能性があります。

パフォーマンス最適化:
- 並列処理を採用しており、ThreadPoolExecutor を使用して複数のファイルを同時に処理します。これにより、大量のファイル（例: 112243 個）を高速に処理できます。
- `--separate` オプションを使用すると、各ファイルを個別に処理してメモリ使用量を抑えられます。

ログ:
- INFO レベルのログ（処理開始、ファイル数など）は `parsing_info.log` に記録されます。
- ERROR 以上のログ（エラー）は `parsing_errors.log` に記録されます。
- ログはタイムスタンプ付きで、定期的に flush されます。

通知:
- 処理完了時に `DISCORD_URL` 環境変数が設定されている場合、Discord に通知が送信されます。`requests` ライブラリが必要です。

```bash
python parse_gaussian_logs.py [input_dir] [options]
```

引数:
- `input_dir`: ログファイルを含むディレクトリ (デフォルト: `./out_molecules/cid_75`)
- `-p, --pattern`: ファイルパターン (デフォルト: `*.log`)
- `-o, --output`: 出力 JSON ファイルのパス (デフォルト: `out_molecules_json/out_molecules.json`)
- `--separate`: 指定すると、各 log ファイルごとに個別の JSON ファイルを作成 (デフォルト: 一つのファイルにまとめる)

例:
```bash
python parse_gaussian_logs.py /path/to/log/directory
```

### 単一ファイル解析 (parse_logs_sample.py)

単一のログファイルを解析し、結果を JSON ファイルに出力します。

```bash
python parse_logs_sample.py logfile.log [-o output.json]
```

引数:
- `logfile`: 解析するログファイル
- `-o, --out`: 出力ファイルのパス (デフォルト: `logfile.cclib.json`)

## スクリプトの説明

- `parse_gaussian_logs.py`: メインのバッチ解析スクリプト。cclib を使用してログファイルを解析し、結果を集約。
- `parse_logs_sample.py`: 単一ファイル解析のサンプルスクリプト。parse_gaussian_logs.py のインスピレーション元。

## 依存関係

- cclib >= 1.8.1: 量子化学ファイルの解析ライブラリ
- pandas >= 2.3.3: データ処理
- numpy >= 2.2.6: 数値計算
- tqdm >= 4.67.1: 進捗バー表示
- requests >= 2.32.5: HTTP リクエストライブラリ (Discord 通知用)

## 出力データ構造

各ログファイルの解析結果は以下の構造の JSON オブジェクトとして出力されます：

```json
{
  "file": "filename.log",
  "metadata": {...},
  "charge": 0,
  "multiplicity": 1,
  "nbasis": 123,
  "natoms": 10,
  "scf_energies_au": [...],
  "final_scf_energy_au": -123.456,
  "vibrations": {
    "frequencies_cm-1": [...],
    "ir_intensities_km/mol": [...],
    "force_constants_mDyneA": [...],
    "reduced_masses_amu": [...]
  },
  "dipole_moment_debye": {
    "x": 1.23,
    "y": 4.56,
    "z": 7.89,
    "total": 8.12
  },
  "mulliken_charges": [...],
  "zpe_au": 0.123,
  "atom_numbers": [...],
  "final_geometry_angstrom": [...]
}
```

## ライセンス

(ライセンス情報をここに記載してください)
