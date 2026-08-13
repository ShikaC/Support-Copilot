from scripts.check_dependency_locks import lock_contents_match


def test_lock_contents_match_when_only_generator_comments_differ() -> None:
    # Given: 两份锁文件包含相同版本和 hash，但生成命令注释不同。
    committed = """# generated as requirements.lock.txt
fastapi==0.140.7 \\
    --hash=sha256:accepted
    # via requirements.txt
"""
    generated = """# generated in a temporary directory
fastapi==0.140.7 \\
    --hash=sha256:accepted
    # via requirements.txt
"""

    # When / Then: 工具生成的注释不属于依赖内容，不应造成误报。
    assert lock_contents_match(committed, generated)


def test_lock_contents_do_not_match_when_versions_differ() -> None:
    # Given: 重新生成的锁文件选择了不同版本。
    committed = "fastapi==0.140.7\n"
    generated = "fastapi==0.141.1\n"

    # When / Then: 实际锁定内容变化时必须报告不一致。
    assert not lock_contents_match(committed, generated)


def test_lock_contents_do_not_match_when_dependency_sources_differ() -> None:
    # Given: 包版本相同，但范围文件已经把间接依赖改成直接依赖。
    committed = """fastapi==0.140.7
    # via framework
"""
    generated = """fastapi==0.140.7
    # via requirements.txt
"""

    # When / Then: 依赖来源属于锁文件内容，变化后必须重新生成并提交。
    assert not lock_contents_match(committed, generated)
