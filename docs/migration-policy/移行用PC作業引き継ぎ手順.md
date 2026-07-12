# 移行用PC作業引き継ぎ手順

## 目的

データ移行ETL作業（`data-migration-etl`）を、現在の作業PCとは異なる「移行用PC」で継続するための手順・注意点をまとめる。
Cursorアカウントは両PCで同一だが、**ワークスペースの内容自体はGitHub経由のプッシュ/プルで引き継ぐ必要がある**。

## 1. 前提

- 移行用PCでも同じCursorアカウントでログインする（追加のアカウント設定は不要）。
- ただしCursorの「Settings Sync」が有効になっていない場合、エディタ設定・拡張機能・キーバインドなどは自動的には引き継がれない。必要であれば移行用PCでも有効化する。
- **エージェントとのチャット履歴・過去のやり取り**（`.cursor/projects/.../agent-transcripts`）はPCローカルに保存されており、GitHub経由では引き継がれない。継続に必要な文脈は本ドキュメントおよび下記の進捗管理ドキュメント（§5）に書き残すこと。

## 2. リポジトリ構成と現状のGit管理状況

このワークスペース（`prj-sapporo-migration.code-workspace`）は3つのフォルダから構成されている。

| フォルダ | Git管理 | リモート | 備考 |
| --- | --- | --- | --- |
| `data-migration-etl` | ✅ 管理済み（`git init`済み、リモートpush済み） | `github.com/gmoms-yamadamio/prj-sapporo-migration`（branch: `main`） | 下記§3参照 |
| `cec-sapporo-front-app-mig/cec-sapporobeer-front-app` | 管理済み | `github.com/gmo-makeshop-si/cec-sapporobeer-front-app`（branch: `migration`） | 通常のclone/pull/pushで引き継ぎ可能 |
| `cec-app-src` | 管理済み | `github.com/cloudec-jp/cec-app`（branch: `release/202606`） | 参照用（カスタマイズ禁止）。未コミットの差分がある場合は要確認 |

`content-migration`（`prj-sapporo-migration`配下の別フォルダ）は今回のスコープ外だが、こちらも現時点でGit未管理。継続作業が必要な場合は同様の対応が必要。

## 3. `data-migration-etl` のリポジトリ設定

`data-migration-etl` フォルダを起点に `git init` → 初回コミット → プッシュ済み。

```bash
cd data-migration-etl
git remote add origin https://github.com/gmoms-yamadamio/prj-sapporo-migration.git
git push -u origin main
```

> **注意**: リポジトリ名は `prj-sapporo-migration` だが、実際にpushしたのは `data-migration-etl` フォルダの内容のみ（このフォルダがリポジトリのルートになっている）。`prj-sapporo-migration` 配下の別フォルダ `content-migration` は含まれていない。プロジェクト全体（`content-migration`含む）をこのリポジトリで管理したい場合は、構成の見直し（例: リポジトリルートに`prj-sapporo-migration`全体を置き直す）が必要になるため、事前に方針を確認すること。

移行用PC側では以下で取得できる。

```bash
git clone https://github.com/gmoms-yamadamio/prj-sapporo-migration.git data-migration-etl
```

### `.gitignore` による本番データ保護

`data-migration-etl/.gitignore` を追加済み。以下のパスは常にGit管理対象外になる（移行用PCで本番相当のPIIデータを同じパスに配置しても、誤ってコミット・プッシュされることはない）。

- `input/raw/*.csv`（旧サイト生CSV）
- `input/cec/*.csv`（CEC会員エクスポート。`member_export_sample.csv`のみ例外的に追跡）
- `output/processed/*.csv`, `output/products/*.csv`, `output/reports/*`（ETL生成物・レポート）

現時点で追跡されているサンプル・ダミーデータ（`member_export_sample.csv`等）はマスク済みのため問題ないが、**本番相当の実データに置き換わった場合は上記パスに置かない、または`.gitignore`の対象パスに配置する**運用を徹底すること。

## 4. 本番PIIデータの取り扱い（Git経由で転送しない）

`input/raw/`, `input/cec/`, `output/` 配下の実データ（会員・注文・住所・ポイント等の個人情報）は、**GitHub経由では転送しない**。移行用PCで作業を継続する場合は、以下のいずれかの安全な方法で個別に転送すること。

- 社内共有ドライブ（アクセス権限が限定されたもの）
- 暗号化USBメモリ
- その他、社内のデータ取り扱いポリシーに準拠した方法

転送後は、同じ相対パス（`data-migration-etl/input/raw/`など）に配置すれば、既存のスクリプトはそのまま動作する。

## 5. 移行用PCでのセットアップ手順

1. **GitHub認証情報の設定**
   移行用PCで以下3つのリポジトリへのアクセス権（SSH鍵 or Personal Access Token）を設定する。
   - `cloudec-jp/cec-app`
   - `gmo-makeshop-si/cec-sapporobeer-front-app`
   - `gmoms-yamadamio/prj-sapporo-migration`

2. **ディレクトリ配置に注意してclone**
   `prj-sapporo-migration.code-workspace` は相対パスで他の2リポジトリを参照している。

   ```json
   {
     "folders": [
       { "path": "." },
       { "path": "../../cec-sapporo-front-app-mig" },
       { "path": "../../cec-app-src" }
     ]
   }
   ```

   このため、移行用PCでも下記のように**同じ相対位置関係**でcloneすること（現PCでのフォルダ構成に対応）。

   ```text
   workspace/
   ├── works/
   │   └── prj-sapporo-migration/
   │       └── data-migration-etl/     ← clone
   ├── cec-sapporo-front-app-mig/
   │   └── cec-sapporobeer-front-app/  ← clone
   └── cec-app-src/                     ← clone
   ```

3. **Python環境確認**
   Python 3.10以上がインストールされていることを確認する（`scripts/requirements.txt`にある通り、追加パッケージのインストールは不要。標準ライブラリのみで動作）。

4. **本番データの配置**（§4の方法で転送したデータを配置）

5. **`prj-sapporo-migration.code-workspace` をCursorで開く**

## 6. 進捗の引き継ぎ

作業の進捗・実施状況は以下の既存ドキュメントに集約されている。移行用PCでの作業開始前に必ず確認すること。

| ドキュメント | 内容 |
| --- | --- |
| [作業方針設計書.md](作業方針設計書.md) | 移行全体の作業方針・手順 |
| [1回目移行チェックリスト.md](1回目移行チェックリスト.md) | 1回目移行の実施チェックリスト |
| `output/reports/checklist_report.md` | チェックリスト自動集計レポート（Markdown、Git管理対象外） |
| `output/reports/checklist_results.json` | チェックリスト結果の生データ（Git管理対象外） |

- 現在の移行ラウンドは環境変数 `MIGRATION_ROUND`（既定値`1`）で管理している。移行用PCでも同じラウンドで作業する場合は明示的に指定するか既定値のままでよいか確認すること。
- `output/reports/*` はGit管理対象外のため、移行用PCへは§4の方法でこれらのファイルも一緒に転送するか、移行用PCで `python scripts/run_all.py` を再実行して再生成すること。

## 7. Cursor固有の注意点まとめ

| 項目 | 引き継がれるか | 対応 |
| --- | --- | --- |
| Cursorアカウント・ログイン | ○（同一アカウント） | 追加設定不要 |
| ルール（`AGENTS.md`, `CLAUDE.md`） | ○ | `cec-app-src`リポジトリに含まれるためcloneで引き継がれる |
| スクリプト・ドキュメント（`data-migration-etl`） | ○ | Git経由でclone/pull |
| エディタ設定・拡張機能 | △ | Settings Sync有効化を確認 |
| エージェントのチャット履歴 | ✗ | 引き継がれない。本ドキュメント・進捗ドキュメントで代替 |
| 本番PIIデータ（実CSV） | ✗（意図的に対象外） | 別ルートで安全に転送（§4） |

## 8. 実施チェックリスト

- [x] `data-migration-etl` 用のリポジトリURLを確認する（`github.com/gmoms-yamadamio/prj-sapporo-migration`）
- [x] `git remote add origin <URL>` → `git push -u origin main` を実行する
- [ ] `content-migration` を含めた管理方針を確認する（§3の注意参照）
- [ ] 移行用PCにGitHub認証情報（3リポジトリ分）を設定する
- [ ] 移行用PCで3リポジトリを正しい相対位置関係でcloneする
- [ ] 移行用PCでPython 3.10+の存在を確認する
- [ ] 本番PIIデータを安全な方法で移行用PCに転送・配置する
- [ ] `output/reports/*` を転送するか、`run_all.py` で再生成する
- [ ] 進捗管理ドキュメント（§6）を確認し、作業を再開する
