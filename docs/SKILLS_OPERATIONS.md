# Skills（Copilot Instructions）運用ガイド

## 📚 目的

このドキュメントは、GitHub Copilot の **Skills機能**（`.github/copilot-instructions.md`）の役割と、本プロジェクトにおける運用方法を説明します。

---

## 🤖 Skillsとは？

### 概要

`.github/copilot-instructions.md` は、GitHub Copilot に対してプロジェクト固有のルールや開発方針を伝えるファイルです。

### 主な特徴

| 項目 | 説明 |
|------|------|
| **対象** | GitHub Copilot（AI） |
| **適用** | 自動読み込み（全てのチャットで自動適用） |
| **更新** | 手動（人間が明示的に編集） |
| **用途** | プロジェクトの「憲法」（守るべき基本方針） |

### 既存ドキュメントとの違い

| ドキュメント | 対象 | 適用方法 | 更新頻度 |
|--------------|------|----------|----------|
| **HANDOFF.md** | 人間 | 手動参照 | 頻繁（日次〜週次） |
| **PROJECT_SPEC.md** | 人間 | 手動参照 | 中程度（フェーズ毎） |
| **copilot-instructions.md** | AI | **自動適用** | 稀（マイルストーン毎） |

---

## 🎯 本プロジェクトにおける役割

### AI開発アシスタントに伝える内容

1. **プロジェクト概要**
   - AI AutoFormの目的（ワーカーフォーム自動送信）
   - システム構成（VPS 2台、PostgreSQL + Flask + Playwright）

2. **コーディング規約**
   - Python: PEP 8、型ヒント推奨
   - API設計: RESTful、`simple_*` prefix使用
   - データベース: `simple_companies`, `simple_products`, `simple_tasks`

3. **既存資産の優先**
   - Phase 1 MVPの実装を崩さない
   - 既存のsimple_*モデルを基準にする

4. **禁止事項**
   - 既存テーブル構造の勝手な変更
   - 新しいORMライブラリの導入（SQLAlchemyで統一）

5. **優先参照ドキュメント**
   - HANDOFF.md（現在の完成状態）
   - PROJECT_SPEC.md（全体仕様）
   - DEEPBIZ_INTEGRATION.md（DeepBiz連携仕様）

---

## 📋 運用フロー

### 日常的な開発（Phase 1, 2, 3...）

```
1. コーディング・実装
   ↓
2. 人間用ドキュメント更新（HANDOFF.md等）
   ↓
3. 変更内容をコミット
```

→ **この段階ではSkillsファイルは更新しない**

### マイルストーン達成時

```
1. Phaseやアーキテクチャの大きな変更が完了
   ↓
2. 「Skillsに反映すべき変更はありますか？」と相談
   ↓
3. 必要なら.github/copilot-instructions.mdを更新
   ↓
4. コミット＆プッシュ
```

---

## ✅ 反映を検討すべきタイミング

### 反映すべき変更

- ✅ **Phaseの完了**（Phase 1→2→3）
  - 例：Phase 2でワーカー管理機能が追加された
  
- ✅ **アーキテクチャの大きな変更**
  - 例：DB構造が大幅に変更された
  - 例：API設計が刷新された
  
- ✅ **新しい「守るべきルール」の確立**
  - 例：「Gemini APIはgemini_service.pyを通じてのみ利用する」
  
- ✅ **「絶対に壊してはいけない」資産の登場**
  - 例：本番稼働中のsimple_*テーブル

### 反映不要な変更

- ❌ タスクの進捗状況
- ❌ バグ修正履歴
- ❌ 一時的な開発メモ
- ❌ TODO項目

---

## 📝 更新例

### Before: Phase 1完成時

```markdown
## 禁止事項
- 既存のsimple_*テーブル構造を変更しない
- VNC機能は既存ファイルを使用
- 新しいORMライブラリを導入しない
```

### After: Phase 2でワーカー管理完成時

```markdown
## 禁止事項
- 既存のsimple_*テーブル構造を変更しない
- VNC機能は既存ファイルを使用
- 新しいORMライブラリを導入しない
- ワーカー管理APIはworker_service.pyを経由すること（直接DB操作禁止）
```

---

## 🔄 更新プロセス

### ステップ1: 相談

開発者が判断に迷った場合、Copilotに相談：

```
「Phase 2が完了しました。Skillsファイルに反映すべき変更はありますか？」
```

### ステップ2: レビュー

CopilotがHANDOFF.mdやPROJECT_STATUS.mdを確認し、提案：

```
以下の項目を追加することをお勧めします：
- ワーカー管理APIの利用ルール
- VNC統合の設定ファイル参照先
```

### ステップ3: 更新

必要に応じて `.github/copilot-instructions.md` を編集：

```bash
# AIに依頼
「提案内容でcopilot-instructions.mdを更新してください」

# または手動編集
vim .github/copilot-instructions.md
```

### ステップ4: コミット

```bash
git add .github/copilot-instructions.md
git commit -m "docs: Update Copilot instructions for Phase 2 completion"
git push
```

---

## 💡 ベストプラクティス

### DO（推奨）

- ✅ **簡潔に保つ**: 長すぎると効果が薄れる（目安: 50-100行）
- ✅ **具体的に書く**: 「適切に実装する」ではなく「simple_api.pyのパターンに従う」
- ✅ **優先順位を明示**: 重要なルールから順に記載
- ✅ **定期的にレビュー**: Phase完了時に内容を見直す

### DON'T（非推奨）

- ❌ **詳細すぎる実装手順**: 「こう実装しろ」ではなく「この方針で」
- ❌ **頻繁な更新**: 毎日更新すると「憲法」の意味がない
- ❌ **プロジェクト履歴**: 「〇月〇日に実装した」などの時系列情報
- ❌ **未確定の計画**: 「Phase 3で実装予定」などの将来計画

---

## 🎯 本プロジェクトの現状

### 現在のステータス

- **Skillsファイル**: 未作成
- **Phase**: Phase 1 MVP完了、Phase 2準備中
- **推奨アクション**: Phase 2開始前に初版を作成

### 初版作成のタイミング

**今がベストタイミング！**

理由：
1. Phase 1が完成し、守るべき資産が明確
2. Phase 2開始前なので、ルールを事前に設定できる
3. DeepBiz連携の基本方針も確立済み

### 次回の更新予定

- Phase 2完了時（VNC統合、ワーカー管理）
- Phase 3完了時（DeepBiz統合、AI機能）

---

## 📚 参考リンク

- [GitHub Copilot Instructions 公式ドキュメント](https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot)
- 本プロジェクト関連ドキュメント:
  - [HANDOFF.md](../HANDOFF.md) - Phase 1完成状態
  - [PROJECT_SPEC.md](../PROJECT_SPEC.md) - プロジェクト全体仕様
  - [docs/ARCHITECTURE.md](./ARCHITECTURE.md) - システムアーキテクチャ

---

**最終更新**: 2025年12月23日  
**作成者**: プロジェクトチーム  
**対象**: 開発メンバー全員
