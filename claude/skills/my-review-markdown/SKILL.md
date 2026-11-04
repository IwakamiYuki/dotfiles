---
name: my-review-markdown
description: Automatically review Markdown files for quality and accuracy using interactive MD Review UI. Use proactively after generating Markdown (documentation, specs, API docs, design documents, README files, etc.) to validate content before delivery. Trigger when: (1) creating/generating Markdown content, (2) documentation authoring/editing tasks, (3) AI-generated content validation needed, (4) user requests quality review/checking. Provides interactive review session with severity-based comments, auto-analyzes results, and suggests improvements.
---

# Review Markdown with MD Review

Markdown ファイルの品質をインタラクティブに確認する MCP (Model Context Protocol) ツール。セッション生成から結果分析まで自動化。

## 🚀 自動発動ガイド

**このスキルは Markdown 生成後に自動的に使うべき** です。以下のシーンで自分から my-review-markdown を呼び出してください：

### 自動発動すべき場面

1. **ドキュメント生成直後**
   - API 仕様書、設計書、README を生成した
   - 技術ドキュメントを作成した
   - ガイドやマニュアルを執筆した

2. **AI 生成コンテンツの品質確認**
   - Claude が作成した Markdown が正確か確認したい
   - 生成内容が完全か検証したい

3. **ドキュメント編集・修正後**
   - 大幅修正後の品質確認
   - 複数ファイルの整合性確認

### 判定ロジック（何をレビューすべきか）

**レビュー対象と判定する**: `.md` ファイルが以下に該当する場合
- **サイズ**: 500 行以上、または複数セクション（h2 以上が 3 個以上）
- **内容タイプ**: 技術仕様、API ドキュメント、設計書、README、ガイド等
- **状態**: 生成直後、大幅修正後、最終確認前

**判定例**:
- ✅ `API_SPEC.md` (生成直後) → レビュー対象
- ✅ `design-doc.md` (修正完了) → レビュー対象
- ✅ `README.md` (初版作成) → レビュー対象
- ❌ `NOTES.md` (短いメモ) → スキップ
- ❌ `.md` ファイル (表示確認のみ) → スキップ

## 何ができるのか

- **見やすい UI でレビュー**: Electron アプリで Markdown を表示・コメント追加
- **行単位でのコメント**: 指定行範囲に重大度レベル付きコメント（must/should/suggestion/question）
- **複数ファイル同時確認**: 1 セッションで複数 Markdown を同時レビュー
- **結果の自動分析**: コメント数・重大度別集計・改善提案を自動生成
- **AI ループ対応**: 修正結果を AI にフィードバックして改良版生成

## ワークフロー概要

```
ユーザー指定（ファイル + 確認項目）
         ↓
セッション ID 生成
         ↓
MD Review アプリ自動起動
         ↓
Markdown を見やすく表示
         ↓
ユーザーがコメント追加（行単位）
         ↓
完了 → JSON で結果取得
         ↓
コメント分析・改善提案を表示
```

## スキル使用時の流れ

### 1. ファイル指定を確認

ユーザーの発言から、レビュー対象のファイルを特定。

```
ユーザー: 「API_SPEC.md と README.md をレビューしてほしい」
スキル: 対象ファイルを確認 → 相対パス → 絶対パスに正規化
```

### 2. 確認項目をヒアリング

どういう点を確認すべきか、ユーザーに確認。

```
スキル: 「以下の点について確認してほしいことはありますか？
  - 技術精度
  - わかりやすさ
  - 完成度
  - その他」

ユーザー: 「技術精度とわかりやすさを重点的に」
スキル: これを instructions パラメータに含める
```

### 3. セッション生成 & アプリ起動

MCP Tool `session.new-id` → `review.request` を実行。

```
- session.new-id で UUID 生成
- review.request で Electron アプリを自動起動
- ユーザーがセッションを確認
```

### 4. ユーザーがレビュー実施

Electron アプリで：
- Markdown を読んで確認
- 気になる行範囲を選択
- コメント + Severity を入力
- 完了

### 5. 結果を自動分析

JSON レスポンスから：
- コメント数を集計
- Severity 別に分類（must/should/suggestion/question）
- 改善提案を生成

```
✅ レビュー完了

【統計】
- 総コメント数: 5
- Must (必須): 1件
- Should (推奨): 2件
- Suggestion: 2件

【改善ポイント】
1. Must 1件を優先修正
2. Should 2件を確認・検討
3. Suggestion 2件で品質向上
```

## よくあるシーン

### シーン 1: 生成 + レビュー（推奨パターン）

```
ユーザー: 「仕様書を生成してレビューしてほしい」

AI の動作（自動発動）:
1. ユーザーの指示で仕様書 (API_SPEC.md) を生成
2. ファイルサイズ・セクション数を確認
3. 「レビュー対象」と判定
4. 【ここで my-review-markdown スキルを自動呼び出し】
5. セッション生成 → Electron アプリ起動
6. ユーザーがレビュー
7. 結果を分析 → 改善提案を提示
8. 修正版を再生成（必要に応じて）

✨ ポイント: ステップ 4 の自動呼び出しが最重要
   「生成完了」→「すぐにレビュー」のフロー
```

### シーン 2: 複数ファイル同時確認

```
ユーザー: 「docs/ 配下の全 Markdown をチェック」

スキル動作:
1. docs/ 配下を検索 → 見つかったファイルリスト表示
2. ユーザーが確認
3. review.request で 1 セッションで複数ファイル確認
4. ファイル別コメント統計を表示
```

### シーン 3: 複数修正後の最終確認

```
ユーザー: 「README.md を何度も修正したので、品質確認したい」

スキル動作:
1. README.md を特定
2. review.request で「Final Quality Check」セッション開始
3. ユーザーがレビュー
4. 残りの課題があれば提示、なければ「承認」を表示
```

### シーン 4: AI 出力品質の検証

```
ユーザー: 「API ドキュメントの正確性を確認したい」

スキル動作:
1. API_DOCS.md を対象に
2. instructions: 「技術精度を重点的に確認」
3. review.request でレビュー
4. コメント結果から改善提案を生成
5. Claude が修正版を生成（AI ループ）
```

## パラメータ説明

### session.new-id

**入力**: なし

**出力**: UUID v4（例: `550e8400-e29b-41d4-a716-446655440000`）

### review.request

| パラメータ | 説明 | 例 |
|----------|------|-----|
| `resume_key` | セッション ID（session.new-id で生成） | `550e8400-...` |
| `title` | セッション名（UI に表示） | `"API Specification Review"` |
| `root` | ファイルの根ディレクトリ（絶対パス） | `/Users/user/project` |
| `files` | レビュー対象ファイル配列 | `["/path/to/API.md", "/path/to/README.md"]` |
| `working_path` | 作業ディレクトリ（Claude Code の実行位置） | `/Users/user/project` |
| `instructions` | オプション：確認項目ガイド | `"Check: 1) Technical accuracy 2) Clarity"` |

## 結果形式

JSON で以下を取得：

```json
{
  "resume_key": "...",
  "verdict": "approved" | "commented" | "cancelled",
  "summary": {
    "comment_count": 5,
    "inline_comment_count": 5,
    "global_comment_count": 0
  },
  "inline_comments": [
    {
      "id": "...",
      "file": "API.md",
      "range": { "startLine": 45, "endLine": 50 },
      "comment": "Add request/response examples",
      "severity": "should",
      "createdAt": "2025-12-29T14:11:44.158Z"
    }
  ],
  "global_comments": [...]
}
```

## スクリプト・リファレンス

### scripts/normalize_paths.py

ユーザー入力ファイルパスを絶対パスに正規化。

```python
from pathlib import Path

def normalize_path(user_path: str, project_root: str, working_dir: str) -> str:
    """相対パス → 絶対パスに正規化"""
    path = Path(user_path)

    # 既に絶対パスなら保持
    if path.is_absolute():
        return str(path.resolve())

    # project_root 相対を優先、なければ working_dir 相対
    candidates = [
        (project_root / path),
        (working_dir / path),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())

    # デフォルト: project_root 相対を返す
    return str((project_root / path).resolve())
```

### scripts/analyze_result.py

review.request の JSON 結果を分析 & 改善提案を生成。

```python
import json

def analyze_review_result(result: dict) -> dict:
    """レビュー結果を分析"""
    comments = result.get('inline_comments', [])

    # Severity 別集計
    severity_count = {
        'must': len([c for c in comments if c['severity'] == 'must']),
        'should': len([c for c in comments if c['severity'] == 'should']),
        'suggestion': len([c for c in comments if c['severity'] == 'suggestion']),
        'question': len([c for c in comments if c['severity'] == 'question']),
    }

    # 次のステップ生成
    next_steps = []
    if severity_count['must'] > 0:
        next_steps.append(f"1. Fix {severity_count['must']} critical issue(s)")
    if severity_count['should'] > 0:
        next_steps.append(f"2. Consider {severity_count['should']} recommended improvement(s)")
    if result['verdict'] == 'approved':
        next_steps.append("3. ✓ Document approved!")

    return {
        'verdict': result['verdict'],
        'severity_count': severity_count,
        'next_steps': next_steps,
        'comments': comments,
    }
```

### references/mcp-tools.md

MCP Tool の詳細仕様（読み込み時に参照）

### references/error-handling.md

エラーシーン別の対応方法

### assets/instructions_template.txt

review.request の instructions パラメータ用テンプレート。

```
# Review Checklist

Please evaluate the following:

1. **Accuracy** - Is the content technically correct?
2. **Clarity** - Is the text clear and easy to understand?
3. **Completeness** - Are all key points covered?
4. **Structure** - Is the organization logical?
5. **Formatting** - Are code examples, diagrams properly formatted?

Comment using severity levels:
- **Must**: Critical issues
- **Should**: Important improvements
- **Suggestion**: Optional improvements
- **Question**: Points needing clarification
```

## エラーハンドリング

### ファイルが見つからない

```
エラー: File not found: /path/to/file.md

対応:
1. ファイルパスを確認
2. 絶対パス / 相対パスを修正
3. 実在するファイルのリストを表示
4. 再度 review.request を実行
```

### アプリが起動しない

```
エラー: Failed to open Electron app

対応:
1. アプリが /Applications/MD\ Review.app に存在するか確認
2. URL Scheme が登録されているか確認
3. 手動で open "mdreview://session/<resume_key>" を実行
```

### セッション重複

```
エラー: Session already exists

対応:
1. 既存セッションの状態を確認
2. 同じ resume_key で review.request を実行（復旧）
3. または新しい session.new-id を生成
```

## 実装上の推奨事項（AI が自動発動するために）

### 1. Markdown 生成直後の自動判定

Markdown ファイルを生成した時点で、以下を確認：

```
生成したファイル → 行数 ≥ 500 or セクション ≥ 3？
              ↓ YES
              レビュー対象と判定
              ↓
              【Skill: my-review-markdown を呼び出す】
              ↓
              セッション生成 → ユーザーレビュー
```

### 2. 呼び出し条件の具体例

**自動呼び出し対象**:
- API 仕様書、設計ドキュメント、README
- 技術ガイド、ユーザーマニュアル
- 大規模な Markdown 生成物

**自動呼び出し不要**:
- メモ、簡単な説明（数百行以下）
- スニペット、コード片の説明
- 確認のみで品質検証不要なファイル

### 3. ユーザーへのフィードバック例

```
✅ 仕様書を生成しました (API_SPEC.md)

【品質確認中...】
- ファイルサイズ: 850行
- セクション数: 7
→ レビュー対象と判定

【MD Review セッション起動】
Electron アプリで対話的にレビューしてください。
コメント完了後、結果を分析して改善提案を提示します。
```

## 参考資料

- **API 詳細**: `references/mcp-tools.md`
- **エラー対応**: `references/error-handling.md`
- **スクリプト**: `scripts/normalize_paths.py`, `scripts/analyze_result.py`
- **テンプレート**: `assets/instructions_template.txt`
