"""真实实现的测试：不连网、不接真机，全部用本地替身验证。

跑：python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKE_ADB = os.path.join(REPO_ROOT, "demo", "fake-adb")
FAKE_STATE = "/tmp/elderly-agent-fake-phone.json"

from src.grounding.vlm import VisionGrounding, nearest_element
from src.phone.accessibility import parse_uiautomator_dump
from src.phone.adb_client import ADBClient
from src.phone.cloud_phone import ADBCloudPhone
from src.planner.llm_planner import OpenAIPlanner, parse_actions


def read_fixture(name):
    with open(
        os.path.join(REPO_ROOT, "demo", "fixtures", name), encoding="utf-8"
    ) as f:
        return f.read()


class TestParseActions(unittest.TestCase):
    def test_bare_list(self):
        actions = parse_actions('[{"kind": "open_app", "target": "微信"}]')
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].kind, "open_app")
        self.assertEqual(actions[0].target, "微信")

    def test_wrapped_dict(self):
        actions = parse_actions(
            '{"actions": [{"kind": "tap", "target": "结账按钮", "params": {}}]}'
        )
        self.assertEqual(actions[0].kind, "tap")

    def test_empty(self):
        self.assertEqual(parse_actions("[]"), [])


class TestParseUiautomatorDump(unittest.TestCase):
    def test_desktop(self):
        screen = parse_uiautomator_dump(read_fixture("desktop_dump.xml"))
        self.assertEqual(screen.app, "桌面")
        self.assertEqual(len(screen.elements), 4)
        wechat = screen.find("微信")
        self.assertIsNotNone(wechat)
        self.assertEqual(wechat.package, "com.tencent.mm")
        self.assertEqual(wechat.bounds, (100, 300, 180, 180))

    def test_wechat(self):
        screen = parse_uiautomator_dump(read_fixture("wechat_dump.xml"))
        self.assertEqual(screen.app, "com.tencent.mm")
        self.assertIsNotNone(screen.find("通讯录"))


class TestNearestElement(unittest.TestCase):
    def setUp(self):
        self.screen = parse_uiautomator_dump(read_fixture("desktop_dump.xml"))

    def test_near_point(self):
        el = nearest_element(self.screen, 190, 390)  # 微信图标中心
        self.assertIsNotNone(el)
        self.assertEqual(el.text, "微信")

    def test_far_point_returns_none(self):
        self.assertIsNone(nearest_element(self.screen, 1000, 1900))


class StubClient:
    """假装是 LLM / VLM：返回写死的 JSON，不连网。"""

    def __init__(self, reply):
        self.reply = reply

    def chat(self, messages, response_format=None):
        return self.reply

    def chat_with_image(self, text, image_png, response_format=None):
        return self.reply


class TestOpenAIPlannerWithStub(unittest.TestCase):
    def test_plan_from_llm_json(self):
        client = StubClient('[{"kind": "open_app", "target": "微信"}]')
        actions = OpenAIPlanner(client).plan("打开微信")
        self.assertEqual(actions[0].target, "微信")


class TestVisionGroundingWithStub(unittest.TestCase):
    def setUp(self):
        self.screen = parse_uiautomator_dump(read_fixture("desktop_dump.xml"))

    def test_hit(self):
        # 0-1000 坐标 (175, 203) → 像素 (189, 390)，正好是微信图标中心
        client = StubClient('{"x": 175, "y": 203}')
        el = VisionGrounding(client).locate(self.screen, "微信", b"\x89PNG fake")
        self.assertIsNotNone(el)
        self.assertEqual(el.text, "微信")

    def test_miss_returns_none(self):
        client = StubClient('{"x": -1, "y": -1}')
        self.assertIsNone(
            VisionGrounding(client).locate(self.screen, "微信", b"\x89PNG")
        )

    def test_no_screenshot_returns_none(self):
        client = StubClient('{"x": 175, "y": 203}')
        self.assertIsNone(VisionGrounding(client).locate(self.screen, "微信", None))


class TestADBCloudPhoneAgainstFakeAdb(unittest.TestCase):
    def setUp(self):
        if os.path.exists(FAKE_STATE):
            os.unlink(FAKE_STATE)
        self.phone = ADBCloudPhone(ADBClient(adb=[sys.executable, FAKE_ADB]))
        self.phone.connect()

    def tearDown(self):
        self.phone.disconnect()

    def test_connect_and_screen(self):
        screen = self.phone.current_screen()
        self.assertEqual(screen.app, "桌面")
        self.assertIsNotNone(screen.find("微信"))

    def test_open_app_changes_screen(self):
        self.assertTrue(self.phone.open_app("com.tencent.mm"))
        screen = self.phone.current_screen()
        self.assertEqual(screen.app, "微信")
        self.assertIsNotNone(screen.find("通讯录"))

    def test_tap_and_screencap(self):
        screen = self.phone.current_screen()
        el = screen.find("微信")
        self.assertTrue(self.phone.tap(el))
        png = self.phone.screenshot()
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_screen_size(self):
        self.assertEqual(self.phone.adb.screen_size(), (1080, 1920))


if __name__ == "__main__":
    unittest.main()
