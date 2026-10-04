# agent-icons

Agent Sidebar（`tmux/scripts/tmux-agent-sidebar`）が、Claude / Codex の種別をカード上に画像で示すためのアイコン。
`@agent_sidebar_type_icon image` のときだけ使う（既定は文字表示）。

| ファイル | 元のマーク | 色 |
|---|---|---|
| `claude.png` | Claude | `#D97757` |
| `codex.png` | OpenAI（Codex 用） | `#E8E8E8` |

- 元の SVG は [Simple Icons](https://simpleicons.org/)（CC0）から取得し、色を付けて 96×96 の透過 PNG にした
- 各マークは、それぞれの権利者（Anthropic / OpenAI）の商標。ここでは、どのツールのカードかを示す目的でのみ使う
- 差し替えるときは、同じファイル名・正方形・透過 PNG で置く（96×96 程度で十分）
