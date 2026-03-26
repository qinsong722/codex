import unittest
from pathlib import Path
from unittest.mock import patch

from selenium.webdriver.common.by import By

from approve_orders_devtools import (
    CHROME_BINARY_CANDIDATES,
    EDGE_BINARY_CANDIDATES,
    DevtoolsApproveBot,
    is_browser_first_run_page,
    choose_browser_binary,
    build_browser_launch_args,
    text_matches,
)


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


class BrowserSelectionTests(unittest.TestCase):
    def test_choose_browser_binary_prefers_chrome(self):
        chrome_path = Path(CHROME_BINARY_CANDIDATES[0])
        edge_path = Path(EDGE_BINARY_CANDIDATES[0])

        with patch.object(Path, "exists", autospec=True) as exists_mock:
            exists_mock.side_effect = lambda path_obj: path_obj in {chrome_path, edge_path}

            browser_name, browser_path = choose_browser_binary()

        self.assertEqual(browser_name, "chrome")
        self.assertEqual(browser_path, chrome_path)

    def test_choose_browser_binary_falls_back_to_edge(self):
        edge_path = Path(EDGE_BINARY_CANDIDATES[0])

        with patch.object(Path, "exists", autospec=True) as exists_mock:
            exists_mock.side_effect = lambda path_obj: path_obj == edge_path

            browser_name, browser_path = choose_browser_binary()

        self.assertEqual(browser_name, "edge")
        self.assertEqual(browser_path, edge_path)

    def test_choose_browser_binary_can_skip_chrome(self):
        chrome_path = Path(CHROME_BINARY_CANDIDATES[0])
        edge_path = Path(EDGE_BINARY_CANDIDATES[0])

        with patch.object(Path, "exists", autospec=True) as exists_mock:
            exists_mock.side_effect = lambda path_obj: path_obj in {chrome_path, edge_path}

            browser_name, browser_path = choose_browser_binary(excluded={"chrome"})

        self.assertEqual(browser_name, "edge")
        self.assertEqual(browser_path, edge_path)

    def test_build_browser_launch_args_includes_debug_port_and_profile(self):
        profile_dir = Path(r"C:\tmp\ride-approver-devtools-profile")

        args = build_browser_launch_args(profile_dir=profile_dir, debugging_port=9333)

        self.assertIn("--remote-debugging-port=9333", args)
        self.assertIn(f"--user-data-dir={profile_dir}", args)
        self.assertIn("--window-size=404,876", args)

    def test_first_run_page_detection_matches_privacy_screen(self):
        self.assertTrue(is_browser_first_run_page("隐私政策 - Google Chrome", "欢迎使用 Chrome"))
        self.assertFalse(is_browser_first_run_page("商旅100", "获取验证码 登录"))


class ApproverSelectionTests(unittest.TestCase):
    def setUp(self):
        self.bot = DevtoolsApproveBot.__new__(DevtoolsApproveBot)

    def test_text_matches_ignores_whitespace(self):
        self.assertTrue(text_matches("瑕冨旦", "  瑕冨旦  "))

    def test_row_match_finds_nested_name(self):
        row = FakeElement(
            text="",
            children=[FakeElement(text="瑕冨旦"), FakeElement(text="鍏朵粬浜?")],
        )

        self.assertTrue(self.bot.row_matches_approver(row, "瑕冨旦"))

    def test_click_target_prefers_right_side_checkbox(self):
        label = FakeElement(text="瑕冨旦", x=20)
        checkbox = FakeElement(
            text="",
            x=280,
            attributes={"class": "van-checkbox__icon"},
        )
        row = FakeElement(text="瑕冨旦", children=[label, checkbox], x=0)

        target = self.bot.find_approver_click_target(row, "瑕冨旦")

        self.assertIs(target, checkbox)


class AgreementTests(unittest.TestCase):
    def test_ensure_agreement_checked_uses_image_only(self):
        bot = DevtoolsApproveBot.__new__(DevtoolsApproveBot)
        clicks = []

        class AgreementImage:
            def __init__(self, src):
                self._src = src

            def get_attribute(self, name):
                if name == "src":
                    return self._src
                return None

        before = AgreementImage("before")
        after = AgreementImage("after")

        def fake_find_visible(locator, timeout=2):
            if locator[1] in (".private-in img", "//div[contains(@class,'private-in')]//img"):
                return before if not clicks else after
            return None

        def fake_safe_click(element):
            clicks.append(element)

        class FakeDriver:
            current_url = "https://b2bjoy.10086.cn/t100/#/login"

        bot.find_visible = fake_find_visible
        bot.safe_click = fake_safe_click
        bot.driver = FakeDriver()

        bot.ensure_agreement_checked()

        self.assertEqual(len(clicks), 1)
        self.assertIs(clicks[0], before)


if __name__ == "__main__":
    unittest.main()
