import json
import os
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "dashboard" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import generate_speaker_appearance as gsa
from pipeline.fetch import generate_real_name_mapping_from_db


class TestSpeakerIdentityRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules_path = ROOT_DIR / "dashboard" / "data" / "speaker_identity_rules.json"
        cls.appearance_path = ROOT_DIR / "dashboard" / "story" / "speaker_appearance.json"
        cls.db_path = ROOT_DIR / "dashboard" / "redive_tw.db"
        cls.real_name_mapping_path = ROOT_DIR / "dashboard" / "data" / "real_name_mapping.json"

        with open(cls.rules_path, "r", encoding="utf-8") as f:
            cls.rules = json.load(f)
        with open(cls.appearance_path, "r", encoding="utf-8") as f:
            cls.appearance = json.load(f)

    def test_01_schema_and_determinism(self):
        self.assertEqual(self.rules.get("version"), "1.0")
        self.assertEqual(self.rules.get("generated_from_truth_version"), "00620004")

        entities = self.rules.get("entities", {})
        speaker_rules = self.rules.get("speaker_rules", {})
        npc_groups = self.rules.get("npc_groups", {})
        npc_rules = self.rules.get("npc_rules", {})
        self.assertEqual(len(entities), 127)
        self.assertGreater(len(speaker_rules), 500)
        self.assertEqual(len(npc_groups), 28)
        self.assertEqual(len(npc_rules), 70)
        self.assertEqual(set(npc_groups) & set(entities), set())
        self.assertEqual(set(npc_rules) & set(speaker_rules), {"神秘女性"})
        self.assertEqual(npc_rules["神秘女性"][0]["allowed_base_ids"], [530])
        self.assertFalse(npc_rules["神秘女性"][0]["allow_null_unit_id"])
        self.assertEqual(speaker_rules["神秘女性"][0]["allowed_base_ids"], [1185])
        self.assertFalse(speaker_rules["神秘女性"][0]["allow_null_unit_id"])
        self.assertFalse(npc_rules["小嬰兒"][0]["allow_null_unit_id"])
        for grp_name, grp in npc_groups.items():
            self.assertEqual(grp["canonical_npc_name"], grp_name)
            self.assertNotIn("real_name", grp)
            self.assertNotIn("profile_unit_id", grp)
            self.assertTrue(all(isinstance(b, int) for b in grp["base_ids"]))
        for bad_kana in [k for k in speaker_rules if gsa.has_japanese_kana(k)] + [k for k in npc_rules if gsa.has_japanese_kana(k)]:
            self.fail(f"規則內不應包含日文假名: {bad_kana}")

        # 驗證各實體 Schema 結構與合併規則
        for canon, ent in entities.items():
            self.assertEqual(ent["canonical_game_name"], canon)
            self.assertIn("real_name", ent)
            self.assertIsInstance(ent["base_ids"], list)
            self.assertTrue(all(isinstance(b, int) for b in ent["base_ids"]))
            self.assertEqual(ent["base_ids"], sorted(set(ent["base_ids"])))
            self.assertIsInstance(ent["profile_unit_id"], int)

        self.assertEqual(entities["拉比林斯達"]["base_ids"], [1068, 1212, 1337])
        self.assertEqual(entities["拉比林斯達"]["profile_unit_id"], 106801)
        self.assertEqual(entities["伊緒"]["base_ids"], [1018, 1101, 1190, 1329])
        self.assertEqual(entities["空花"]["base_ids"], [1045, 1095, 1191, 1270])
        self.assertEqual(entities["靜流"]["base_ids"], [1049, 1091, 1171, 1200, 1365])
        self.assertEqual(entities["似似花"]["base_ids"], [1070, 1150, 1266, 1338])
        self.assertEqual(entities["薇歐莉特"]["real_name"], "菫")
        self.assertEqual(entities["薇歐莉特"]["profile_unit_id"], 133101)
        self.assertEqual(entities["秋乃＆咲戀"]["base_ids"], [1809])

        # 驗證決定性生成（與磁碟上的 JSON 完全一致）
        rebuilt = gsa.build_speaker_identity_rules(db_path=self.db_path)
        self.assertEqual(rebuilt, self.rules)

    def test_02_confirmed_real_names_aliases_and_exclusions(self):
        sr = self.rules["speaker_rules"]

        # 31 位已確認純現實名（必須允許 allow_null_unit_id=True）
        expected_pure_real = {
            "晶": "拉比林斯達",
            "真那": "霸瞳皇帝",
            "紫布菜": "雪菲",
            "克蕾雅": "克蕾琪塔",
            "真璃": "露易絲瑪莉",
            "由仁": "優妮",
            "佳凜": "花凜",
            "寢亞": "涅婭",
            "璃亞": "可璃亞",
            "花子": "克蘿依",
            "蘭": "蘭法",
            "愛莉": "厄莉絲",
            "禰羅": "涅妃‧涅羅",
            "飛白": "格蕾斯",
            "千惠": "克蘿茜",
            "牡丹": "安涅默涅",
            "樞": "庫露露",
            "鳳子": "鳳凰",
            "伽音": "華音",
            "愛來": "埃拉",
            "志名都": "志那都",
            "幸乃": "雪野",
            "夜雲": "阿剌克涅",
            "斜": "拿娜",
            "璐璐": "璐璐伊",
            "希留耶": "凱留",
            "可蘿": "可可蘿",
            "魅空": "美空",
            "菫": "薇歐莉特",
            "撫瑠無": "烏爾姆",
            "燐人": "琳德",
        }
        for name, target in expected_pure_real.items():
            self.assertIn(name, sr, f"缺少純現實名規則: {name}")
            self.assertEqual(sr[name][0]["entity"], target)
            self.assertTrue(sr[name][0]["allow_null_unit_id"])
            expected_bases = sorted(
                set(self.rules["entities"][target]["base_ids"])
                | set(gsa.EXTRA_CHARACTER_BASE_IDS.get(target, ()))
            )
            self.assertEqual(sr[name][0]["allowed_base_ids"], expected_bases)

        # 驗證 A1 25 組專屬額外 base_id 已精準放行，且 1327 不在彩羽中
        for target, extra_ids in gsa.EXTRA_CHARACTER_BASE_IDS.items():
            self.assertIn(target, sr)
            for bid in extra_ids:
                self.assertIn(bid, sr[target][0]["allowed_base_ids"], f"{target} 缺少額外 base_id {bid}")
        self.assertNotIn(1327, sr["彩羽"][0]["allowed_base_ids"])

        # 嚴格禁止納入歸戶規則的項目
        forbidden = [
            "艾爾", "大神", "跳躍王", "拉基拉基", "尾狗刀",
            "詠斗", "贊恩", "善", "？？？", "旁白", "【系統】", "堇",
        ]
        for bad in forbidden:
            self.assertNotIn(bad, sr, f"禁止納入歸戶的字串竟出現在 speaker_rules: {bad}")

        # 萊拉耶爾官方全名與耶兒均歸戶至萊拉耶爾（real_name 維持 祓樹 艾爾），艾爾仍不拆入
        self.assertEqual(self.rules["entities"]["萊拉耶爾"]["real_name"], "祓樹 艾爾")
        self.assertIn("祓樹 艾爾", sr)
        self.assertEqual(sr["祓樹 艾爾"][0]["entity"], "萊拉耶爾")
        self.assertIn("耶兒", sr)
        self.assertEqual(
            sr["耶兒"],
            [{"entity": "萊拉耶爾", "allowed_base_ids": [1265, 1328, 1381], "allow_null_unit_id": True}],
        )

        # 尤絲蒂亞娜 unit_id 分流規則
        yustiana = sr["尤絲蒂亞娜"]
        self.assertEqual(len(yustiana), 2)
        self.assertEqual(
            yustiana[0],
            {"entity": "霸瞳皇帝", "allowed_base_ids": [1069], "allow_null_unit_id": False},
        )
        self.assertEqual(
            yustiana[1],
            {
                "entity": "貪吃佩可",
                "allowed_base_ids": [1058, 1075, 1118, 1210, 1279, 1383, 1804],
                "allow_null_unit_id": False,
            },
        )
        self.assertEqual(sr["尤絲蒂亞娜‧F‧阿斯特賴亞"][0]["entity"], "貪吃佩可")

        # 特別限定與白名單別名
        self.assertEqual(
            sr["１號"],
            [{"entity": "櫻", "allowed_base_ids": [1361], "allow_null_unit_id": False}],
        )
        self.assertEqual(
            sr["宮子（剎鬼）"],
            [{"entity": "剎鬼", "allowed_base_ids": [1359], "allow_null_unit_id": False}],
        )
        expected_aliases = {
            "黑暗伊緒": "伊緒",
            "黑暗空花": "空花",
            "黑暗靜流": "靜流",
            "Misty★霞": "霞",
            "Purely★栞": "栞",
            "Lovely★莫妮卡": "莫妮卡",
            "Shiny★智": "智",
            "諾維姆": "矛依未",
            "修特帕魯": "杏奈",
            "阿剌克涅女士": "阿剌克涅",
            "誓約女君": "克莉絲提娜",
            "變貌大妃": "似似花",
            "変貌大妃": "似似花",
            "迷宮女王": "拉比林斯達",
            "拉比林θ": "拉比林斯達",
            "鮮紅的立方體": "拉比林斯達",
            "拜拉潔耶爾": "萊拉耶爾",
            "碧奇": "碧卡拉",
            "大食客": "貪吃佩可",
            "飢餓的公主": "貪吃佩可",
            "導引者": "可可蘿",
            "引導者": "可可蘿",
            "導引少女": "可可蘿",
            "貓耳魔法少女": "凱留",
            "霸瞳天星": "霸瞳皇帝",
            "可璃": "可璃亞",
            "暮光流星的成員": "流夏",
            "涅雅": "涅婭",
            "士條怜": "怜",
            "士条怜": "怜",
            "風間千愛爾": "琪愛兒",
            "貪吃佩可的聲音": "貪吃佩可",
        }
        for alias, target in expected_aliases.items():
            self.assertIn(alias, sr, f"缺少白名單規則: {alias}")
            self.assertEqual(sr[alias][0]["entity"], target)

    def test_03_unit_id_gating_merge_and_anti_merge(self):
        # 反誤併與隔離測試（含 1900/1920/1916/527/1327 與單話錯植特例）
        self.assertIsNone(gsa.resolve_speaker_identity("１號", 1411, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("碧的聲音", 116911, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("尤絲蒂亞娜", None, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("彩羽", 132741, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("似似花", 106811, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("宮子", 100011, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("七七香", 102811, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("初音", 4211, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("少女", None, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("少女", 211, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("神秘女性", 53011, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("神秘女性", 6511, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("神秘女性", None, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("陌生的女性", None, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("羅塞塔通話中的優妮", None, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("姊姊", 6511, self.rules))
        self.assertIsNone(gsa.resolve_speaker_identity("姊姊", None, self.rules))
        self.assertIsNone(gsa.resolve_appearance_target("ジュン", 104711, self.rules))
        self.assertIsNone(gsa.resolve_appearance_target("オクトー", 106211, self.rules))
        self.assertIsNone(gsa.resolve_appearance_target("ナレーション", None, self.rules))
        self.assertEqual(gsa.resolve_speaker_identity("伊莉亞・奧恩斯坦", None, self.rules), "伊莉亞")
        self.assertEqual(gsa.resolve_speaker_identity("羅塞塔", None, self.rules), "羅塞塔")
        self.assertEqual(gsa.resolve_speaker_identity("大神", 51411, self.rules), "大神")
        self.assertEqual(gsa.resolve_speaker_identity("菲歐？", 190011, self.rules), "愛梅斯")
        self.assertEqual(gsa.resolve_speaker_identity("菲歐？", None, self.rules), "愛梅斯")
        self.assertEqual(gsa.resolve_speaker_identity("澄花", 52711, self.rules), "澄花")
        self.assertEqual(gsa.resolve_speaker_identity("怪奇怪靈", 192011, self.rules), "怪奇怪靈")
        self.assertEqual(gsa.resolve_speaker_identity("美空的角色", 192011, self.rules), "美空的角色")
        self.assertEqual(gsa.resolve_speaker_identity("卡里莎", 191611, self.rules), "卡里莎")
        self.assertEqual(gsa.resolve_speaker_identity("少年", 191611, self.rules), "少年")
        self.assertEqual(gsa.resolve_speaker_identity("史萊姆們", 191611, self.rules), "史萊姆們")
        self.assertEqual(gsa.resolve_appearance_target("長老", 107211, self.rules), "長老")
        self.assertEqual(gsa.resolve_appearance_target("嚮導老君", 107211, self.rules), "嚮導老君")
        self.assertEqual(gsa.resolve_appearance_target("剎鬼‧八斗神", None, self.rules), "剎鬼‧八斗神")
        self.assertEqual(gsa.resolve_appearance_target("變成依里的茜里", 100611, self.rules), "變成依里的茜里")

        # 1A 部分：7 組 NPC 合併群組驗證
        self.assertEqual(gsa.resolve_npc_group("詠斗", 106211, self.rules), "尾狗刀")
        self.assertEqual(gsa.resolve_npc_group("過去的詠斗", 106211, self.rules), "尾狗刀")
        self.assertEqual(gsa.resolve_npc_group("尾狗刀？？？", 106211, self.rules), "尾狗刀")
        self.assertEqual(gsa.resolve_npc_group("跳躍王", 107311, self.rules), "拉基拉基")
        self.assertEqual(gsa.resolve_npc_group("拉基拉基", 999911, self.rules), "拉基拉基")
        self.assertEqual(gsa.resolve_npc_group("拉基尼卡東", None, self.rules), "拉基拉基")
        self.assertEqual(gsa.resolve_npc_group("善", 191711, self.rules), "贊恩")
        self.assertEqual(gsa.resolve_npc_group("回憶的贊恩", 191711, self.rules), "贊恩")
        self.assertEqual(gsa.resolve_npc_group("佐拉", 107211, self.rules), "宙")
        self.assertIsNone(gsa.resolve_npc_group("長老", 107211, self.rules))
        self.assertIsNone(gsa.resolve_npc_group("嚮導老君", 107211, self.rules))
        self.assertEqual(gsa.resolve_npc_group("黎‧普賽爾", 193711, self.rules), "芙蕾雅")
        self.assertEqual(gsa.resolve_npc_group("菲絲雷斯", 193711, self.rules), "芙蕾雅")
        self.assertEqual(gsa.resolve_npc_group("八斗神局長", 193611, self.rules), "八斗神")
        self.assertIsNone(gsa.resolve_npc_group("剎鬼‧八斗神", None, self.rules))
        self.assertEqual(gsa.resolve_npc_group("米奈娃β", 191111, self.rules), "米奈娃")
        self.assertEqual(gsa.resolve_npc_group("過去的米奈娃", 191111, self.rules), "米奈娃")

        # 第二大點：可操作角特殊稱呼與個人劇情匿名代稱（嚴格 unit_id 放行）
        self.assertEqual(gsa.resolve_speaker_identity("小孩彩羽", 132611, self.rules), "彩羽")
        self.assertEqual(gsa.resolve_speaker_identity("成人苑", 132711, self.rules), "苑")
        self.assertEqual(gsa.resolve_speaker_identity("成人苑？", 132711, self.rules), "苑")
        self.assertEqual(gsa.resolve_speaker_identity("羅塞塔通話中的優妮", 116411, self.rules), "優妮")
        self.assertEqual(gsa.resolve_speaker_identity("陌生的女性", 135511, self.rules), "埃拉")
        self.assertEqual(gsa.resolve_speaker_identity("陌生的女性", 135611, self.rules), "志那都")
        self.assertEqual(gsa.resolve_speaker_identity("和服的女性", 135811, self.rules), "雪野")
        self.assertEqual(gsa.resolve_speaker_identity("陰沉的少女", 125611, self.rules), "碧卡拉")
        self.assertEqual(gsa.resolve_speaker_identity("銀髮少女", 133611, self.rules), "梅杜莎")
        self.assertEqual(gsa.resolve_speaker_identity("活潑的小女孩", 132411, self.rules), "彩羽")
        self.assertEqual(gsa.resolve_speaker_identity("黑髮少女", 125811, self.rules), "莉莉")
        self.assertEqual(gsa.resolve_speaker_identity("金髮少女", 126011, self.rules), "可璃亞")
        self.assertEqual(gsa.resolve_speaker_identity("藍髮少女", 126111, self.rules), "普蕾西亞")
        self.assertEqual(gsa.resolve_speaker_identity("神秘女性", 118511, self.rules), "花凜")
        self.assertEqual(gsa.resolve_speaker_identity("Ｈ先生", 113411, self.rules), "初音")
        self.assertEqual(gsa.resolve_speaker_identity("反派千金", 139011, self.rules), "鏡華")
        self.assertEqual(gsa.resolve_speaker_identity("蠍獅少女", 134911, self.rules), "華音")
        self.assertEqual(gsa.resolve_speaker_identity("少女", 106411, self.rules), "雪菲")
        self.assertEqual(gsa.resolve_speaker_identity("姊姊", 107011, self.rules), "似似花")
        self.assertEqual(gsa.resolve_speaker_identity("姊姊", 135511, self.rules), "埃拉")

        # A1 早期 NPC / 特別編號 / 雙人卡子編號正確歸戶測試
        self.assertEqual(gsa.resolve_speaker_identity("愛梅斯", 190011, self.rules), "愛梅斯")
        self.assertEqual(gsa.resolve_speaker_identity("美空", 192011, self.rules), "美空")
        self.assertEqual(gsa.resolve_speaker_identity("花凜", 190811, self.rules), "花凜")
        self.assertEqual(gsa.resolve_speaker_identity("涅比亞", 190911, self.rules), "涅比亞")
        self.assertEqual(gsa.resolve_speaker_identity("班比", 140211, self.rules), "班比")
        self.assertEqual(gsa.resolve_speaker_identity("布武機", 140111, self.rules), "布武機")
        self.assertEqual(gsa.resolve_speaker_identity("克蘿茜", 140611, self.rules), "克蘿茜")
        self.assertEqual(gsa.resolve_speaker_identity("烏爾姆", 140511, self.rules), "烏爾姆")
        self.assertEqual(gsa.resolve_speaker_identity("涅婭", 191615, self.rules), "涅婭")
        self.assertEqual(gsa.resolve_speaker_identity("吉塔", 170111, self.rules), "吉塔")
        self.assertEqual(gsa.resolve_speaker_identity("志那都", 500011, self.rules), "志那都")
        self.assertEqual(gsa.resolve_speaker_identity("菲歐", 52731, self.rules), "菲歐")
        self.assertEqual(gsa.resolve_speaker_identity("初音", 118311, self.rules), "初音")
        self.assertEqual(gsa.resolve_speaker_identity("栞", 118411, self.rules), "栞")
        self.assertEqual(gsa.resolve_speaker_identity("美美", 120411, self.rules), "美美")
        self.assertEqual(gsa.resolve_speaker_identity("禊", 120511, self.rules), "禊")
        self.assertEqual(gsa.resolve_speaker_identity("鏡華", 120611, self.rules), "鏡華")
        self.assertEqual(gsa.resolve_speaker_identity("秋乃", 121711, self.rules), "秋乃")
        self.assertEqual(gsa.resolve_speaker_identity("咲戀", 121811, self.rules), "咲戀")
        self.assertEqual(gsa.resolve_speaker_identity("安", 124311, self.rules), "安")
        self.assertEqual(gsa.resolve_speaker_identity("古蕾婭", 124411, self.rules), "古蕾婭")
        self.assertEqual(gsa.resolve_speaker_identity("靜流", 128111, self.rules), "靜流")
        self.assertEqual(gsa.resolve_speaker_identity("璃乃", 128211, self.rules), "璃乃")
        self.assertEqual(gsa.resolve_speaker_identity("彩羽", 132611, self.rules), "彩羽")
        self.assertEqual(gsa.resolve_speaker_identity("苑", 132741, self.rules), "苑")

        # 正確歸戶測試（現實名/特殊別名）
        self.assertEqual(gsa.resolve_speaker_identity("耶兒", 126511, self.rules), "萊拉耶爾")
        self.assertEqual(gsa.resolve_speaker_identity("耶兒", 132811, self.rules), "萊拉耶爾")
        self.assertEqual(gsa.resolve_speaker_identity("耶兒", 138111, self.rules), "萊拉耶爾")
        self.assertEqual(gsa.resolve_speaker_identity("耶兒", None, self.rules), "萊拉耶爾")
        self.assertEqual(gsa.resolve_speaker_identity("晶", 106811, self.rules), "拉比林斯達")
        self.assertEqual(gsa.resolve_speaker_identity("晶", None, self.rules), "拉比林斯達")
        self.assertEqual(gsa.resolve_speaker_identity("真那", 106911, self.rules), "霸瞳皇帝")
        self.assertEqual(gsa.resolve_speaker_identity("菫", 133111, self.rules), "薇歐莉特")
        self.assertEqual(gsa.resolve_speaker_identity("黑暗伊緒", 119011, self.rules), "伊緒")
        self.assertEqual(gsa.resolve_speaker_identity("黑暗伊緒", 101811, self.rules), "伊緒")
        self.assertEqual(gsa.resolve_speaker_identity("尤絲蒂亞娜", 106911, self.rules), "霸瞳皇帝")
        self.assertEqual(gsa.resolve_speaker_identity("尤絲蒂亞娜", 105811, self.rules), "貪吃佩可")
        self.assertEqual(gsa.resolve_speaker_identity("宮子（剎鬼）", 135916, self.rules), "剎鬼")
        self.assertEqual(gsa.resolve_speaker_identity("１號", 136111, self.rules), "櫻")
        self.assertEqual(gsa.resolve_speaker_identity("秋乃&咲戀", 180911, self.rules), "秋乃＆咲戀")
        self.assertEqual(gsa.resolve_speaker_identity("貪吃佩可的聲音", None, self.rules), "貪吃佩可")

        # 1B 部分：21 組純中文 NPC 群組、重名 fallback 與嚴格隔離驗證
        self.assertEqual(gsa.resolve_appearance_target("神秘女性", 118511, self.rules), "花凜")
        self.assertEqual(gsa.resolve_appearance_target("神秘女性", 53011, self.rules), "冥")
        self.assertIsNone(gsa.resolve_appearance_target("神秘女性", 6511, self.rules))
        self.assertIsNone(gsa.resolve_appearance_target("神秘女性", None, self.rules))
        self.assertEqual(gsa.resolve_appearance_target("小嬰兒", 50911, self.rules), "小律")
        self.assertIsNone(gsa.resolve_appearance_target("小嬰兒", None, self.rules))
        self.assertEqual(gsa.resolve_npc_group("吉諾", 16011, self.rules), "賭場王")
        self.assertEqual(gsa.resolve_npc_group("前賭場王", 16011, self.rules), "賭場王")
        self.assertEqual(gsa.resolve_npc_group("鬼魂豪紳", 191411, self.rules), "豪紳")
        self.assertEqual(gsa.resolve_npc_group("貴族議長", 191411, self.rules), "豪紳")
        self.assertEqual(gsa.resolve_npc_group("阿澤爾德的幻影", 191911, self.rules), "阿澤爾德")
        self.assertEqual(gsa.resolve_npc_group("阿澤爾德？", 191911, self.rules), "阿澤爾德")
        self.assertEqual(gsa.resolve_npc_group("彌勒的聲音", 192611, self.rules), "彌勒")
        self.assertEqual(gsa.resolve_npc_group("分身格魯尼", 194311, self.rules), "格魯尼")
        self.assertEqual(gsa.resolve_npc_group("露易絲瑪莉的祖母", 53111, self.rules), "瑪莉絲黛菈")
        self.assertEqual(gsa.resolve_npc_group("梅杜莎‧米亞", 51611, self.rules), "米亞")
        self.assertEqual(gsa.resolve_npc_group("骷髏老爸？", 2411, self.rules), "骷髏老爸")
        self.assertEqual(gsa.resolve_npc_group("骷髏頭", 2411, self.rules), "骷髏老爸")
        self.assertEqual(gsa.resolve_npc_group("諾斯德拉達姆斯？", 2712, self.rules), "昴")
        self.assertEqual(gsa.resolve_npc_group("拉格？", 50211, self.rules), "拉格")
        self.assertIsNone(gsa.resolve_npc_group("帆稀？", 50211, self.rules))
        self.assertEqual(gsa.resolve_npc_group("雨神大人", 11611, self.rules), "雨吉")
        self.assertEqual(gsa.resolve_npc_group("似龍生物", 12311, self.rules), "似龍")
        self.assertEqual(gsa.resolve_npc_group("機械玩具王", 14911, self.rules), "玩具王")
        self.assertIsNone(gsa.resolve_npc_group("玩具王二世", 14911, self.rules))
        self.assertEqual(gsa.resolve_npc_group("好朋友Ｘ？", 13211, self.rules), "好朋友X")
        self.assertEqual(gsa.resolve_npc_group("鯊魚魔物", 13711, self.rules), "鮫肌牙之丞")
        self.assertEqual(gsa.resolve_npc_group("超級‧衝刺喬", 18711, self.rules), "瘋狂喬")
        self.assertEqual(gsa.resolve_npc_group("扭曲的音寵之精靈", 19211, self.rules), "音寵之精靈")
        self.assertEqual(gsa.resolve_npc_group("館主", 17511, self.rules), "莫夫")
        self.assertEqual(gsa.resolve_npc_group("宇宙蓋登", 50512, self.rules), "改造蓋登")
        self.assertIsNone(gsa.resolve_npc_group("蓋登", 50511, self.rules))
        self.assertEqual(gsa.resolve_appearance_target("蓋登", 50511, self.rules), "蓋登")
        self.assertEqual(gsa.resolve_appearance_target("優衣？", None, self.rules), "優衣？")
        self.assertIsNone(gsa.resolve_appearance_target("ぷうきち", None, self.rules))

    def test_04_speaker_appearance_output_contracts(self):
        # 1) speaker_appearance.json 絕不可含日文假名
        self.assertEqual([k for k in self.appearance if gsa.has_japanese_kana(k)], [])

        # 2) NPC 合併代表鍵與未合併獨立 NPC 應保留；已併入群組之別名與匿名路人不得再獨立存在
        for kept in (
            "大神", "尾狗刀", "拉基拉基", "贊恩", "宙", "芙蕾雅", "八斗神", "米奈娃",
            "賭場王", "豪紳", "阿澤爾德", "彌勒", "格魯尼", "冥", "瑪莉絲黛菈", "米亞",
            "骷髏老爸", "昴", "拉格", "雨吉", "似龍", "玩具王", "好朋友X",
            "鮫肌牙之丞", "瘋狂喬", "音寵之精靈", "莫夫", "小律", "改造蓋登", "蓋登",
            "長老", "嚮導老君", "剎鬼‧八斗神", "帆稀？", "玩具王二世",
            "萬能人偶", "金幣怪", "霸瞳皇帝？", "優衣？", "啾", "啾太", "時間管理員", "時間儀", "梅杜希亞娜", "大蛇",
            "TYPE-R", "艾爾格雅", "TYPE-Q", "蕾忒", "TYPE-P", "澄花",
            "羅塞塔", "變成依里的茜里", "假帆稀", "偽惠理子", "怪奇怪靈", "美空的角色", "卡里莎", "史萊姆們",
        ):
            self.assertIn(kept, self.appearance, f"名稱 {kept} 應保留於 speaker_appearance.json")

        for absent in (
            "？？？", "旁白", "【系統】",
            "晶", "真那", "菫", "耶兒", "菲歐？", "黑暗伊緒", "黑暗空花", "黑暗靜流",
            "Misty★霞", "Purely★栞", "Lovely★莫妮卡", "Shiny★智",
            "諾維姆", "修特帕魯", "阿剌克涅女士", "誓約女君", "變貌大妃", "変貌大妃",
            "迷宮女王", "拉比林θ", "鮮紅的立方體", "拜拉潔耶爾", "碧奇",
            "尤絲蒂亞娜", "宮子（剎鬼）", "貪吃佩可的聲音",
            "詠斗", "過去的詠斗", "尾狗刀？", "尾狗刀？？", "尾狗刀？？？",
            "拉基尼卡東", "跳躍王", "善", "贊恩？", "回憶的贊恩", "佐拉",
            "黎‧普賽爾", "菲絲雷斯", "通訊魔法的芙蕾雅", "八斗神局長", "米奈娃β", "過去的米奈娃",
            "吉諾", "前賭場王", "鬼魂豪紳", "貴族議長", "阿澤爾德的幻影", "阿澤爾德？",
            "彌勒的聲音", "分身格魯尼", "露易絲瑪莉的祖母", "梅杜莎‧米亞",
            "骷髏老爸？", "骷髏頭", "諾斯德拉達姆斯？", "拉格？", "雨神大人", "似龍生物",
            "機械玩具王", "好朋友Ｘ？", "鯊魚魔物", "超級‧衝刺喬", "扭曲的音寵之精靈",
            "館主", "小嬰兒", "宇宙蓋登",
            "小孩彩羽", "成人苑", "成人苑？", "神秘女性", "陌生的女性", "姊姊", "少女",
            "ジュン", "オクトー", "ナレーション", "ぷうきち",
        ):
            self.assertNotIn(absent, self.appearance, f"{absent} 不應以獨立 key 出現在 speaker_appearance.json")

        # 3) 驗證合併話數與 1411 未混入 櫻
        self.assertNotIn(1030006, self.appearance.get("櫻", []))
        self.assertEqual(len(self.appearance["尾狗刀"]), 72)
        self.assertEqual(len(self.appearance["拉基拉基"]), 58)
        self.assertEqual(len(self.appearance["贊恩"]), 41)
        self.assertEqual(len(self.appearance["宙"]), 17)
        self.assertEqual(len(self.appearance["長老"]), 7)
        self.assertEqual(len(self.appearance["嚮導老君"]), 4)
        self.assertEqual(len(self.appearance["芙蕾雅"]), 53)
        self.assertEqual(len(self.appearance["八斗神"]), 25)
        self.assertEqual(len(self.appearance["米奈娃"]), 25)
        self.assertEqual(len(self.appearance["賭場王"]), 17)
        self.assertEqual(len(self.appearance["豪紳"]), 21)
        self.assertEqual(len(self.appearance["阿澤爾德"]), 45)
        self.assertEqual(len(self.appearance["彌勒"]), 40)
        self.assertEqual(len(self.appearance["格魯尼"]), 21)
        self.assertEqual(len(self.appearance["冥"]), 9)
        self.assertEqual(len(self.appearance["瑪莉絲黛菈"]), 9)
        self.assertEqual(len(self.appearance["米亞"]), 37)
        self.assertEqual(len(self.appearance["骷髏老爸"]), 98)
        self.assertEqual(len(self.appearance["昴"]), 18)
        self.assertEqual(len(self.appearance["拉格"]), 21)
        self.assertEqual(len(self.appearance["雨吉"]), 10)
        self.assertEqual(len(self.appearance["似龍"]), 6)
        self.assertEqual(len(self.appearance["玩具王"]), 14)
        self.assertEqual(len(self.appearance["好朋友X"]), 15)
        self.assertEqual(len(self.appearance["鮫肌牙之丞"]), 5)
        self.assertEqual(len(self.appearance["瘋狂喬"]), 6)
        self.assertEqual(len(self.appearance["音寵之精靈"]), 8)
        self.assertEqual(len(self.appearance["莫夫"]), 11)
        self.assertEqual(len(self.appearance["小律"]), 4)
        self.assertEqual(len(self.appearance["改造蓋登"]), 5)
        self.assertEqual(len(self.appearance["蓋登"]), 3)
        self.assertEqual(len(self.appearance["愛梅斯"]), 544)
        self.assertEqual(len(self.appearance["美空"]), 162)
        self.assertEqual(len(self.appearance["花凜"]), 122)
        self.assertEqual(len(self.appearance["涅比亞"]), 53)
        self.assertEqual(len(self.appearance["班比"]), 47)
        self.assertEqual(len(self.appearance["布武機"]), 81)
        self.assertEqual(len(self.appearance["克蘿茜"]), 127)
        self.assertEqual(len(self.appearance["烏爾姆"]), 85)
        self.assertEqual(len(self.appearance["彩羽"]), 73)
        self.assertEqual(len(self.appearance["苑"]), 81)
        self.assertEqual(len(self.appearance["似似花"]), 165)

    def test_05_real_name_mapping_and_reality_avatar_fixes(self):
        with open(self.real_name_mapping_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        self.assertNotIn("秋乃＆咲戀", mapping)
        self.assertEqual(mapping.get("藤堂 秋乃＆佐佐木 咲戀"), "秋乃&咲戀")
        self.assertEqual(len(mapping.values()), len(set(mapping.values())))

        avatar_script = (ROOT_DIR / "tools" / "fetch_all_reality_avatars.py").read_text(encoding="utf-8")
        self.assertIn("現士實 似似花", avatar_script)
        self.assertNotIn("現士場 黑江", avatar_script)
        self.assertNotIn("現士場黑江", avatar_script)

        reality_map_path = ROOT_DIR / "dashboard" / "avatar_reality_mapping.json"
        with open(reality_map_path, "r", encoding="utf-8") as f:
            reality_map = json.load(f)
        self.assertEqual(reality_map.get("現士實 似似花"), 107032)
        self.assertEqual(reality_map.get("黑江 花子"), 110832)
        self.assertNotIn("現士場黑江", reality_map)
        self.assertNotIn("黑江", reality_map)

    def test_06_full_9420_story_corpus_audit(self):
        story_dir = ROOT_DIR / "dashboard" / "story"
        story_files = [
            fn for fn in sorted(os.listdir(story_dir))
            if fn.endswith(".json") and fn[:-5].isdigit()
        ]
        self.assertEqual(len(story_files), 9420)

        speaker_rules = self.rules["speaker_rules"]
        npc_rules = self.rules["npc_rules"]
        expected = {}
        misoka_npc_stories = set()
        karin_npc_stories = set()
        ames_npc_stories = set()

        for fn in story_files:
            sid = int(fn[:-5])
            with open(story_dir / fn, "r", encoding="utf-8") as f:
                items = json.load(f)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict) or item.get("type") != "dialogue":
                    continue
                raw = item.get("name")
                if not isinstance(raw, str):
                    continue
                cleaned = raw.strip()
                if not cleaned or gsa.has_japanese_kana(cleaned):
                    continue
                uid = gsa._normalize_unit_id(item.get("unit_id"))
                base_id = (uid // 100) if uid is not None else None

                if cleaned == "美空" and base_id == 1920:
                    misoka_npc_stories.add(sid)
                elif cleaned == "花凜" and base_id == 1908:
                    karin_npc_stories.add(sid)
                elif cleaned == "愛梅斯" and base_id == 1900:
                    ames_npc_stories.add(sid)

                if cleaned in speaker_rules or cleaned in npc_rules:
                    resolved = gsa.resolve_appearance_target(cleaned, uid, self.rules)
                    if resolved and not gsa.is_invalid_name(resolved):
                        expected.setdefault(resolved, set()).add(sid)
                    continue

                if gsa.is_invalid_name(cleaned):
                    continue

                for part in gsa.COMPOUND_SPLIT_RE.split(cleaned):
                    p = part.strip()
                    if not p or gsa.is_invalid_name(p):
                        continue
                    resolved = gsa.resolve_appearance_target(p, uid, self.rules)
                    if resolved and not gsa.is_invalid_name(resolved):
                        expected.setdefault(resolved, set()).add(sid)

        # 驗證 A1 已補齊 1900/1908/1920 對應本尊話數
        self.assertTrue(misoka_npc_stories <= set(self.appearance["美空"]))
        self.assertTrue(karin_npc_stories <= set(self.appearance["花凜"]))
        self.assertTrue(ames_npc_stories <= set(self.appearance["愛梅斯"]))
        self.assertGreater(len(misoka_npc_stories), 90)
        self.assertGreater(len(karin_npc_stories), 60)
        self.assertGreater(len(ames_npc_stories), 500)

        # 驗證 disk 上 speaker_appearance.json 與全語料稽核結果完全一致（零漂移）
        expected_sorted = {k: sorted(v) for k, v in expected.items()}
        self.assertEqual(self.appearance, expected_sorted)


if __name__ == "__main__":
    unittest.main()
