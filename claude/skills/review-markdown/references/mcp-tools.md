# MCP Tool 詳細仕様

## session.new-id

セッション ID（UUID v4）を生成。

**入力**: なし

**出力**: `string` (UUID v4 形式)

```
例: 550e8400-e29b-41d4-a716-446655440000
```

## review.request

Markdown レビューセッションを開始。Electron アプリを自動起動してセッション UI を表示。

### 入力パラメータ

```typescript
{
  resume_key: string;      // session.new-id で生成した UUID
  title: string;           // セッション表示名
  root: string;            // ファイルの根ディレクトリ（絶対パス）
  files: string[];         // レビュー対象ファイルパス配列
  working_path: string;    // 作業ディレクトリ（Claude Code の実行位置）
  instructions?: string;   // オプション：確認項目ガイド
}
```

### パラメータ詳細

#### resume_key
- 型: `string` (UUID v4)
- 必須: Yes
- 説明: session.new-id で生成した UUID
- 例: `"550e8400-e29b-41d4-a716-446655440000"`

#### title
- 型: `string`
- 必須: Yes
- 説明: セッション表示名（Electron アプリの UI に表示）
- 例: `"API Specification Review"`, `"Documentation Quality Check"`

#### root
- 型: `string` (絶対パス)
- 必須: Yes
- 説明: ファイルの根ディレクトリ。ここを基準に files を解釈
- 例: `"/Users/user/project"`, `"/home/user/docs"`
- ⚠️ **重要**: 必ず絶対パスで指定。相対パスは使用不可

#### files
- 型: `string[]` (ファイルパス配列)
- 必須: Yes
- 説明: レビュー対象ファイルパス。root 相対 or 絶対パスで指定
- 例: `["/Users/user/project/API.md", "/Users/user/project/README.md"]`
- または: `["docs/API.md", "docs/README.md"]` (root 相対)
- ⚠️ **重要**: 複数ファイルの場合、1 セッションで同時表示可能

#### working_path
- 型: `string` (絶対パス)
- 必須: Yes
- 説明: 作業ディレクトリ（Claude Code の現在位置）。ファイル相対パス解釈の基準
- 例: `"/Users/user/project"`
- 用途: ユーザーへ表示するファイルパスを「working_path 基準の相対パス」で表示

#### instructions (オプション)
- 型: `string`
- 必須: No
- 説明: レビュー時の確認項目ガイド。UI 側で表示される
- 例: `"Please check:\n1. Technical accuracy\n2. Clarity\n3. Completeness"`
- デフォルト: 指定なしの場合、ジェネリックなチェックリストが使用される

### 出力（JSON Response）

```typescript
{
  resume_key: string;
  title: string;
  verdict: 'approved' | 'commented' | 'cancelled';
  summary: {
    overall_comment?: string;
    comment_count: number;
    inline_comment_count: number;
    global_comment_count: number;
  };
  inline_comments: InlineComment[];
  global_comments: GlobalComment[];
  meta: {
    startedAt: string;     // ISO 8601 timestamp
    finalizedAt: string;   // ISO 8601 timestamp
    root: string;
    instructions?: string;
    reviewed_files: string[];
    files: FileInfo[];
  };
}
```

### 出力詳細

#### verdict
- `"approved"`: コメントなし、全て承認
- `"commented"`: コメントあり、検討事項あり
- `"cancelled"`: ユーザーが途中でキャンセル

#### summary
- `comment_count`: 総コメント数（inline + global）
- `inline_comment_count`: 行範囲コメント数
- `global_comment_count`: セッション全体コメント数

#### inline_comments (配列)

```typescript
{
  id: string;                        // コメント一意ID (UUID)
  file: string;                      // ファイルパス
  range: {
    startLine: number;               // 開始行（1-indexed）
    endLine: number;                 // 終了行（1-indexed）
  };
  comment: string;                   // コメント本文
  severity: 'must' | 'should' | 'suggestion' | 'question';
  createdAt: string;                 // ISO 8601 timestamp
  anchor: {
    fileContentHash: string;         // ファイルのハッシュ値（変更検出用）
    rangeTextHash?: string;          // 行範囲テキストのハッシュ
    preview?: string;                // 行範囲のテキストプレビュー
  };
}
```

**severity の意味:**
- `"must"`: 必須修正（critical）
- `"should"`: 推奨改善（important）
- `"suggestion"`: 提案改善（optional）
- `"question"`: 質問・確認事項（info）

#### global_comments (配列)

```typescript
{
  id: string;                        // コメント一意ID
  comment: string;                   // コメント本文
  createdAt: string;                 // ISO 8601 timestamp
}
```

#### meta
- `startedAt`, `finalizedAt`: セッション開始・終了時刻
- `reviewed_files`: ユーザーが確認したファイル
- `files`: 各ファイルのメタ情報
  - `file`: ファイルパス
  - `fileContentHash`: ファイルハッシュ（変更検出用）
  - `lineCount`: ファイルの行数

### 動作フロー

1. `resume_key`, `title`, `root`, `files`, `working_path` を指定
2. `review.request` 実行
3. Electron アプリが自動起動
4. ユーザーが Markdown を確認 → コメント追加
5. ユーザーが「Finalize」ボタンをクリック
6. JSON 結果を返却（ブロッキング待機）

### エラーハンドリング

```
Status: error
message: "File not found: /path/to/file.md"
```

主なエラー：
- `"File not found"` - ファイルが存在しない
- `"Invalid path"` - パスが不正
- `"Session already exists"` - resume_key が既に存在
- `"App launch failed"` - Electron アプリ起動失敗

## 実装例

### JavaScript/TypeScript

```typescript
// 1. セッション ID 生成
const sessionId = await tools.call('mcp__md-review__session_new-id');

// 2. review.request 実行
const result = await tools.call('mcp__md-review__review_request', {
  resume_key: sessionId,
  title: 'API Documentation Review',
  root: '/Users/user/project',
  files: [
    '/Users/user/project/docs/API.md',
    '/Users/user/project/README.md',
  ],
  working_path: '/Users/user/project',
  instructions: 'Please check:\n1. Technical accuracy\n2. Clarity',
});

// 3. 結果を JSON で解析
const parsed = JSON.parse(result);
console.log(`Verdict: ${parsed.verdict}`);
console.log(`Comments: ${parsed.summary.comment_count}`);
parsed.inline_comments.forEach(c => {
  console.log(`- [${c.file}:${c.range.startLine}] ${c.comment}`);
});
```

## 重要な注意点

### パス指定ルール

**root と files の関係:**

```
✅ 正しい:
root: "/Users/user/project"
files: ["/Users/user/project/API.md"]

✅ 正しい（相対パス）:
root: "/Users/user/project"
files: ["API.md", "docs/README.md"]

❌ 間違い（相対パス未指定）:
root: "/Users/user/project"
files: ["API.md"]  // working_path 基準ではなく root 基準なので注意

❌ 間違い（相対パスで root を指定）:
root: "."
files: ["docs/API.md"]
```

### セッション冪等性

同じ `resume_key` で 2 回目の `review.request` を実行すると、既存セッションが復旧される。

```typescript
// 1 回目
const result1 = await tools.call('review.request', { resume_key: 'abc-123', ... });

// ユーザーがレビュー → コメント取得

// 2 回目（同じ resume_key）
const result2 = await tools.call('review.request', { resume_key: 'abc-123', ... });
// 既存セッションが復旧される（同じコメント + 新規コメント）
```

### ファイル変更検出

`fileContentHash` を使うことで、レビュー対象ファイルが変更されたか検出可能。

```typescript
const meta1 = result1.meta.files[0].fileContentHash;
const meta2 = result2.meta.files[0].fileContentHash;

if (meta1 !== meta2) {
  console.log('ファイルが変更されました');
}
```
