---
name: migration-checklist-execution
description: >-
  Run an interactive execution of a Sapporo (prj-sapporo-migration) data
  migration checklist: copy the round's checklist markdown to a timestamped
  execution record, ask the executor's name, then walk through every checklist
  row top-to-bottom asking whether the work item is complete, and record
  実施日時/実施者/結果/判定, pulling automated results from
  output/reports/checklist_results.json where possible. Use when the user
  says something like "移行作業を始めます", "移行検証を始めます", "本番移行を始めます",
  or otherwise wants to start/run a migration checklist for this repo.
---

# 移行チェックリスト実施

## 前提

- 対象手順書: `docs/migration-policy/{N}回目移行手順書.md`
- 対象チェックリスト: `docs/migration-policy/{N}回目移行チェックリスト.md`（手順書の冒頭に相互参照あり）
- チェックリストの「入力方法」列が、各チェック項目の記録方法（自動／半自動／手動）を示す。これがこのSkillの分岐ロジックの正。
- 自動集計の実データは `output/reports/checklist_results.json`（`scripts/lib/checklist.py` が管理）。人手記録は `python scripts/record_manual_result.py <ID> "<結果>" --by <実施者> --judge <OK|NG> --note "<備考>"` で同ファイルに記録できる。
- `python scripts/render_checklist_report.py` を実行すると、上記JSONから `output/reports/checklist_report.md`（ID別の結果・判定まとめ）が再生成される。困ったら実行前提: `cd data-migration-etl` してから `scripts/` 配下を実行する。

## 手順

### 1. 対象ラウンドの特定

- ユーザーの発言から回次（1回目／2回目／3回目）と、検証／本番のどちらかを判定する。不明な場合は質問する。
- `docs/migration-policy/{N}回目移行チェックリスト.md` の存在を確認する。無ければユーザーに伝えて停止する（既存チェックリストを流用して新規作成することはこのSkillの範囲外）。

### 2. 実施記録用コピーを作成

- タイムスタンプ `YYYYMMDD_HHMMSS`（実行時刻）を生成する。
- `docs/migration-policy/execution-records/` ディレクトリが無ければ作成する。
- 元チェックリストを一切変更せず、`docs/migration-policy/execution-records/{元ファイル名（拡張子なし）}_{タイムスタンプ}.md` としてコピーを作成する。以降の記入はこのコピーにのみ行う。

### 3. 実施者名を質問

- チャットで実施者名を質問する（選択式ではなく自由回答なので `AskQuestion` は使わない）。
- コピーの「0. サマリー」表の「実施者（全体責任者）」に記入し、「実施期間」の開始日時を記録する。

### 4. チェックリストを上から順に処理

「0. サマリー」と末尾の改訂履歴を除き、全セクション（1〜6、6-A〜6-Fを含む）の各行を、表に出てくる順番のまま処理する。各行について「実施作業」「チェック項目」「期待値・確認方法」「入力方法」列を読む。

**4a. 実施作業の完了確認**

- 「実施作業」列が「追加の作業は不要」等、直前の行の実施のみで完了する旨を示す場合 → 質問せずそのまま完了扱いとする。
- それ以外 → 「実施作業」の内容を明示した上で、完了したか質問する。ユーザーが完了したと回答するまで次のチェック記入には進まない。未完了・保留の場合はその旨をコピーに書き残し、次の行に進むか停止するかユーザーに確認する。
- 完了確認が取れたら、その行の「実施日時」に現在時刻（`YYYY-MM-DD HH:MM`）、「実施者」に手順3の名前を入れる。

**4b. 結果・判定の記入（「入力方法」列で分岐）**

| 入力方法 | 対応 |
| --- | --- |
| 自動 | 事前に `python scripts/run_all.py`（または該当する `generate_*.py`）が実行済みか確認し、未実行ならユーザーに実行してもらう。`output/reports/checklist_results.json` からこのチェックID（`1.13_OrderCustomer` や `3.9_guest`、`3.11_raw_total_payment` のような複合キーは `scripts/render_checklist_report.py` の `combine_*`/`ROWS` 定義を参照）の値を読み、結果・判定を記入する。単純には `python scripts/render_checklist_report.py` を実行し、生成された `output/reports/checklist_report.md` の該当行（結果・判定が算出済み）をそのまま転記してよい |
| 半自動（ログ解析）／手動 | バッチ実行ログファイルがあるか確認する。あれば `python scripts/parse_sb00092_log.py <ログファイル>` を実行後、上記「自動」と同様にJSON/レポートから値を取得する。ログが無い・解析失敗の場合は「手動（CLI記録）」と同様にユーザーに確認する |
| 手動（CLI記録） | ユーザーに結果（値）と判定（OK/NG）を質問する。回答を得たら `python scripts/record_manual_result.py <ID> "<結果>" --by "<実施者>" --judge <OK|NG> --note "<備考>"` を実行してJSON/レポートにも反映し、同じ値をコピーに記入する |
| 手動（目視確認のみ） | ユーザーに完了有無・結果（コメント）・判定（OK/NG）を質問し、コピーに記入する。`record_manual_result.py` での記録は任意だが、後続レポートに残したい場合は実施する |

- 判定が NG の場合は、原因・対応方針・再確認結果を「備考」に質問して記入する（チェックリストの記入要領に準拠）。

**4c. コピーへの反映**

- 1行処理するたびに（またはまとめて数行ごとに）該当行の「実施日時」「実施者」「結果（件数等）」「判定」「備考」セルをコピーファイルに書き込む。途中で中断してもコピーに進捗が残るようにする。

### 5. サマリーの確定

- 全行処理後、「0. サマリー」の「実施期間」終了日時を記入する。
- 「総合判定」は、全行の判定が OK（または対象外）なら OK、いずれかが NG なら NG とする。
- NG があれば「特記事項・持ち越し課題」をユーザーに質問して記入する。無ければ「特記事項なし」等を記入する。

### 6. 最終レポート生成

- `python scripts/render_checklist_report.py` を再実行し、`output/reports/checklist_report.md` を最新状態にする。
- 実施記録コピー（`docs/migration-policy/execution-records/*.md`）とレポート（`output/reports/checklist_report.md`）の両方のパスをユーザーに伝える。

## 注意事項

- 元のチェックリスト（`docs/migration-policy/{N}回目移行チェックリスト.md`）は絶対に編集しない。編集対象は常にタイムスタンプ付きコピー。
- チェックリストの列構成は回次ごとに多少変わる可能性があるため、1回目の列順を決め打ちせず、その都度コピー自体の表ヘッダーから列を判定する。
- 検証（`MIGRATION_VERIFICATION=1`）と本番実行では、注文抽出カットオフ日付など環境変数の扱いが異なる（[1回目移行チェックリスト.md](../../../docs/migration-policy/1回目移行チェックリスト.md) 2.9 参照）。どちらの実行かはユーザーに確認し、スクリプト実行を依頼する際に明示する。
