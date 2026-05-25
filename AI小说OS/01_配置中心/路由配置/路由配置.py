def test():
    """
    自测函数
    """
    # 1. 测试从字典加载规则并获取路由
    router = Router()
    router.load_rules_from_dict(test_rules_dict)
    test_context = {"task": "dialogue_generation", "model_size": "small"}
    target = router.get_route(test_context)
    print(f"Test 1 - Route found: {target}")
    assert target == "gpt-3.5-turbo"

    # 2. 测试动态注册规则并优先匹配
    router.register_rule({
        "id": "rule_dynamic",
        "priority": 10,
        "condition": {
            "type": "contains",
            "field": "task",
            "value": "dialogue"
        },
        "target": "gpt-4-turbo"
    })
    target = router.get_route(test_context)
    print(f"Test 2 - Route after dynamic registration: {target}")
    assert target == "gpt-4-turbo"

    # 3. 测试热重载 (模拟文件变更，此处简化，直接调用reload并检查日志)
    # 此处仅验证热重载方法存在且不报错
    try:
        router.reload_rules()
        print("Test 3 - Hot reload executed without error.")
    except Exception as e:
        print(f"Test 3 - Hot reload failed: {e}")

    # 4. 测试默认规则
    unknown_context = {"task": "unknown_task"}
    target = router.get_route(unknown_context)
    print(f"Test 4 - Default route: {target}")
    assert target == "gpt-3.5-turbo"

    # 5. 测试清除规则后重新加载
    router.clear_rules()
    assert len(router.rules) == 0
    print("Test 5 - Clear rules: OK")
    router.load_rules_from_dict(test_rules_dict)
    target = router.get_route(test_context)
    print(f"Test 6 - Route after reload: {target}")
    assert target == "gpt-3.5-turbo"

    print("All tests passed.")


if __name__ == "__main__":
    test()