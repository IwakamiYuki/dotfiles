#!/usr/bin/env python3
"""
MD Review レビュー結果分析

review.request の JSON 結果を分析し、
- Severity 別集計
- 改善ポイント提案
- 次のステップ推奨

を生成。
"""

import json
from typing import Any, Dict, List


def analyze_review_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    レビュー結果を分析

    Args:
        result: review.request の JSON レスポンス

    Returns:
        分析結果の辞書
    """
    comments = result.get('inline_comments', [])
    global_comments = result.get('global_comments', [])

    # Severity 別集計
    severity_count = {
        'must': len([c for c in comments if c['severity'] == 'must']),
        'should': len([c for c in comments if c['severity'] == 'should']),
        'suggestion': len([c for c in comments if c['severity'] == 'suggestion']),
        'question': len([c for c in comments if c['severity'] == 'question']),
    }

    # ファイル別集計
    file_comments = {}
    for comment in comments:
        file = comment['file']
        if file not in file_comments:
            file_comments[file] = {
                'total': 0,
                'must': 0,
                'should': 0,
                'suggestion': 0,
                'question': 0,
            }
        file_comments[file]['total'] += 1
        file_comments[file][comment['severity']] += 1

    # 次のステップ生成
    next_steps = []
    verdict = result.get('verdict', 'unknown')

    if severity_count['must'] > 0:
        next_steps.append(
            f"1. Fix {severity_count['must']} critical issue(s) marked as 'must'"
        )
    if severity_count['should'] > 0:
        next_steps.append(
            f"2. Consider {severity_count['should']} recommended improvement(s) marked as 'should'"
        )
    if severity_count['suggestion'] > 0:
        next_steps.append(
            f"3. Review {severity_count['suggestion']} suggestion(s) for quality enhancement"
        )

    if verdict == 'approved':
        next_steps.append("✓ Document approved and ready for use!")
    elif verdict == 'commented':
        if not next_steps:
            next_steps.append("Review comments above and re-submit if needed")

    return {
        'verdict': verdict,
        'summary': {
            'total_comments': result['summary'].get('comment_count', 0),
            'inline_comments': result['summary'].get('inline_comment_count', 0),
            'global_comments': result['summary'].get('global_comment_count', 0),
        },
        'severity_count': severity_count,
        'file_comments': file_comments,
        'next_steps': next_steps,
        'comments': comments,
        'global_comments': global_comments,
    }


def format_summary(analysis: Dict[str, Any]) -> str:
    """
    分析結果を人間が読みやすい形式でフォーマット

    Args:
        analysis: analyze_review_result の出力

    Returns:
        フォーマットされた文字列
    """
    lines = []
    lines.append('✅ レビュー完了')
    lines.append('')

    # ステータス
    verdict_display = {
        'approved': '✓ 承認',
        'commented': '📝 コメント付き',
        'cancelled': '⏸️ キャンセル',
    }
    lines.append(f"【ステータス】{verdict_display.get(analysis['verdict'], 'Unknown')}")
    lines.append('')

    # コメント統計
    summary = analysis['summary']
    lines.append('【コメント統計】')
    lines.append(f"  総数: {summary['total_comments']}件")
    lines.append(f"  インライン: {summary['inline_comments']}件")
    lines.append(f"  グローバル: {summary['global_comments']}件")
    lines.append('')

    # Severity 別
    severity = analysis['severity_count']
    if any(severity.values()):
        lines.append('【指摘レベル別】')
        if severity['must'] > 0:
            lines.append(f"  🔴 Must（必須修正）: {severity['must']}件")
        if severity['should'] > 0:
            lines.append(f"  🟡 Should（推奨）: {severity['should']}件")
        if severity['suggestion'] > 0:
            lines.append(f"  🟢 Suggestion（提案）: {severity['suggestion']}件")
        if severity['question'] > 0:
            lines.append(f"  ❓ Question（質問）: {severity['question']}件")
        lines.append('')

    # ファイル別
    if analysis['file_comments']:
        lines.append('【ファイル別コメント数】')
        for file, counts in sorted(analysis['file_comments'].items()):
            lines.append(f"  {file}: {counts['total']}件")
        lines.append('')

    # 次のステップ
    if analysis['next_steps']:
        lines.append('【次のステップ】')
        for step in analysis['next_steps']:
            lines.append(f"  {step}")
        lines.append('')

    return '\n'.join(lines)


def print_comments(analysis: Dict[str, Any], max_comments: int = 10):
    """
    コメント内容を表示

    Args:
        analysis: analyze_review_result の出力
        max_comments: 表示する最大コメント数
    """
    comments = analysis['comments']
    if not comments:
        return

    print('【主要なコメント】')
    for i, comment in enumerate(comments[:max_comments]):
        severity_emoji = {
            'must': '🔴',
            'should': '🟡',
            'suggestion': '🟢',
            'question': '❓',
        }.get(comment['severity'], '•')

        file = comment['file']
        start_line = comment['range']['startLine']
        end_line = comment['range']['endLine']
        text = comment['comment']

        print(f"{i+1}. {severity_emoji} [{file}:{start_line}-{end_line}]")
        print(f"   {text}")

    if len(comments) > max_comments:
        print(f"\n... and {len(comments) - max_comments} more comments")


if __name__ == '__main__':
    # テスト用の dummy レスポンス
    dummy_result = {
        'verdict': 'commented',
        'summary': {
            'comment_count': 5,
            'inline_comment_count': 5,
            'global_comment_count': 0,
        },
        'inline_comments': [
            {
                'file': 'API.md',
                'range': {'startLine': 45, 'endLine': 50},
                'comment': 'Add request/response examples',
                'severity': 'should',
            },
            {
                'file': 'README.md',
                'range': {'startLine': 10, 'endLine': 15},
                'comment': 'Fix typo: intialization → initialization',
                'severity': 'must',
            },
        ],
        'global_comments': [],
    }

    analysis = analyze_review_result(dummy_result)
    print(format_summary(analysis))
    print_comments(analysis)
