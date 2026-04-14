import unittest
from pathlib import Path
from unittest.mock import patch

from selenium.common.exceptions import WebDriverException
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

    def test_click_target_accepts_right_side_icon_like_control(self):
        label = FakeElement(text="瑕冨旦", x=20)
        radio_dot = FakeElement(
            text="",
            x=286,
            width=24,
            height=24,
            attributes={"class": "selection-dot"},
        )
        row = FakeElement(text="瑕冨旦", children=[label, radio_dot], x=0, width=360)

        target = self.bot.find_approver_click_target(row, "瑕冨旦")

        self.assertIs(target, radio_dot)


class ApproverAuditTests(unittest.TestCase):
    def setUp(self):
        self.bot = DevtoolsApproveBot.__new__(DevtoolsApproveBot)
        self.bot.last_validated_approver_name = ""
        self.bot.last_validation_mode = ""

    def test_audit_uses_binding_value_when_available(self):
        self.bot.probe_selected_approver_binding_value = lambda: {"value": "Alice", "source": "hidden-input"}
        self.bot.get_selected_approver_name = lambda: "Bob"
        self.bot.get_selected_approver_text = lambda: "Bob"
        self.bot.target_approver_row_looks_selected = lambda name: False
        self.bot.selection_page_contains_approver_name = lambda name: False
        self.bot.driver = object()

        audit = self.bot.assess_selected_approver_audit("Alice")

        self.assertEqual(audit["verdict"], "通过")
        self.assertEqual(audit["binding_value"], "Alice")
        self.assertEqual(audit["binding_source"], "hidden-input")
        self.assertIn("最终绑定值", audit["evidence"])

    def test_audit_flags_binding_mismatch(self):
        self.bot.probe_selected_approver_binding_value = lambda: {"value": "Bob", "source": "hidden-input"}
        self.bot.get_selected_approver_name = lambda: "Bob"
        self.bot.get_selected_approver_text = lambda: "Bob"
        self.bot.target_approver_row_looks_selected = lambda name: False
        self.bot.selection_page_contains_approver_name = lambda name: False
        self.bot.driver = object()

        audit = self.bot.assess_selected_approver_audit("Alice")

        self.assertEqual(audit["verdict"], "未通过")
        self.assertIn("最终绑定值是 'Bob'", audit["evidence"])

    def test_get_selected_approver_name_falls_back_to_flow_tracking(self):
        self.bot.get_selected_approver_text = lambda: ""
        self.bot.get_flow_tracking_active_approver_name = lambda: "Alice"

        self.assertEqual(self.bot.get_selected_approver_name(), "Alice")

    def test_confirm_selected_approver_before_submit_shows_dialog_on_pass(self):
        shown = {"created": False}
        self.bot.assess_selected_approver_audit = lambda expected_name: {
            "verdict": "通过",
            "binding_value": "Alice",
            "binding_source": "hidden-input",
            "actual_name": "Alice",
            "clicked_name": "Alice",
            "clicked_text": "Alice",
            "selection_state": "目标行已选中",
            "visible_target": "目标审批人仍可见",
            "evidence": "最终绑定值 'Alice' 与目标一致。",
            "validation_mode": "",
        }
        self.bot.log = lambda message: None

        class FakeTk:
            def withdraw(self):
                shown["created"] = True

            def attributes(self, *args, **kwargs):
                shown["created"] = True

            def destroy(self):
                shown["created"] = True

        with patch("approve_orders_devtools.tk.Tk", return_value=FakeTk()), patch(
            "approve_orders_devtools.messagebox.askokcancel",
            return_value=False,
        ) as ask:
            with self.assertRaises(RuntimeError):
                self.bot.confirm_selected_approver_before_submit("Alice")

        self.assertTrue(shown["created"])
        self.assertIn("右侧选择圈", ask.call_args.args[1])

    def test_confirm_selected_approver_before_submit_shows_dialog_for_heuristic_pass(self):
        self.bot.assess_selected_approver_audit = lambda expected_name: {
            "verdict": "通过",
            "binding_value": "",
            "binding_source": "",
            "actual_name": "Alice",
            "clicked_name": "Alice",
            "clicked_text": "Alice",
            "selection_state": "目标行已选中",
            "visible_target": "目标审批人仍可见",
            "evidence": "页面文本与目标一致。",
            "validation_mode": "",
        }
        self.bot.log = lambda message: None
        shown = {"created": False}

        class FakeTk:
            def withdraw(self):
                shown["created"] = True

            def attributes(self, *args, **kwargs):
                shown["created"] = True

            def destroy(self):
                shown["created"] = True

        with patch("approve_orders_devtools.tk.Tk", return_value=FakeTk()), patch(
            "approve_orders_devtools.messagebox.askokcancel",
            return_value=False,
        ) as ask:
            with self.assertRaises(RuntimeError):
                self.bot.confirm_selected_approver_before_submit("Alice")

        self.assertTrue(shown["created"])
        self.assertTrue(ask.called)
        self.assertIn("右侧选择圈", ask.call_args.args[1])


class AgreementTests(unittest.TestCase):
    def test_ensure_agreement_checked_uses_image_only(self):
        bot = DevtoolsApproveBot.__new__(DevtoolsApproveBot)
        calls = []

        class FakeDriver:
            current_url = "https://b2bjoy.10086.cn/t100/#/login"

            def __init__(self):
                self.clicked = False

            def execute_script(self, script, *args):
                calls.append(script)
                if "document.elementFromPoint" in script:
                    self.clicked = True
                    return True
                return self.clicked

        bot.driver = FakeDriver()

        bot.ensure_agreement_checked()

        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(bot.driver.clicked)


class IdleRefreshTests(unittest.TestCase):
    def setUp(self):
        self.bot = DevtoolsApproveBot.__new__(DevtoolsApproveBot)
        self.logs = []
        self.bot.log = self.logs.append
        self.bot.dismiss_noise = lambda: None
        self.bot.login_screen_visible = lambda: False
        self.bot.login = lambda: None
        self.bot.open_audit_page = lambda: None
        self.bot.switch_to_pending_approval_tab = lambda: None
        self.bot.click_status_tab = lambda label: None
        self.bot.find_action_buttons = lambda labels, exact=True: []
        self.bot.wait_for_page_ready = lambda settle_seconds=0.0: None
        self.bot.recover_idle_session_if_needed = lambda: False

    def test_refresh_audit_page_uses_single_direct_navigation(self):
        calls = []

        class FakeDriver:
            def refresh(self):
                raise AssertionError("refresh() should not be used for idle reopening")

            def get(self, url):
                calls.append(url)

        self.bot.driver = FakeDriver()

        self.bot.refresh_audit_page()

        self.assertEqual(len(calls), 1)
        self.assertIn("_ts=", calls[0])

    def test_refresh_audit_page_recovers_after_navigation_failure(self):
        recover_calls = []
        state = {"calls": 0}

        class FakeDriver:
            def get(self, url):
                raise WebDriverException("timed out")

        self.bot.driver = FakeDriver()

        def recover():
            state["calls"] += 1
            recover_calls.append("recover")
            return state["calls"] > 1

        self.bot.recover_idle_session_if_needed = recover

        self.bot.refresh_audit_page()

        self.assertGreaterEqual(len(recover_calls), 1)
        self.assertTrue(any("Recovered the session after the idle keepalive reopen failed." in entry for entry in self.logs))


if __name__ == "__main__":
    unittest.main()
