#!/usr/bin/env python3
"""
ファイルパス正規化ユーティリティ

ユーザー入力の相対パスを絶対パスに正規化。
project_root 相対 → working_dir 相対の順で試行。
"""

from pathlib import Path
from typing import List


def normalize_path(
    user_path: str,
    project_root: str,
    working_dir: str,
) -> str:
    """
    ユーザー入力パスを絶対パスに正規化

    Args:
        user_path: ユーザーが指定したパス（相対 or 絶対）
        project_root: プロジェクトルート（絶対パス）
        working_dir: 作業ディレクトリ（絶対パス）

    Returns:
        絶対パス
    """
    path = Path(user_path)

    # 既に絶対パスなら保持
    if path.is_absolute():
        return str(path.resolve())

    # project_root 相対を試行
    project_candidate = (Path(project_root) / path).resolve()
    if project_candidate.exists():
        return str(project_candidate)

    # working_dir 相対を試行
    working_candidate = (Path(working_dir) / path).resolve()
    if working_candidate.exists():
        return str(working_candidate)

    # どちらもなければ project_root 相対を返す
    # （実在しないファイルかもしれないが、一貫性のため）
    return str(project_candidate)


def normalize_paths(
    user_paths: List[str],
    project_root: str,
    working_dir: str,
) -> List[str]:
    """
    複数パスを正規化

    Args:
        user_paths: ユーザーが指定したパスのリスト
        project_root: プロジェクトルート
        working_dir: 作業ディレクトリ

    Returns:
        正規化されたパスのリスト
    """
    return [
        normalize_path(p, project_root, working_dir)
        for p in user_paths
    ]


def validate_files_exist(paths: List[str]) -> tuple[List[str], List[str]]:
    """
    ファイル存在確認

    Args:
        paths: パスリスト

    Returns:
        (存在するパス, 存在しないパス) のタプル
    """
    existing = []
    missing = []

    for p in paths:
        if Path(p).exists():
            existing.append(p)
        else:
            missing.append(p)

    return existing, missing


if __name__ == '__main__':
    # テスト例
    test_paths = ['docs/API.md', 'README.md', 'src/spec.md']
    project_root = '/Users/user/project'
    working_dir = '/Users/user/project'

    normalized = normalize_paths(test_paths, project_root, working_dir)
    print('Normalized paths:')
    for p in normalized:
        print(f'  {p}')

    existing, missing = validate_files_exist(normalized)
    print(f'\nExisting: {len(existing)}, Missing: {len(missing)}')
