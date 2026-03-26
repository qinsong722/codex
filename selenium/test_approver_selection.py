import unittest

from selenium.webdriver.common.by import By

from approve_orders import ApproveBot, text_matches


class FakeElement:
    def __init__(
        self,
        text="",
        *,
        displayed=True,
        width=100,
        height=32,
        x=0,
        y=0,
        attributes=None,
        children=None,
        element_id=None,
    ):
        self.text = text
        self._displayed = displayed
        self.rect = {"width": width, "height": height, "x": x, "y": y}
        self._attributes = attributes or {}
        self._children = children or []
        self.id = element_id or f"fake-{id(self)}"

    def is_displayed(self):
        return self._displayed

    def find_elements(self, by, value):
        if by == By.XPATH and value == ".//*":
            return list(self._children)
        return []

    def get_attribute(self, name):
        return self._attributes.get(name)

    def click(self):
        return None


class ApproverSelectionTests(unittest.TestCase):
    def setUp(self):
        self.bot = ApproveBot.__new__(ApproveBot)

    def test_text_matches_ignores_whitespace(self):
        self.assertTrue(text_matches("覃嵩", "  覃嵩  "))

    def test_row_match_finds_nested_name(self):
        row = FakeElement(
            text="",
            children=[FakeElement(text="覃嵩"), FakeElement(text="其他人")],
        )
        self.assertTrue(self.bot.row_matches_approver(row, "覃嵩"))

    def test_click_target_prefers_right_side_checkbox(self):
        label = FakeElement(text="覃嵩", x=20)
        checkbox = FakeElement(
            text="",
            x=280,
            attributes={"class": "van-checkbox__icon"},
        )
        row = FakeElement(text="覃嵩", children=[label, checkbox], x=0)

        target = self.bot.find_approver_click_target(row, "覃嵩")

        self.assertIs(target, checkbox)

    def test_click_target_requires_checkbox_like_target(self):
        label = FakeElement(text="覃嵩", x=20)
        row = FakeElement(text="覃嵩", children=[label], x=0)

        target = self.bot.find_approver_click_target(row, "覃嵩")

        self.assertIsNone(target)

    def test_login_submit_button_prefers_topmost_exact_login(self):
        top_login = FakeElement(text="登录", x=20, y=200, width=320, height=44)
        lower_login = FakeElement(text="登录", x=20, y=500, width=320, height=44)

        class FakeDriver:
            def find_elements(self, by, value):
                return [lower_login, top_login]

        self.bot.driver = FakeDriver()

        target = self.bot.find_login_submit_button()

        self.assertIs(target, top_login)

    def test_should_refocus_code_input_when_focus_is_elsewhere(self):
        code_input = FakeElement(attributes={"value": "12"})

        class FakeDriver:
            current_url = "https://b2bjoy.10086.cn/t100/#/login"

            def execute_script(self, script, *args):
                if "document.activeElement === arguments[0]" in script:
                    return False
                return None

        self.bot.driver = FakeDriver()

        self.assertTrue(self.bot.should_refocus_code_input(code_input))

    def test_should_not_refocus_after_code_complete(self):
        code_input = FakeElement(attributes={"value": "123456"})

        class FakeDriver:
            current_url = "https://b2bjoy.10086.cn/t100/#/login"

            def execute_script(self, script, *args):
                if "document.activeElement === arguments[0]" in script:
                    return False
                return None

        self.bot.driver = FakeDriver()

        self.assertFalse(self.bot.should_refocus_code_input(code_input))

    def test_refocus_attempts_window_activation_before_click(self):
        code_input = FakeElement(attributes={"value": "12"})
        calls = []

        class FakeDriver:
            current_url = "https://b2bjoy.10086.cn/t100/#/login"

            def execute_script(self, script, *args):
                calls.append(("script", script))
                if "document.activeElement === arguments[0]" in script:
                    return False
                return None

        def fake_find_visible(locator, timeout=1):
            return code_input

        def fake_activate_window():
            calls.append(("activate", None))

        def fake_click():
            calls.append(("click", None))

        code_input.click = fake_click
        self.bot.driver = FakeDriver()
        self.bot.find_visible = fake_find_visible
        self.bot.activate_browser_window = fake_activate_window

        self.bot.keep_code_input_focused()

        self.assertEqual(calls[0][0], "script")
        self.assertIn(("activate", None), calls)
        self.assertIn(("click", None), calls)

    def test_refocus_uses_system_click_path(self):
        code_input = FakeElement(attributes={"value": "12"})
        calls = []

        class FakeDriver:
            current_url = "https://b2bjoy.10086.cn/t100/#/login"

            def execute_script(self, script, *args):
                if "document.activeElement === arguments[0]" in script:
                    return False
                calls.append(("script", script))
                return None

        def fake_find_visible(locator, timeout=1):
            return code_input

        def fake_activate_window():
            calls.append(("activate", None))

        def fake_system_click(element):
            calls.append(("system_click", element))

        self.bot.driver = FakeDriver()
        self.bot.find_visible = fake_find_visible
        self.bot.activate_browser_window = fake_activate_window
        self.bot.system_click_code_input = fake_system_click

        self.bot.keep_code_input_focused()

        self.assertIn(("system_click", code_input), calls)


if __name__ == "__main__":
    unittest.main()
